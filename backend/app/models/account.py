from decimal import Decimal
from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, str_enum


class AccountKind(StrEnum):
    BANK = "bank"  # Facebank
    EXCHANGE = "exchange"  # Binance
    WALLET = "wallet"  # Zinli, El Dorado, Nequi
    CASH = "cash"
    CREDIT_CARD = "credit_card"  # balance usually negative
    OTHER = "other"


class Account(TimestampMixin, Base):
    """A platform where money lives. Balance = initial_balance + movements."""

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[AccountKind] = mapped_column(str_enum(AccountKind))
    currency: Mapped[str] = mapped_column(String(10))  # USD, USDT, COP, VES...
    initial_balance: Mapped[Decimal] = mapped_column(default=Decimal(0))
    is_active: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[str | None] = mapped_column(Text)
