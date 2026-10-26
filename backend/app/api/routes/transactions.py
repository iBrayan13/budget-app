from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_owned
from app.models import (
    Account,
    Category,
    CategoryKind,
    Obligation,
    ObligationStatus,
    Transaction,
    TransactionKind,
    User,
)
from app.schemas.transactions import TransactionIn, TransactionOut
from app.services.fx import RateResolver, money

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _validate_refs(db: DbSession, user: User, body: TransactionIn) -> Account:
    account = get_owned(db, Account, body.account_id, user, "Plataforma")
    if body.category_id is not None:
        category = get_owned(db, Category, body.category_id, user, "Categoría")
        expected = (
            CategoryKind.INCOME if body.kind == TransactionKind.INCOME else CategoryKind.EXPENSE
        )
        if category.kind != expected:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "La categoría no corresponde al tipo de movimiento",
            )
    return account


def _out(t: Transaction, rates: RateResolver) -> TransactionOut:
    out = TransactionOut.model_validate(t)
    out.amount_base = money(rates.to_base(t.amount, t.currency, t.occurred_on, t.fx_rate))
    return out


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    db: DbSession,
    user: CurrentUser,
    start: date | None = None,
    end: date | None = None,
    account_id: int | None = None,
    category_id: int | None = None,
    kind: TransactionKind | None = None,
    limit: int = 500,
):
    q = select(Transaction).where(Transaction.user_id == user.id)
    if start:
        q = q.where(Transaction.occurred_on >= start)
    if end:
        q = q.where(Transaction.occurred_on <= end)
    if account_id:
        q = q.where(Transaction.account_id == account_id)
    if category_id:
        q = q.where(Transaction.category_id == category_id)
    if kind:
        q = q.where(Transaction.kind == kind)
    q = q.order_by(Transaction.occurred_on.desc(), Transaction.id.desc()).limit(min(limit, 2000))
    rates = RateResolver(db, user)
    return [_out(t, rates) for t in db.scalars(q)]


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(body: TransactionIn, db: DbSession, user: CurrentUser):
    account = _validate_refs(db, user, body)
    t = Transaction(user_id=user.id, currency=account.currency, **body.model_dump())
    db.add(t)
    db.commit()
    return _out(t, RateResolver(db, user))


@router.put("/{transaction_id}", response_model=TransactionOut)
def replace_transaction(transaction_id: int, body: TransactionIn, db: DbSession, user: CurrentUser):
    t = get_owned(db, Transaction, transaction_id, user, "Movimiento")
    account = _validate_refs(db, user, body)
    for field, value in body.model_dump().items():
        setattr(t, field, value)
    t.currency = account.currency
    db.commit()
    return _out(t, RateResolver(db, user))


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: int, db: DbSession, user: CurrentUser):
    t = get_owned(db, Transaction, transaction_id, user, "Movimiento")
    if t.obligation_id is not None:
        # The fixed-expense payment it settled becomes pending again.
        obligation = db.get(Obligation, t.obligation_id)
        obligation.status = ObligationStatus.PENDING
    db.delete(t)
    db.commit()
