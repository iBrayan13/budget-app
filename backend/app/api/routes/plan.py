from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.schemas.plan import PlanOut, ScenarioIn, ScenarioOut
from app.services.plan import compute_plan, compute_scenario

router = APIRouter(prefix="/plan", tags=["plan"])


def _month(value: date | None) -> date:
    return (value or date.today()).replace(day=1)


@router.get("", response_model=PlanOut)
def get_plan(db: DbSession, user: CurrentUser, month: date | None = Query(default=None)):
    return compute_plan(db, user, _month(month))


@router.post("/scenario", response_model=ScenarioOut)
def scenario(
    body: ScenarioIn,
    db: DbSession,
    user: CurrentUser,
    month: date | None = Query(default=None),
):
    return compute_scenario(db, user, body.lifestyle_target, _month(month))


class SettingsIn(BaseModel):
    emergency_fund_months: int = Field(ge=1, le=24)


@router.patch("/settings")
def update_settings(body: SettingsIn, db: DbSession, user: CurrentUser) -> dict[str, int]:
    user.emergency_fund_months = body.emergency_fund_months
    db.commit()
    return {"emergency_fund_months": user.emergency_fund_months}
