from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_owned
from app.models import Account, Loan, LoanPayment
from app.schemas.loans import LoanIn, LoanOut, LoanPaymentIn, LoanPaymentOut, LoansSummary
from app.services.fx import RateResolver, money
from app.services.goals import account_balance, reserved_on_account

router = APIRouter(tags=["loans"])

Z = Decimal(0)


def _payment_out(p: LoanPayment, account: Account) -> LoanPaymentOut:
    return LoanPaymentOut(
        id=p.id,
        account_id=p.account_id,
        account_name=account.name,
        amount=p.amount,
        occurred_on=p.occurred_on,
        notes=p.notes,
    )


def _loan_out(db: DbSession, loan: Loan, rates: RateResolver, today: date) -> LoanOut:
    rows = db.execute(
        select(LoanPayment, Account)
        .join(Account, Account.id == LoanPayment.account_id)
        .where(LoanPayment.loan_id == loan.id)
        .order_by(LoanPayment.occurred_on, LoanPayment.id)
    ).all()
    paid = sum((p.amount for p, _ in rows), Z)
    balance = loan.principal - paid
    rate = rates.rate(loan.currency, today)
    account = db.get(Account, loan.account_id)
    return LoanOut(
        id=loan.id,
        borrower=loan.borrower,
        account_id=loan.account_id,
        account_name=account.name,
        currency=loan.currency,
        principal=loan.principal,
        start_date=loan.start_date,
        due_date=loan.due_date,
        notes=loan.notes,
        paid=money(paid),
        balance=money(balance),
        balance_base=money(balance / rate) if rate else None,
        progress_pct=money(paid / loan.principal * 100),
        payments=[_payment_out(p, acc) for p, acc in rows],
    )


@router.get("/loans", response_model=LoansSummary)
def list_loans(db: DbSession, user: CurrentUser):
    today = date.today()
    rates = RateResolver(db, user)
    items = [
        _loan_out(db, loan, rates, today)
        for loan in db.scalars(
            select(Loan)
            .where(Loan.user_id == user.id)
            .order_by(Loan.start_date.desc(), Loan.id.desc())
        )
    ]
    total = sum((i.balance_base for i in items if i.balance_base is not None), Z)
    return LoansSummary(
        base_currency=user.base_currency, total_balance_base=money(total), items=items
    )


@router.post("/loans", status_code=status.HTTP_201_CREATED)
def create_loan(body: LoanIn, db: DbSession, user: CurrentUser) -> dict[str, int]:
    account = get_owned(db, Account, body.account_id, user, "Plataforma")
    free = account_balance(db, user, account) - reserved_on_account(db, account.id)
    if body.amount > free:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Solo tienes {free:.2f} {account.currency} libres en {account.name}",
        )
    loan = Loan(
        user_id=user.id,
        borrower=body.borrower,
        account_id=account.id,
        currency=account.currency,
        principal=body.amount,
        start_date=body.start_date,
        due_date=body.due_date,
        notes=body.notes,
    )
    db.add(loan)
    db.commit()
    return {"id": loan.id}


@router.delete("/loans/{loan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loan(loan_id: int, db: DbSession, user: CurrentUser) -> None:
    """Deleting a loan undoes it: the money goes back to its platform, payments included."""
    db.delete(get_owned(db, Loan, loan_id, user, "Préstamo"))
    db.commit()


@router.post("/loans/{loan_id}/payments", status_code=status.HTTP_201_CREATED)
def add_payment(
    loan_id: int, body: LoanPaymentIn, db: DbSession, user: CurrentUser
) -> dict[str, int]:
    loan = get_owned(db, Loan, loan_id, user, "Préstamo")
    account = get_owned(db, Account, body.account_id, user, "Plataforma")
    if account.currency != loan.currency:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"El préstamo es en {loan.currency}: cobra a una plataforma en {loan.currency}",
        )
    paid = sum(
        db.scalars(select(LoanPayment.amount).where(LoanPayment.loan_id == loan.id)).all(), Z
    )
    outstanding = loan.principal - paid
    if body.amount > outstanding:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Solo falta cobrar {outstanding:.2f} {loan.currency}",
        )
    payment = LoanPayment(
        loan_id=loan.id, account_id=account.id, **body.model_dump(exclude={"account_id"})
    )
    db.add(payment)
    db.commit()
    return {"id": payment.id}


@router.delete("/loan-payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(payment_id: int, db: DbSession, user: CurrentUser) -> None:
    payment = db.get(LoanPayment, payment_id)
    loan = db.get(Loan, payment.loan_id) if payment else None
    if loan is None or loan.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cobro no encontrado")
    account = db.get(Account, payment.account_id)
    # Undoing a payment takes that money out of the platform again: it must still be free there.
    free = account_balance(db, user, account) - reserved_on_account(db, account.id)
    if payment.amount > free:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"No puedes deshacer este cobro: {account.name} ya tiene menos dinero libre",
        )
    db.delete(payment)
    db.commit()
