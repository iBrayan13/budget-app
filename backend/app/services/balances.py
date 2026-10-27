from collections import defaultdict
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Loan, LoanPayment, Transaction, TransactionKind, Transfer


def account_movements(db: Session, user_id: int) -> dict[int, Decimal]:
    """Net movement per account (native currency): incomes - expenses +/- adjustments +/- transfers.

    Balance of an account = initial_balance + movement.
    """
    signed = case(
        (Transaction.kind == TransactionKind.EXPENSE, -Transaction.amount),
        else_=Transaction.amount,
    )
    totals: dict[int, Decimal] = defaultdict(Decimal)

    for account_id, total in db.execute(
        select(Transaction.account_id, func.sum(signed))
        .where(Transaction.user_id == user_id)
        .group_by(Transaction.account_id)
    ):
        totals[account_id] += total

    for account_id, total in db.execute(
        select(Transfer.from_account_id, func.sum(Transfer.amount_out))
        .where(Transfer.user_id == user_id)
        .group_by(Transfer.from_account_id)
    ):
        totals[account_id] -= total

    for account_id, total in db.execute(
        select(Transfer.to_account_id, func.sum(Transfer.amount_in))
        .where(Transfer.user_id == user_id)
        .group_by(Transfer.to_account_id)
    ):
        totals[account_id] += total

    # External fees leave the fee platform, on top of what was sent.
    for account_id, total in db.execute(
        select(Transfer.fee_account_id, func.sum(Transfer.fee_amount))
        .where(Transfer.user_id == user_id, Transfer.fee_account_id.is_not(None))
        .group_by(Transfer.fee_account_id)
    ):
        totals[account_id] -= total

    # Loans: money leaves the platform when lent and comes back with each payment.
    for account_id, total in db.execute(
        select(Loan.account_id, func.sum(Loan.principal))
        .where(Loan.user_id == user_id)
        .group_by(Loan.account_id)
    ):
        totals[account_id] -= total

    for account_id, total in db.execute(
        select(LoanPayment.account_id, func.sum(LoanPayment.amount))
        .join(Loan, Loan.id == LoanPayment.loan_id)
        .where(Loan.user_id == user_id)
        .group_by(LoanPayment.account_id)
    ):
        totals[account_id] += total

    return totals


def account_has_movements(db: Session, account_id: int) -> bool:
    tx = db.scalar(select(Transaction.id).where(Transaction.account_id == account_id).limit(1))
    if tx is not None:
        return True
    tr = db.scalar(
        select(Transfer.id)
        .where(
            (Transfer.from_account_id == account_id)
            | (Transfer.to_account_id == account_id)
            | (Transfer.fee_account_id == account_id)
        )
        .limit(1)
    )
    if tr is not None:
        return True
    return db.scalar(select(Loan.id).where(Loan.account_id == account_id).limit(1)) is not None
