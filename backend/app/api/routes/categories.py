from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_owned
from app.models import Category, CategoryKind, RecurringExpense, Transaction
from app.schemas.categories import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])


def _ensure_unique(db, user_id: int, kind: CategoryKind, name: str, exclude_id: int | None = None):
    q = select(Category.id).where(
        Category.user_id == user_id, Category.kind == kind, Category.name == name
    )
    if exclude_id is not None:
        q = q.where(Category.id != exclude_id)
    if db.scalar(q) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe la categoría {name}")


@router.get("", response_model=list[CategoryOut])
def list_categories(db: DbSession, user: CurrentUser, include_inactive: bool = False):
    q = (
        select(Category)
        .where(Category.user_id == user.id)
        .order_by(Category.kind, Category.level, Category.name)
    )
    if not include_inactive:
        q = q.where(Category.is_active)
    return db.scalars(q).all()


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryCreate, db: DbSession, user: CurrentUser):
    _ensure_unique(db, user.id, body.kind, body.name)
    category = Category(user_id=user.id, **body.model_dump())
    db.add(category)
    db.commit()
    return category


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, body: CategoryUpdate, db: DbSession, user: CurrentUser):
    category = get_owned(db, Category, category_id, user, "Categoría")
    changes = body.model_dump(exclude_unset=True)
    if "level" in changes and (category.kind == CategoryKind.EXPENSE) != (
        changes["level"] is not None
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Solo los gastos tienen nivel, y es obligatorio para ellos",
        )
    if "name" in changes:
        _ensure_unique(db, user.id, category.kind, changes["name"], exclude_id=category.id)
    for field, value in changes.items():
        setattr(category, field, value)
    db.commit()
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: DbSession, user: CurrentUser):
    category = get_owned(db, Category, category_id, user, "Categoría")
    used = db.scalar(
        select(Transaction.id).where(Transaction.category_id == category.id).limit(1)
    ) or db.scalar(
        select(RecurringExpense.id).where(RecurringExpense.category_id == category.id).limit(1)
    )
    if used:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "La categoría está en uso; desactívala en lugar de borrarla"
        )
    db.delete(category)
    db.commit()
