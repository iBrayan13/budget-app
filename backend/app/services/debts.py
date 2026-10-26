from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    Category,
    CategoryKind,
    Debt,
    DebtKind,
    ExpenseLevel,
    Obligation,
    ObligationStatus,
    RecurringExpense,
    Transaction,
    Transfer,
    User,
)
from app.services.balances import account_movements
from app.services.fx import RateResolver
from app.services.recurrence import per_month, per_year

DEBT_CATEGORY = "Pago de deudas"
# Common guideline: debt installments should not exceed ~30 % of income.
MAX_DEBT_RATIO = Decimal("0.30")


def debt_category(db: Session, user: User) -> Category:
    category = db.scalar(
        select(Category).where(
            Category.user_id == user.id,
            Category.kind == CategoryKind.EXPENSE,
            Category.name == DEBT_CATEGORY,
        )
    )
    if category is None:
        category = Category(
            user_id=user.id,
            name=DEBT_CATEGORY,
            kind=CategoryKind.EXPENSE,
            level=ExpenseLevel.ESSENTIAL,
        )
        db.add(category)
        db.flush()
    return category


@dataclass
class DebtStatus:
    paid_total: Decimal  # in the debt currency
    payments_count: int
    balance: Decimal  # estimated outstanding principal, debt currency
    remaining_installments: int | None
    monthly_payment: Decimal | None  # monthly equivalent of the installment, debt currency
    total_interest: Decimal | None
    next_due_date: date | None
    next_due_amount: Decimal | None


def _convert(amount: Decimal, frm: str, to: str, on: date, rates: RateResolver, fx: Decimal | None):
    if frm == to:
        return amount
    base = rates.to_base(amount, frm, on, fx)
    rate_to = rates.rate(to, on)
    return None if base is None or rate_to is None else base * rate_to


def amortized_balance(
    principal: Decimal,
    annual_pct: Decimal,
    periods_per_year: Decimal,
    installment: Decimal,
    payments: int,
) -> Decimal:
    """Outstanding principal of a fixed-installment (French) loan after `payments` installments."""
    r = annual_pct / 100 / periods_per_year
    if r == 0:
        return max(principal - installment * payments, Decimal(0))
    growth = (1 + r) ** payments
    return max(principal * growth - installment * (growth - 1) / r, Decimal(0))


def debt_status(db: Session, debt: Debt, rates: RateResolver, today: date) -> DebtStatus:
    payments = db.execute(
        select(
            Transaction.amount, Transaction.currency, Transaction.occurred_on, Transaction.fx_rate
        ).where(Transaction.debt_id == debt.id)
    ).all()
    paid_total = Decimal(0)
    for amount, currency, occurred_on, fx in payments:
        converted = _convert(amount, currency, debt.currency, occurred_on, rates, fx)
        if converted is not None:
            paid_total += converted

    schedule = (
        db.get(RecurringExpense, debt.recurring_expense_id) if debt.recurring_expense_id else None
    )
    monthly = periods = None
    if schedule is not None:
        monthly = schedule.amount * per_month(schedule.rrule, schedule.start_date)
        periods = per_year(schedule.rrule, schedule.start_date)

    count = len(payments)
    if debt.kind == DebtKind.CREDIT_CARD and debt.account_id:
        # The card account carries the debt as a negative balance; paying it is a transfer in.
        account = db.get(Account, debt.account_id)
        movement = account_movements(db, debt.user_id).get(account.id, Decimal(0))
        balance = max(-(account.initial_balance + movement), Decimal(0))
        transfers_in = db.scalars(
            select(Transfer.amount_in).where(Transfer.to_account_id == account.id)
        ).all()
        paid_total += sum(transfers_in, Decimal(0))
        count += len(transfers_in)
    elif debt.interest_rate_annual and debt.installment_amount and periods:
        balance = amortized_balance(
            debt.original_amount, debt.interest_rate_annual, periods, debt.installment_amount, count
        )
    else:
        balance = max(debt.original_amount - paid_total, Decimal(0))

    remaining = (
        max(debt.installments_total - count, 0) if debt.installments_total is not None else None
    )
    total_interest = (
        debt.installment_amount * debt.installments_total - debt.original_amount
        if debt.installment_amount and debt.installments_total
        else None
    )

    next_due = None
    if schedule is not None:
        next_due = db.execute(
            select(Obligation.due_date, Obligation.expected_amount)
            .where(
                Obligation.recurring_expense_id == schedule.id,
                Obligation.status == ObligationStatus.PENDING,
            )
            .order_by(Obligation.due_date)
            .limit(1)
        ).first()

    return DebtStatus(
        paid_total=paid_total,
        payments_count=count,
        balance=balance,
        remaining_installments=remaining,
        monthly_payment=monthly,
        total_interest=total_interest,
        next_due_date=next_due[0] if next_due else None,
        next_due_amount=next_due[1] if next_due else None,
    )
