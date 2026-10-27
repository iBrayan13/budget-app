"""Monthly picture: income, what it costs to survive and to live well, and the emergency fund."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Category,
    ExpenseLevel,
    GoalKind,
    Obligation,
    ObligationStatus,
    RecurringExpense,
    Transaction,
    TransactionKind,
    Transfer,
    User,
)
from app.schemas.plan import GoalOut, PlanOut, ScenarioOut
from app.services.budget import month_start
from app.services.fx import RateResolver, money
from app.services.goals import GoalState, accounts_total, ensure_emergency_goal, goal_states
from app.services.obligations import sync_obligations
from app.services.p2p import transfer_cost
from app.services.recurrence import per_month

Z = Decimal(0)
WINDOW = 3  # averages use the 3 full months before the chosen month
MONTH_DAYS = Decimal("30.44")


def month_bounds(month: date) -> tuple[date, date]:
    start = month.replace(day=1)
    return start, start + relativedelta(months=1) - timedelta(days=1)


@dataclass
class Flows:
    income: Decimal = Z
    variable_essential: Decimal = Z
    variable_lifestyle: Decimal = Z
    obligations_paid: Decimal = Z  # fixed-expense payments already made (in the month)
    p2p: Decimal = Z


def flows(db: Session, user: User, rates: RateResolver, start: date, end: date) -> Flows:
    f = Flows()
    rows = db.execute(
        select(
            Transaction.kind,
            Transaction.occurred_on,
            Transaction.amount,
            Transaction.currency,
            Transaction.fx_rate,
            Transaction.obligation_id,
            Category.level,
        )
        .select_from(Transaction)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.user_id == user.id,
            Transaction.kind != TransactionKind.ADJUSTMENT,
            Transaction.occurred_on.between(start, end),
        )
    ).all()
    for kind, on, amount, currency, fx, obligation_id, level in rows:
        value = rates.to_base(amount, currency, on, fx)
        if value is None:
            continue
        if kind == TransactionKind.INCOME:
            f.income += value
        elif obligation_id is not None:
            f.obligations_paid += value
        elif level == ExpenseLevel.LIFESTYLE:
            f.variable_lifestyle += value
        else:
            f.variable_essential += value

    transfers = db.scalars(
        select(Transfer).where(
            Transfer.user_id == user.id, Transfer.occurred_on.between(start, end)
        )
    ).unique()
    for t in transfers:
        cost = transfer_cost(t, rates).cost
        if cost is not None:
            f.p2p += cost
    return f


def pending_due(db: Session, user: User, rates: RateResolver, start: date, end: date) -> Decimal:
    rows = db.execute(
        select(Obligation.due_date, Obligation.expected_amount, Obligation.currency)
        .select_from(Obligation)
        .join(RecurringExpense, RecurringExpense.id == Obligation.recurring_expense_id)
        .where(
            RecurringExpense.user_id == user.id,
            Obligation.status == ObligationStatus.PENDING,
            Obligation.due_date.between(start, end),
        )
    ).all()
    total = Z
    for on, amount, currency in rows:
        value = rates.to_base(amount, currency, on)
        if value is not None:
            total += value
    return total


def recurring_monthly(
    db: Session, user: User, rates: RateResolver, today: date
) -> tuple[Decimal, Decimal]:
    """Monthly equivalent of active fixed expenses: (essential, lifestyle)."""
    rows = db.execute(
        select(RecurringExpense, Category.level)
        .select_from(RecurringExpense)
        .join(Category, Category.id == RecurringExpense.category_id)
        .where(RecurringExpense.user_id == user.id, RecurringExpense.is_active)
    ).all()
    essential = lifestyle = Z
    for expense, level in rows:
        if expense.end_date and expense.end_date < today:
            continue
        rate = rates.rate(expense.currency, today)
        if rate is None:
            continue
        monthly = expense.amount * per_month(expense.rrule, expense.start_date) / rate
        if level == ExpenseLevel.LIFESTYLE:
            lifestyle += monthly
        else:
            essential += monthly
    return essential, lifestyle


@dataclass
class Base:
    """Typical month, in base currency: averages of the window plus fixed expenses."""

    income: Decimal
    fixed_essential: Decimal
    variable_essential: Decimal
    p2p: Decimal
    fixed_lifestyle: Decimal
    variable_lifestyle: Decimal

    @property
    def survive(self) -> Decimal:
        return self.fixed_essential + self.variable_essential + self.p2p

    @property
    def lifestyle(self) -> Decimal:
        return self.fixed_lifestyle + self.variable_lifestyle

    @property
    def live(self) -> Decimal:
        return self.survive + self.lifestyle


def average_base(db: Session, user: User, rates: RateResolver, month: date, today: date) -> Base:
    # The last WINDOW months, the chosen one included, so new income shows up right away.
    win_start = month_start(month, WINDOW - 1)
    win_end = month_bounds(month)[1]
    f = flows(db, user, rates, win_start, win_end)
    fixed_e, fixed_l = recurring_monthly(db, user, rates, today)
    n = Decimal(WINDOW)
    return Base(
        income=f.income / n,
        fixed_essential=fixed_e,
        variable_essential=f.variable_essential / n,
        p2p=f.p2p / n,
        fixed_lifestyle=fixed_l,
        variable_lifestyle=f.variable_lifestyle / n,
    )


@dataclass
class Context:
    today: date
    month: date
    flows: Flows
    pending: Decimal
    base: Base
    states: list[GoalState]
    reserved: Decimal
    accounts: Decimal
    emergency: GoalState
    pace: Decimal  # monthly contributions to all goals together


def _gather(db: Session, user: User, month: date, today: date) -> Context:
    rates = RateResolver(db, user)
    start, end = month_bounds(month)
    sync_obligations(db, user, end)
    ensure_emergency_goal(db, user)
    states, reserved = goal_states(db, user, rates, today)
    return Context(
        today=today,
        month=month,
        flows=flows(db, user, rates, start, end),
        pending=pending_due(db, user, rates, start, end),
        base=average_base(db, user, rates, month, today),
        states=states,
        reserved=reserved,
        accounts=accounts_total(db, user, rates, today),
        emergency=next(s for s in states if s.goal.kind == GoalKind.EMERGENCY_FUND),
        pace=sum((s.pace for s in states), Z),
    )


def _eta(today: date, missing: Decimal | None, pace: Decimal) -> date | None:
    if missing is None:
        return None
    if missing <= 0:
        return today
    if pace <= 0:
        return None
    return today + timedelta(days=round(missing / pace * MONTH_DAYS))


def _fund(user: User, c: Context) -> tuple[Decimal | None, Decimal | None]:
    """(target, missing). Target is months x cost of surviving; None until there is a cost."""
    if c.base.survive <= 0:
        return None, None
    target = c.base.survive * user.emergency_fund_months
    return target, max(target - c.emergency.current, Z)


def _share(part: Decimal, income: Decimal) -> Decimal | None:
    return money(part / income * 100) if income > 0 else None


def _goal_out(s: GoalState, target: Decimal | None, today: date) -> GoalOut:
    g = s.goal
    remaining = None if target is None else max(target - s.current, Z)
    needed = None
    if remaining and g.target_date:
        months_left = max(
            (g.target_date.year - today.year) * 12 + g.target_date.month - today.month, 1
        )
        needed = remaining / months_left
    return GoalOut(
        id=g.id,
        name=g.name,
        kind=g.kind.value,
        target_amount=money(target),
        target_date=g.target_date,
        priority=g.priority,
        is_active=g.is_active,
        notes=g.notes,
        current=money(s.current),
        progress_pct=money(s.current / target * 100) if target else None,
        remaining=money(remaining),
        monthly_needed=money(needed),
        pace=money(s.pace),
        eta=_eta(today, remaining, s.pace),
    )


def compute_plan(db: Session, user: User, month: date, today: date | None = None) -> PlanOut:
    c = _gather(db, user, month.replace(day=1), today or date.today())
    f, b = c.flows, c.base
    costs = f.variable_essential + f.variable_lifestyle + f.obligations_paid + f.p2p + c.pending
    fund_target, fund_missing = _fund(user, c)
    covered = c.emergency.current / b.survive if b.survive > 0 else None
    return PlanOut(
        month=c.month,
        base_currency=user.base_currency,
        income_month=money(f.income),
        costs_month=money(costs),
        p2p_month=money(f.p2p),
        net_month=money(f.income - costs),
        income_avg=money(b.income),
        fixed_essential=money(b.fixed_essential),
        variable_essential=money(b.variable_essential),
        p2p_avg=money(b.p2p),
        survive=money(b.survive),
        fixed_lifestyle=money(b.fixed_lifestyle),
        variable_lifestyle=money(b.variable_lifestyle),
        live=money(b.live),
        savings_capacity=money(b.income - b.live),
        pace=money(c.pace),
        accounts_total=money(c.accounts),
        reserved=money(c.reserved),
        free=money(c.accounts - c.reserved),
        emergency_months=user.emergency_fund_months,
        fund_target=money(fund_target),
        fund_current=money(c.emergency.current),
        fund_missing=money(fund_missing),
        fund_months_covered=money(covered),
        fund_eta=_eta(c.today, fund_missing, c.emergency.pace),
        rule_essential_pct=_share(b.survive, b.income),
        rule_lifestyle_pct=_share(b.lifestyle, b.income),
        rule_savings_pct=_share(b.income - b.live, b.income),
        goals=[
            _goal_out(
                s,
                fund_target if s.goal.kind == GoalKind.EMERGENCY_FUND else s.goal.target_amount,
                c.today,
            )
            for s in c.states
        ],
    )


def compute_scenario(
    db: Session, user: User, lifestyle_target: Decimal, month: date, today: date | None = None
) -> ScenarioOut:
    """What-if on the lifestyle spending: survival cost stays, fixed savings pace stays."""
    c = _gather(db, user, month.replace(day=1), today or date.today())
    b = c.base
    live_target = b.survive + lifestyle_target
    capacity = b.income - live_target
    _, missing = _fund(user, c)
    if missing is None:
        months = None
    elif missing <= 0:
        months = Z
    elif capacity > 0:
        months = missing / capacity
    else:
        months = None
    return ScenarioOut(
        income_avg=money(b.income),
        survive=money(b.survive),
        current_lifestyle=money(b.lifestyle),
        lifestyle_target=money(lifestyle_target),
        live_target=money(live_target),
        savings_capacity=money(capacity),
        fund_months=money(months),
        required_income=money(live_target + c.pace),
        max_lifestyle=money(max(b.income - b.survive - c.pace, Z)),
    )
