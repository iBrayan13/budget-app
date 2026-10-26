from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, str_enum


class RecurringExpense(TimestampMixin, Base):
    """Fixed expense with a schedule (monthly, every 2 months, days 15 and 30, yearly...).

    `rrule` is an RFC 5545 rule without DTSTART, e.g. "FREQ=MONTHLY;INTERVAL=2" or
    "FREQ=MONTHLY;BYMONTHDAY=15,-1". `start_date` acts as DTSTART.
    """

    __tablename__ = "recurring_expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="valid_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    amount: Mapped[Decimal]
    currency: Mapped[str] = mapped_column(String(10))
    rrule: Mapped[str] = mapped_column(String(255))
    start_date: Mapped[date]
    end_date: Mapped[date | None]
    is_active: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[str | None] = mapped_column(Text)


class ObligationStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    SKIPPED = "skipped"


class Obligation(TimestampMixin, Base):
    """A concrete occurrence of a recurring expense. Overdue = pending and due_date < today."""

    __tablename__ = "obligations"
    __table_args__ = (UniqueConstraint("recurring_expense_id", "due_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    recurring_expense_id: Mapped[int] = mapped_column(
        ForeignKey("recurring_expenses.id", ondelete="CASCADE"), index=True
    )
    due_date: Mapped[date] = mapped_column(index=True)
    expected_amount: Mapped[Decimal]
    currency: Mapped[str] = mapped_column(String(10))
    status: Mapped[ObligationStatus] = mapped_column(
        str_enum(ObligationStatus), default=ObligationStatus.PENDING
    )
