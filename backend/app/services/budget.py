from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transaction, TransactionKind, User
from app.services.fx import RateResolver


def month_start(d: date, months_back: int = 0) -> date:
    y, m = d.year, d.month - months_back
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def average_monthly_income(
    db: Session, user: User, rates: RateResolver, today: date, months: int = 3
) -> Decimal | None:
    """Average income (base currency) of the last `months` full months that had income.

    Falls back to the current month when there is no history yet. None if no income at all.
    """
    start = month_start(today, months)
    rows = db.execute(
        select(
            Transaction.occurred_on, Transaction.amount, Transaction.currency, Transaction.fx_rate
        ).where(
            Transaction.user_id == user.id,
            Transaction.kind == TransactionKind.INCOME,
            Transaction.occurred_on >= start,
            Transaction.occurred_on <= today,
        )
    ).all()

    by_month: dict[date, Decimal] = {}
    for occurred_on, amount, currency, fx_rate in rows:
        value = rates.to_base(amount, currency, occurred_on, fx_rate)
        if value is not None:
            key = month_start(occurred_on)
            by_month[key] = by_month.get(key, Decimal(0)) + value

    current = month_start(today)
    history = [v for k, v in by_month.items() if k != current and v > 0]
    if history:
        return sum(history, Decimal(0)) / len(history)
    return by_month.get(current)
