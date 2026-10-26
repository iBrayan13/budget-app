from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, str_enum


class DebtKind(StrEnum):
    INSTALLMENT_LOAN = "installment_loan"  # fixed installments (generates obligations)
    CREDIT_CARD = "credit_card"  # balance tracked on a credit_card account
    INFORMAL = "informal"  # owed to a person, no fixed schedule


class Debt(TimestampMixin, Base):
    """Payments are transactions with debt_id (or transfers into the credit card account)."""

    __tablename__ = "debts"
    __table_args__ = (
        CheckConstraint("original_amount > 0", name="original_amount_positive"),
        CheckConstraint(
            "kind <> 'credit_card' OR account_id IS NOT NULL", name="credit_card_needs_account"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[DebtKind] = mapped_column(str_enum(DebtKind))
    creditor: Mapped[str | None] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(10))
    original_amount: Mapped[Decimal]
    interest_rate_annual: Mapped[Decimal | None]  # percentage, e.g. 28.5
    installment_amount: Mapped[Decimal | None]
    installments_total: Mapped[int | None]
    start_date: Mapped[date]
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    recurring_expense_id: Mapped[int | None] = mapped_column(
        ForeignKey("recurring_expenses.id", ondelete="SET NULL"), unique=True
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[str | None] = mapped_column(Text)
