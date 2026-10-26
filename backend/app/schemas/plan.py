from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import Dec


class GoalOut(BaseModel):
    id: int
    name: str
    kind: str  # savings | emergency_fund
    target_amount: Dec | None
    target_date: date | None
    priority: int
    is_active: bool
    notes: str | None
    current: Dec
    progress_pct: Dec | None
    remaining: Dec | None
    monthly_needed: Dec | None  # to reach the target by target_date
    pace: Dec  # average monthly contributions, last 3 months
    eta: date | None  # at the current pace


class PlanOut(BaseModel):
    month: date
    base_currency: str
    # Chosen month, actual
    income_month: Dec
    costs_month: Dec  # expenses + fixed payments made + pending fixed due + P2P costs
    p2p_month: Dec
    net_month: Dec
    # Typical month: average of the 3 previous months + fixed expenses
    income_avg: Dec
    fixed_essential: Dec
    variable_essential: Dec
    p2p_avg: Dec
    survive: Dec
    fixed_lifestyle: Dec
    variable_lifestyle: Dec
    live: Dec
    savings_capacity: Dec  # income_avg - live
    pace: Dec  # monthly contributions to goals and the fund
    # Money
    accounts_total: Dec
    reserved: Dec
    free: Dec
    # Emergency fund
    emergency_months: int
    fund_target: Dec | None
    fund_current: Dec
    fund_missing: Dec | None
    fund_months_covered: Dec | None
    fund_eta: date | None
    # 50/30/20 check, percentages of average income
    rule_essential_pct: Dec | None
    rule_lifestyle_pct: Dec | None
    rule_savings_pct: Dec | None
    goals: list[GoalOut]


class ScenarioIn(BaseModel):
    lifestyle_target: Decimal = Field(ge=0, max_digits=20, decimal_places=8)


class ScenarioOut(BaseModel):
    income_avg: Dec
    survive: Dec
    current_lifestyle: Dec
    lifestyle_target: Dec
    live_target: Dec
    savings_capacity: Dec
    fund_months: Dec | None  # months to complete the fund with that capacity
    required_income: Dec  # income needed to live at the target and keep the savings pace
    max_lifestyle: Dec  # lifestyle spending that still fits with the current savings pace
