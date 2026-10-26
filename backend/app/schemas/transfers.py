from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import Dec, PositiveAmount, Rate


class TransferIn(BaseModel):
    from_account_id: int
    to_account_id: int
    amount_out: PositiveAmount  # everything that left the source, fees included
    amount_in: PositiveAmount  # what actually arrived
    fee_amount: Decimal = Field(default=Decimal(0), ge=0, max_digits=20, decimal_places=8)
    ref_rate_out: Rate | None = None
    ref_rate_in: Rate | None = None
    occurred_on: date
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.from_account_id == self.to_account_id:
            raise ValueError("Origen y destino deben ser distintos")
        if self.fee_amount > self.amount_out:
            raise ValueError("La comisión no puede superar el monto enviado")
        return self


class RouteStepIn(TransferIn):
    occurred_on: date | None = None  # defaults to the route date


class RouteIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    started_on: date
    notes: str | None = Field(default=None, max_length=500)
    steps: list[RouteStepIn] = Field(min_length=1, max_length=20)


class CostOut(BaseModel):
    value_out: Dec | None
    value_in: Dec | None
    cost: Dec | None
    fee: Dec | None
    spread: Dec | None
    cost_pct: Dec | None


class TransferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    route_id: int | None
    step: int | None
    from_account_id: int
    to_account_id: int
    from_currency: str
    to_currency: str
    amount_out: Dec
    amount_in: Dec
    fee_amount: Dec
    ref_rate_out: Dec | None
    ref_rate_in: Dec | None
    occurred_on: date
    notes: str | None
    cost: CostOut


class RouteOut(BaseModel):
    id: int
    name: str | None
    started_on: date
    notes: str | None
    steps: list[TransferOut]
    cost: CostOut  # value_out of first step, value_in of last, cost = sum of steps


class PairSummary(BaseModel):
    from_account_id: int
    to_account_id: int
    count: int
    volume: Dec
    cost: Dec
    cost_pct: Dec | None


class P2PSummary(BaseModel):
    base_currency: str
    count: int
    volume: Dec  # money that entered P2P (first step of each route), in base currency
    cost: Dec
    fees: Dec
    spread: Dec
    cost_pct: Dec | None
    missing_rates: int  # transfers excluded because a reference rate is missing
    by_pair: list[PairSummary]
