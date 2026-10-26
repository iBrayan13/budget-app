from datetime import date
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.models import ExpenseLevel, ObligationStatus
from app.schemas.common import Currency, Dec, LongName, PositiveAmount, Rate


class RecurringExpenseIn(BaseModel):
    name: LongName
    category_id: int
    account_id: int | None = None  # usual paying platform
    amount: PositiveAmount
    currency: Currency
    rrule: str = Field(max_length=255)
    start_date: date  # first due date to track
    end_date: date | None = None
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def check_dates(self) -> Self:
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("La fecha de fin no puede ser anterior al inicio")
        return self


class RecurringExpenseOut(BaseModel):
    id: int
    name: str
    category_id: int
    level: ExpenseLevel | None
    account_id: int | None
    amount: Dec
    currency: str
    rrule: str
    start_date: date
    end_date: date | None
    is_active: bool
    notes: str | None
    debt_id: int | None
    per_month: Dec  # occurrences per month
    monthly_amount: Dec  # in the expense currency
    monthly_amount_base: Dec | None
    next_due_date: date | None


class RecurringSummary(BaseModel):
    base_currency: str
    monthly_total_base: Dec
    monthly_essential_base: Dec
    monthly_lifestyle_base: Dec
    without_rate: list[str]
    items: list[RecurringExpenseOut]


class SchedulePreviewIn(BaseModel):
    rrule: str = Field(max_length=255)
    start_date: date
    end_date: date | None = None
    count: int = Field(default=6, ge=1, le=24)


class SchedulePreviewOut(BaseModel):
    rrule: str
    dates: list[date]
    per_month: Dec


class ObligationOut(BaseModel):
    id: int
    recurring_expense_id: int
    name: str
    category_id: int
    account_id: int | None
    debt_id: int | None
    due_date: date
    expected_amount: Dec
    currency: str
    expected_base: Dec | None
    status: ObligationStatus
    is_overdue: bool
    transaction_id: int | None
    paid_amount: Dec | None
    paid_currency: str | None


class PayObligationIn(BaseModel):
    account_id: int
    # In the account currency. Optional when it matches the obligation currency.
    amount: PositiveAmount | None = None
    occurred_on: date | None = None  # defaults to today
    fx_rate: Rate | None = None
    description: str | None = Field(default=None, max_length=500)
