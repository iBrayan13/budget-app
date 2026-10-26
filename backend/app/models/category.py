from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, str_enum


class CategoryKind(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class ExpenseLevel(StrEnum):
    ESSENTIAL = "essential"  # counts toward "sobrevivir"
    LIFESTYLE = "lifestyle"  # only counts toward "vivir bien"


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "name"),
        CheckConstraint(
            "(kind = 'expense' AND level IS NOT NULL) OR (kind = 'income' AND level IS NULL)",
            name="level_only_for_expenses",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[CategoryKind] = mapped_column(str_enum(CategoryKind))
    level: Mapped[ExpenseLevel | None] = mapped_column(str_enum(ExpenseLevel))
    color: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)
