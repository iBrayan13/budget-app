from collections import defaultdict
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Transaction, TransactionKind, Transfer


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

    return totals


def account_has_movements(db: Session, account_id: int) -> bool:
    tx = db.scalar(select(Transaction.id).where(Transaction.account_id == account_id).limit(1))
    if tx is not None:
        return True
    tr = db.scalar(
        select(Transfer.id)
        .where((Transfer.from_account_id == account_id) | (Transfer.to_account_id == account_id))
        .limit(1)
    )
    return tr is not None
