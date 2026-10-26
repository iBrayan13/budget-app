from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.models import DebtKind
from app.schemas.common import Currency, Dec, LongName, PositiveAmount, Rate


class DebtScheduleIn(BaseModel):
    """Fixed installments. Creates (or updates) a linked fixed expense with its obligations."""

    installment_amount: PositiveAmount
    rrule: str = Field(default="FREQ=MONTHLY", max_length=255)
    first_due_date: date
    installments_total: int | None = Field(default=None, ge=1, le=1200)
    account_id: int | None = None  # platform you usually pay from


class DebtIn(BaseModel):
    name: LongName
    kind: DebtKind
    creditor: str | None = Field(default=None, max_length=120)
    currency: Currency
    original_amount: PositiveAmount
    interest_rate_annual: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=4)
    start_date: date
    account_id: int | None = None  # the credit_card account, for kind=credit_card
    schedule: DebtScheduleIn | None = None
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.kind == DebtKind.CREDIT_CARD and self.account_id is None:
            raise ValueError("Una tarjeta de crédito necesita su plataforma (cuenta de la tarjeta)")
        if self.kind == DebtKind.INSTALLMENT_LOAN and self.schedule is None:
            raise ValueError("Un préstamo a cuotas necesita el plan de cuotas")
        return self


class DebtOut(BaseModel):
    id: int
    name: str
    kind: DebtKind
    creditor: str | None
    currency: str
    original_amount: Dec
    interest_rate_annual: Dec | None
    installment_amount: Dec | None
    installments_total: int | None
    start_date: date
    account_id: int | None
    recurring_expense_id: int | None
    schedule_rrule: str | None
    schedule_first_due_date: date | None
    schedule_account_id: int | None
    is_active: bool
    notes: str | None
    # Computed
    paid_total: Dec
    payments_count: int
    balance: Dec
    balance_base: Dec | None
    progress_pct: Dec
    remaining_installments: int | None
    monthly_payment: Dec | None
    monthly_payment_base: Dec | None
    total_interest: Dec | None
    next_due_date: date | None
    next_due_amount: Dec | None
    end_date: date | None


class DebtsSummary(BaseModel):
    base_currency: str
    total_balance_base: Dec
    monthly_payments_base: Dec
    avg_monthly_income_base: Dec | None
    debt_ratio_pct: Dec | None  # monthly installments / income
    max_ratio_pct: Dec
    capacity_base: Dec | None  # extra monthly installment you could take on
    items: list[DebtOut]


class DebtPaymentIn(BaseModel):
    """Extra payment (abono). For credit cards it becomes a transfer into the card account."""

    account_id: int
    amount: PositiveAmount  # in the paying account currency
    amount_in: PositiveAmount | None = None  # credit cards only, when currencies differ
    occurred_on: date
    fx_rate: Rate | None = None
    description: str | None = Field(default=None, max_length=500)
