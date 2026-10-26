from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models import AccountKind
from app.schemas.common import Amount, Currency, Dec, Name


class AccountCreate(BaseModel):
    name: Name
    kind: AccountKind
    currency: Currency
    initial_balance: Amount = Decimal(0)
    notes: str | None = None


class AccountUpdate(BaseModel):
    """Currency cannot change: existing movements are recorded in it."""

    name: Name | None = None
    kind: AccountKind | None = None
    initial_balance: Amount | None = None
    is_active: bool | None = None
    notes: str | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: AccountKind
    currency: str
    initial_balance: Dec
    is_active: bool
    notes: str | None
    balance: Dec
    rate: Dec | None  # units of currency per 1 base unit, None if unknown
    balance_base: Dec | None


class AccountsSummary(BaseModel):
    base_currency: str
    total_base: Dec
    accounts_without_rate: list[str]
    accounts: list[AccountOut]
