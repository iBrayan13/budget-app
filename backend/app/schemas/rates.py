from datetime import date

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Currency, Dec, Rate


class RateIn(BaseModel):
    currency: Currency
    rate_date: date
    rate: Rate


class RateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    currency: str
    rate_date: date
    rate: Dec
