from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Dec, LongName, PositiveAmount


class LoanIn(BaseModel):
    borrower: LongName
    account_id: int  # platform the money leaves from
    amount: PositiveAmount
    start_date: date
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)


class LoanPaymentIn(BaseModel):
    account_id: int  # platform the money comes back to (same currency as the loan)
    amount: PositiveAmount
    occurred_on: date
    notes: str | None = Field(default=None, max_length=500)


class LoanPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    account_name: str
    amount: Dec
    occurred_on: date
    notes: str | None


class LoanOut(BaseModel):
    id: int
    borrower: str
    account_id: int
    account_name: str
    currency: str
    principal: Dec
    start_date: date
    due_date: date | None
    notes: str | None
    paid: Dec
    balance: Dec
    balance_base: Dec | None
    progress_pct: Dec
    payments: list[LoanPaymentOut]


class LoansSummary(BaseModel):
    base_currency: str
    total_balance_base: Dec
    principal_total_base: Dec
    paid_total_base: Dec
    items: list[LoanOut]
