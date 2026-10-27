from dataclasses import dataclass
from decimal import Decimal

from app.models import Transfer
from app.services.fx import RateResolver


@dataclass(frozen=True)
class TransferCost:
    """Everything in base currency. None when a reference rate is missing."""

    value_out: Decimal | None  # what left, at the reference rate
    value_in: Decimal | None  # what arrived, at the reference rate
    cost: Decimal | None  # value_out - value_in = fees + spread
    fee: Decimal | None  # explicit fee charged by the platform
    spread: Decimal | None  # hidden cost of the P2P rate vs reference

    @property
    def cost_pct(self) -> Decimal | None:
        if self.cost is None or not self.value_out:
            return None
        return self.cost / self.value_out * 100


def transfer_cost(t: Transfer, rates: RateResolver) -> TransferCost:
    """value_out is everything that left, in base currency, including an external fee."""
    external = t.fee_account_id is not None
    rate_out = t.ref_rate_out or rates.rate(t.from_account.currency, t.occurred_on)
    rate_in = t.ref_rate_in or rates.rate(t.to_account.currency, t.occurred_on)
    rate_fee = rates.rate(t.fee_account.currency, t.occurred_on) if external else rate_out

    value_in = t.amount_in / rate_in if rate_in else None
    fee = t.fee_amount / rate_fee if rate_fee else None
    value_out = None
    if rate_out and (not external or fee is not None):
        value_out = t.amount_out / rate_out + (fee if external else 0)
    cost = value_out - value_in if value_out is not None and value_in is not None else None
    spread = cost - fee if cost is not None and fee is not None else None
    return TransferCost(value_out, value_in, cost, fee, spread)
