from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.models import CategoryKind, ExpenseLevel
from app.schemas.common import Name


class CategoryCreate(BaseModel):
    name: Name
    kind: CategoryKind
    level: ExpenseLevel | None = None
    color: str | None = None

    @model_validator(mode="after")
    def level_matches_kind(self) -> Self:
        if self.kind == CategoryKind.EXPENSE and self.level is None:
            raise ValueError("Un gasto debe ser 'essential' o 'lifestyle'")
        if self.kind == CategoryKind.INCOME and self.level is not None:
            raise ValueError("Una categoría de ingreso no lleva nivel")
        return self


class CategoryUpdate(BaseModel):
    name: Name | None = None
    level: ExpenseLevel | None = None
    color: str | None = None
    is_active: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: CategoryKind
    level: ExpenseLevel | None
    color: str | None
    is_active: bool
