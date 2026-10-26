from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_owned
from app.models import ExchangeRate
from app.schemas.rates import RateIn, RateOut

router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])


@router.get("", response_model=list[RateOut])
def list_rates(db: DbSession, user: CurrentUser, currency: str | None = None, limit: int = 200):
    q = (
        select(ExchangeRate)
        .where(ExchangeRate.user_id == user.id)
        .order_by(ExchangeRate.rate_date.desc(), ExchangeRate.currency)
        .limit(min(limit, 1000))
    )
    if currency:
        q = q.where(ExchangeRate.currency == currency.upper())
    return db.scalars(q).all()


@router.put("", response_model=RateOut)
def upsert_rate(body: RateIn, db: DbSession, user: CurrentUser):
    """One rate per currency and day: saving again on the same day replaces it."""
    rate = db.scalar(
        select(ExchangeRate).where(
            ExchangeRate.user_id == user.id,
            ExchangeRate.currency == body.currency,
            ExchangeRate.rate_date == body.rate_date,
        )
    )
    if rate is None:
        rate = ExchangeRate(user_id=user.id, **body.model_dump())
        db.add(rate)
    else:
        rate.rate = body.rate
    db.commit()
    return rate


@router.delete("/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rate(rate_id: int, db: DbSession, user: CurrentUser):
    db.delete(get_owned(db, ExchangeRate, rate_id, user, "Tasa"))
    db.commit()
