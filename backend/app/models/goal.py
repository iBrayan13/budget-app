from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, str_enum


class GoalKind(StrEnum):
    SAVINGS = "savings"  # PC, carro, moto, casa, iniciales...
    EMERGENCY_FUND = "emergency_fund"  # target = months x survival cost (computed)


class SavingsGoal(TimestampMixin, Base):
    """A virtual envelope: money stays on its platform but is reserved via allocations."""

    __tablename__ = "savings_goals"
    __table_args__ = (
        CheckConstraint(
            "kind = 'emergency_fund' OR target_amount IS NOT NULL", name="savings_needs_target"
        ),
        CheckConstraint("target_amount IS NULL OR target_amount > 0", name="target_positive"),
        Index(
            "uq_savings_goals_one_emergency_fund",
            "user_id",
            unique=True,
            postgresql_where=text("kind = 'emergency_fund'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[GoalKind] = mapped_column(str_enum(GoalKind), default=GoalKind.SAVINGS)
    name: Mapped[str] = mapped_column(String(120))
    target_amount: Mapped[Decimal | None]  # base currency
    target_date: Mapped[date | None]
    priority: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[str | None] = mapped_column(Text)


class GoalAllocation(TimestampMixin, Base):
    """Reserve (positive) or release (negative) money of an account for a goal."""

    __tablename__ = "goal_allocations"
    __table_args__ = (CheckConstraint("amount <> 0", name="amount_non_zero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(
        ForeignKey("savings_goals.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal]  # in the account currency
    allocated_on: Mapped[date]
    notes: Mapped[str | None] = mapped_column(Text)
