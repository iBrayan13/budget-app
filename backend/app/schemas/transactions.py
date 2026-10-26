from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import TransactionKind
from app.schemas.common import Dec, NonZeroAmount, Rate


class TransactionIn(BaseModel):
    account_id: int
    kind: TransactionKind
    amount: NonZeroAmount  # positive; adjustments may be negative
    occurred_on: date
    category_id: int | None = None
    description: str | None = Field(default=None, max_length=500)
    fx_rate: Rate | None = None

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.kind != TransactionKind.ADJUSTMENT and self.amount < 0:
            raise ValueError("El monto debe ser positivo")
        if self.kind == TransactionKind.EXPENSE and self.category_id is None:
            raise ValueError("Un gasto necesita categoría")
        if self.kind == TransactionKind.ADJUSTMENT and self.category_id is not None:
            raise ValueError("Un ajuste no lleva categoría")
        return self


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    kind: TransactionKind
    amount: Dec
    currency: str
    occurred_on: date
    category_id: int | None
    description: str | None
    fx_rate: Dec | None
    amount_base: Dec | None = None
