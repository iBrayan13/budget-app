from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_owned
from app.models import Account
from app.schemas.accounts import AccountCreate, AccountOut, AccountsSummary, AccountUpdate
from app.services.balances import account_has_movements, account_movements
from app.services.fx import RateResolver, money
from app.services.goals import reserved_on_account

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _ensure_unique_name(db: DbSession, user_id: int, name: str, exclude_id: int | None = None):
    q = select(Account.id).where(Account.user_id == user_id, Account.name == name)
    if exclude_id is not None:
        q = q.where(Account.id != exclude_id)
    if db.scalar(q) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya tienes una plataforma llamada {name}")


@router.get("", response_model=AccountsSummary)
def list_accounts(db: DbSession, user: CurrentUser, include_inactive: bool = False):
    q = select(Account).where(Account.user_id == user.id).order_by(Account.name)
    if not include_inactive:
        q = q.where(Account.is_active)
    accounts = db.scalars(q).all()

    movements = account_movements(db, user.id)
    rates = RateResolver(db, user)
    today = date.today()
    out = [
        _out(a, a.initial_balance + movements.get(a.id, Decimal(0)), rates.rate(a.currency, today))
        for a in accounts
    ]
    return AccountsSummary(
        base_currency=user.base_currency,
        total_base=sum((a.balance_base for a in out if a.balance_base is not None), Decimal(0)),
        accounts_without_rate=[a.name for a in out if a.balance_base is None and a.balance != 0],
        accounts=out,
    )


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(body: AccountCreate, db: DbSession, user: CurrentUser):
    _ensure_unique_name(db, user.id, body.name)
    account = Account(user_id=user.id, **body.model_dump())
    db.add(account)
    db.commit()
    rate = RateResolver(db, user).rate(account.currency, date.today())
    return _out(account, account.initial_balance, rate)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(account_id: int, body: AccountUpdate, db: DbSession, user: CurrentUser):
    account = get_owned(db, Account, account_id, user, "Plataforma")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("is_active") is False and reserved_on_account(db, account.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta plataforma tiene dinero apartado en metas; libéralo antes de archivarla",
        )
    if "name" in changes:
        _ensure_unique_name(db, user.id, changes["name"], exclude_id=account.id)
    for field, value in changes.items():
        setattr(account, field, value)
    db.commit()
    balance = account.initial_balance + account_movements(db, user.id).get(account.id, Decimal(0))
    return _out(account, balance, RateResolver(db, user).rate(account.currency, date.today()))


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, db: DbSession, user: CurrentUser):
    account = get_owned(db, Account, account_id, user, "Plataforma")
    if account_has_movements(db, account.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La plataforma tiene movimientos; archívala en lugar de borrarla",
        )
    db.delete(account)
    db.commit()


def _out(account: Account, balance: Decimal, rate: Decimal | None) -> AccountOut:
    return AccountOut(
        id=account.id,
        name=account.name,
        kind=account.kind,
        currency=account.currency,
        initial_balance=account.initial_balance,
        is_active=account.is_active,
        notes=account.notes,
        balance=balance,
        rate=rate,
        balance_base=money(balance / rate) if rate else None,
    )
