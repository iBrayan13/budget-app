from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Loan(TimestampMixin, Base):
    """Money you lent to someone. Lent in the platform's currency; no interest is tracked."""

    __tablename__ = "loans"
    __table_args__ = (CheckConstraint("principal > 0", name="principal_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    borrower: Mapped[str] = mapped_column(String(120))
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    currency: Mapped[str] = mapped_column(String(10))
    principal: Mapped[Decimal]
    start_date: Mapped[date]
    due_date: Mapped[date | None]
    notes: Mapped[str | None] = mapped_column(Text)


class LoanPayment(TimestampMixin, Base):
    """Money paid back to you, received in a platform of the loan's currency."""

    __tablename__ = "loan_payments"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    loan_id: Mapped[int] = mapped_column(ForeignKey("loans.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal]
    occurred_on: Mapped[date]
    notes: Mapped[str | None] = mapped_column(Text)
