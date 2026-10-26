from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import Dec, LongName, NonZeroAmount, PositiveAmount


class GoalIn(BaseModel):
    name: LongName
    target_amount: PositiveAmount
    target_date: date | None = None
    priority: int = Field(default=0, ge=0, le=99)
    notes: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class AllocationIn(BaseModel):
    account_id: int
    amount: NonZeroAmount  # in the platform's currency; negative releases money back
    allocated_on: date
    notes: str | None = Field(default=None, max_length=500)


class AllocationOut(BaseModel):
    id: int
    goal_id: int
    account_id: int
    account_name: str
    currency: str
    amount: Dec
    allocated_on: date
    notes: str | None
