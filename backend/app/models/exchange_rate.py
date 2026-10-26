from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ExchangeRate(TimestampMixin, Base):
    """Manual reference rate: how many units of `currency` equal 1 unit of the base currency.

    Example (base USD): COP 4100 means 1 USD = 4100 COP. Used to value balances and to
    measure the hidden cost (spread) of P2P transfers.
    """

    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("user_id", "currency", "rate_date"),
        CheckConstraint("rate > 0", name="rate_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    currency: Mapped[str] = mapped_column(String(10))
    rate_date: Mapped[date]
    rate: Mapped[Decimal]
