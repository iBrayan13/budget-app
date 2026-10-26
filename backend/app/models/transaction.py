from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.account import Account
from app.models.base import Base, TimestampMixin, str_enum


class TransactionKind(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    ADJUSTMENT = "adjustment"  # signed correction to match the real platform balance


class Transaction(TimestampMixin, Base):
    """Income or expense on one account, in that account's currency.

    `fx_rate` = units of the account currency per 1 base-currency unit at that moment.
    When null, the closest manual exchange rate is used.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("kind = 'adjustment' OR amount > 0", name="amount_positive"),
        CheckConstraint("fx_rate IS NULL OR fx_rate > 0", name="fx_rate_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[TransactionKind] = mapped_column(str_enum(TransactionKind))
    amount: Mapped[Decimal]
    fx_rate: Mapped[Decimal | None]
    occurred_on: Mapped[date] = mapped_column(index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT")
    )
    obligation_id: Mapped[int | None] = mapped_column(
        ForeignKey("obligations.id", ondelete="SET NULL"), unique=True
    )
    debt_id: Mapped[int | None] = mapped_column(ForeignKey("debts.id", ondelete="SET NULL"))
    currency: Mapped[str] = mapped_column(String(10))  # copy of the account currency

    account: Mapped[Account] = relationship(lazy="joined")
