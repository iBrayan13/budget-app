"""Savings goals are virtual envelopes: the money stays in its platform, allocations reserve it."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, GoalAllocation, GoalKind, SavingsGoal, User
from app.services.balances import account_movements
from app.services.budget import month_start
from app.services.fx import RateResolver

Z = Decimal(0)
EMERGENCY_NAME = "Fondo de emergencia"


@dataclass
class GoalState:
    goal: SavingsGoal
    current: Decimal = Z  # reserved today, in base currency
    pace: Decimal = Z  # average monthly contributions over the last 3 months


def ensure_emergency_goal(db: Session, user: User) -> SavingsGoal:
    goal = db.scalar(
        select(SavingsGoal).where(
            SavingsGoal.user_id == user.id, SavingsGoal.kind == GoalKind.EMERGENCY_FUND
        )
    )
    if goal is None:
        goal = SavingsGoal(user_id=user.id, kind=GoalKind.EMERGENCY_FUND, name=EMERGENCY_NAME)
        db.add(goal)
        db.commit()
    return goal


def account_balance(db: Session, user: User, account: Account) -> Decimal:
    return account.initial_balance + account_movements(db, user.id).get(account.id, Z)


def reserved_on_account(db: Session, account_id: int, goal_id: int | None = None) -> Decimal:
    q = select(func.sum(GoalAllocation.amount)).where(GoalAllocation.account_id == account_id)
    if goal_id is not None:
        q = q.where(GoalAllocation.goal_id == goal_id)
    return db.scalar(q) or Z


def goal_states(
    db: Session, user: User, rates: RateResolver, today: date
) -> tuple[list[GoalState], Decimal]:
    """Active goals with their balance, plus everything reserved across all goals (base)."""
    states = {
        g.id: GoalState(g)
        for g in db.scalars(
            select(SavingsGoal).where(SavingsGoal.user_id == user.id, SavingsGoal.is_active)
        )
    }
    since = month_start(today, 2)  # last 3 months, current one included
    reserved = Z
    rows = db.execute(
        select(GoalAllocation, Account.currency)
        .join(Account, Account.id == GoalAllocation.account_id)
        .join(SavingsGoal, SavingsGoal.id == GoalAllocation.goal_id)
        .where(SavingsGoal.user_id == user.id)
    ).all()
    for alloc, currency in rows:
        rate = rates.rate(currency, today)
        if rate is None:
            continue
        value = alloc.amount / rate
        reserved += value
        state = states.get(alloc.goal_id)
        if state is None:
            continue
        state.current += value
        if value > 0 and alloc.allocated_on >= since:
            state.pace += value / 3
    return list(states.values()), reserved


def accounts_total(db: Session, user: User, rates: RateResolver, today: date) -> Decimal:
    """Balance of all active platforms in base currency (same rule as /accounts)."""
    movements = account_movements(db, user.id)
    total = Z
    for a in db.scalars(select(Account).where(Account.user_id == user.id, Account.is_active)):
        rate = rates.rate(a.currency, today)
        if rate is not None:
            total += (a.initial_balance + movements.get(a.id, Z)) / rate
    return total
