from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_owned
from app.models import Account, GoalAllocation, GoalKind, SavingsGoal
from app.schemas.goals import AllocationIn, AllocationOut, GoalIn
from app.services.goals import account_balance, reserved_on_account

router = APIRouter(tags=["goals"])

Z = Decimal(0)
EMERGENCY_LOCKED = "El fondo de emergencia se calcula solo: cambia sus meses en Metas"


def _allocation_out(a: GoalAllocation, account: Account) -> AllocationOut:
    return AllocationOut(
        id=a.id,
        goal_id=a.goal_id,
        account_id=a.account_id,
        account_name=account.name,
        currency=account.currency,
        amount=a.amount,
        allocated_on=a.allocated_on,
        notes=a.notes,
    )


@router.post("/goals", status_code=status.HTTP_201_CREATED)
def create_goal(body: GoalIn, db: DbSession, user: CurrentUser) -> dict[str, int]:
    goal = SavingsGoal(user_id=user.id, kind=GoalKind.SAVINGS, **body.model_dump())
    db.add(goal)
    db.commit()
    return {"id": goal.id}


@router.put("/goals/{goal_id}")
def update_goal(goal_id: int, body: GoalIn, db: DbSession, user: CurrentUser) -> dict[str, int]:
    goal = get_owned(db, SavingsGoal, goal_id, user, "Meta")
    if goal.kind == GoalKind.EMERGENCY_FUND:
        raise HTTPException(status.HTTP_409_CONFLICT, EMERGENCY_LOCKED)
    for field, value in body.model_dump().items():
        setattr(goal, field, value)
    db.commit()
    return {"id": goal.id}


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, db: DbSession, user: CurrentUser) -> None:
    """Deleting a goal frees its money; the platforms themselves are not touched."""
    goal = get_owned(db, SavingsGoal, goal_id, user, "Meta")
    if goal.kind == GoalKind.EMERGENCY_FUND:
        raise HTTPException(status.HTTP_409_CONFLICT, EMERGENCY_LOCKED)
    db.delete(goal)
    db.commit()


@router.get("/goals/{goal_id}/allocations", response_model=list[AllocationOut])
def list_allocations(goal_id: int, db: DbSession, user: CurrentUser):
    goal = get_owned(db, SavingsGoal, goal_id, user, "Meta")
    rows = db.execute(
        select(GoalAllocation, Account)
        .join(Account, Account.id == GoalAllocation.account_id)
        .where(GoalAllocation.goal_id == goal.id)
        .order_by(GoalAllocation.allocated_on.desc(), GoalAllocation.id.desc())
    ).all()
    return [_allocation_out(a, acc) for a, acc in rows]


@router.post(
    "/goals/{goal_id}/allocations",
    response_model=AllocationOut,
    status_code=status.HTTP_201_CREATED,
)
def add_allocation(goal_id: int, body: AllocationIn, db: DbSession, user: CurrentUser):
    goal = get_owned(db, SavingsGoal, goal_id, user, "Meta")
    account = get_owned(db, Account, body.account_id, user, "Plataforma")
    if not account.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La plataforma está archivada")

    if body.amount > 0:
        free = account_balance(db, user, account) - reserved_on_account(db, account.id)
        if body.amount > free:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Solo tienes {free:.2f} {account.currency} libres en {account.name}",
            )
    elif reserved_on_account(db, account.id, goal.id) + body.amount < 0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Esta meta no tiene tanto apartado en {account.name}",
        )

    alloc = GoalAllocation(goal_id=goal.id, **body.model_dump())
    db.add(alloc)
    db.commit()
    return _allocation_out(alloc, account)


@router.delete("/goal-allocations/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_allocation(allocation_id: int, db: DbSession, user: CurrentUser) -> None:
    alloc = db.get(GoalAllocation, allocation_id)
    goal = db.get(SavingsGoal, alloc.goal_id) if alloc else None
    if goal is None or goal.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aporte no encontrado")
    if alloc.amount < 0:
        # Undoing a release re-reserves that money: it must still fit in the platform.
        account = db.get(Account, alloc.account_id)
        reserved_after = reserved_on_account(db, account.id) - alloc.amount
        if reserved_after > account_balance(db, user, account):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"No alcanza el saldo de {account.name} para volver a apartar ese dinero",
            )
    db.delete(alloc)
    db.commit()
