from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.account import Account
from app.models.base import Base, TimestampMixin


class TransferRoute(TimestampMixin, Base):
    """Groups the steps of one P2P chain, e.g. Facebank -> Binance -> Zinli -> Nequi."""

    __tablename__ = "transfer_routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str | None] = mapped_column(String(120))
    started_on: Mapped[date]
    notes: Mapped[str | None] = mapped_column(Text)

    steps: Mapped[list["Transfer"]] = relationship(
        back_populates="route", order_by="Transfer.step", passive_deletes=True
    )


class Transfer(TimestampMixin, Base):
    """Money moving between two of your platforms, possibly changing currency.

    Real cost in base currency =
        amount_out / ref_rate_out - amount_in / ref_rate_in
    which includes explicit fees (fee_amount, already part of amount_out) and the
    hidden spread of the P2P rate. ref rates fall back to the manual exchange_rates.
    """

    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint("from_account_id <> to_account_id", name="different_accounts"),
        CheckConstraint("amount_out > 0 AND amount_in > 0", name="amounts_positive"),
        CheckConstraint("fee_amount >= 0", name="fee_non_negative"),
        CheckConstraint("ref_rate_out IS NULL OR ref_rate_out > 0", name="ref_rate_out_positive"),
        CheckConstraint("ref_rate_in IS NULL OR ref_rate_in > 0", name="ref_rate_in_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    route_id: Mapped[int | None] = mapped_column(
        ForeignKey("transfer_routes.id", ondelete="SET NULL"), index=True
    )
    step: Mapped[int | None]
    from_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    to_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    amount_out: Mapped[Decimal]
    amount_in: Mapped[Decimal]
    fee_amount: Mapped[Decimal] = mapped_column(default=Decimal(0))  # in the source currency
    ref_rate_out: Mapped[Decimal | None]
    ref_rate_in: Mapped[Decimal | None]
    occurred_on: Mapped[date] = mapped_column(index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    route: Mapped[TransferRoute | None] = relationship(back_populates="steps")
    from_account: Mapped[Account] = relationship(foreign_keys=[from_account_id], lazy="joined")
    to_account: Mapped[Account] = relationship(foreign_keys=[to_account_id], lazy="joined")
