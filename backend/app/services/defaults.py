"""Suggested starting data. Everything is editable afterwards."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountKind, Category, CategoryKind, ExpenseLevel, User

E, L = ExpenseLevel.ESSENTIAL, ExpenseLevel.LIFESTYLE

DEFAULT_ACCOUNTS = [
    ("Facebank", AccountKind.BANK, "USD"),
    ("Binance", AccountKind.EXCHANGE, "USDT"),
    ("Zinli", AccountKind.WALLET, "USD"),
    ("El Dorado", AccountKind.WALLET, "USDT"),
    ("Nequi", AccountKind.WALLET, "COP"),
    ("Efectivo", AccountKind.CASH, "COP"),
]

DEFAULT_EXPENSE_CATEGORIES = [
    ("Vivienda", E),
    ("Servicios públicos", E),
    ("Internet y celular", E),
    ("Mercado", E),
    ("Transporte", E),
    ("Salud", E),
    ("Seguros", E),
    ("Educación", E),
    ("Impuestos", E),
    ("Pago de deudas", E),
    ("Reparaciones y mantenimiento", E),
    ("Restaurantes y domicilios", L),
    ("Entretenimiento", L),
    ("Suscripciones", L),
    ("Ropa y calzado", L),
    ("Tecnología", L),
    ("Viajes", L),
    ("Regalos", L),
    ("Otros gastos", L),
]

DEFAULT_INCOME_CATEGORIES = [
    "Salario",
    "Honorarios / freelance",
    "Intereses y rendimientos",
    "Otros ingresos",
]


def seed_accounts(db: Session, user: User) -> int:
    """Adds the suggested platforms that do not exist yet (matched by name)."""
    existing = set(db.scalars(select(Account.name).where(Account.user_id == user.id)))
    new = [
        Account(user_id=user.id, name=name, kind=kind, currency=currency)
        for name, kind, currency in DEFAULT_ACCOUNTS
        if name not in existing
    ]
    db.add_all(new)
    db.commit()
    return len(new)


def seed_categories(db: Session, user: User) -> int:
    """Adds the suggested categories that do not exist yet (matched by name)."""
    existing = set(
        db.execute(select(Category.kind, Category.name).where(Category.user_id == user.id))
        .tuples()
        .all()
    )
    new = [
        Category(user_id=user.id, name=name, kind=CategoryKind.EXPENSE, level=level)
        for name, level in DEFAULT_EXPENSE_CATEGORIES
        if (CategoryKind.EXPENSE, name) not in existing
    ] + [
        Category(user_id=user.id, name=name, kind=CategoryKind.INCOME)
        for name in DEFAULT_INCOME_CATEGORIES
        if (CategoryKind.INCOME, name) not in existing
    ]
    db.add_all(new)
    db.commit()
    return len(new)


def seed_defaults(db: Session, user: User) -> dict[str, int]:
    return {"accounts": seed_accounts(db, user), "categories": seed_categories(db, user)}
