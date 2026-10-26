from bisect import bisect_right
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExchangeRate, User

# Assumed 1:1 with USD when the user has not entered a rate for them.
USD_STABLECOINS = {"USDT", "USDC"}

CENT = Decimal("0.01")


class RateResolver:
    """Finds the manual reference rate (units of `currency` per 1 base unit) for a date.

    Uses the latest rate on or before the date; if none exists yet, the earliest one after it.
    Loads each currency's rates once per request.
    """

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user_id = user.id
        self.base = user.base_currency
        self._cache: dict[str, tuple[list[date], list[Decimal]]] = {}

    def _load(self, currency: str) -> tuple[list[date], list[Decimal]]:
        if currency not in self._cache:
            rows = self.db.execute(
                select(ExchangeRate.rate_date, ExchangeRate.rate)
                .where(ExchangeRate.user_id == self.user_id, ExchangeRate.currency == currency)
                .order_by(ExchangeRate.rate_date)
            ).all()
            self._cache[currency] = ([r[0] for r in rows], [r[1] for r in rows])
        return self._cache[currency]

    def rate(self, currency: str, on: date) -> Decimal | None:
        if currency == self.base:
            return Decimal(1)
        dates, rates = self._load(currency)
        if dates:
            i = bisect_right(dates, on)
            return rates[i - 1] if i > 0 else rates[0]
        if self.base == "USD" and currency in USD_STABLECOINS:
            return Decimal(1)
        return None

    def to_base(self, amount: Decimal, currency: str, on: date, rate: Decimal | None = None):
        rate = rate or self.rate(currency, on)
        return None if rate is None else amount / rate


def money(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(CENT)
