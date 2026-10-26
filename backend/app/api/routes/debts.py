from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_owned
from app.models import (
    Account,
    Debt,
    DebtKind,
    RecurringExpense,
    Transaction,
    TransactionKind,
    Transfer,
    User,
)
from app.schemas.debts import DebtIn, DebtOut, DebtPaymentIn, DebtsSummary
from app.services.budget import average_monthly_income
from app.services.debts import MAX_DEBT_RATIO, debt_category, debt_status
from app.services.fx import RateResolver, money
from app.services.obligations import reset_pending, sync_obligations
from app.services.recurrence import InvalidRule, normalize_rule, nth_occurrence

router = APIRouter(prefix="/debts", tags=["debts"])

PCT = Decimal("0.01")


def _debt_out(db: DbSession, debt: Debt, rates: RateResolver, today: date) -> DebtOut:
    s = debt_status(db, debt, rates, today)
    schedule = (
        db.get(RecurringExpense, debt.recurring_expense_id) if debt.recurring_expense_id else None
    )
    rate = rates.rate(debt.currency, today)
    progress = (1 - s.balance / debt.original_amount) * 100 if debt.original_amount else 0
    return DebtOut(
        id=debt.id,
        name=debt.name,
        kind=debt.kind,
        creditor=debt.creditor,
        currency=debt.currency,
        original_amount=debt.original_amount,
        interest_rate_annual=debt.interest_rate_annual,
        installment_amount=debt.installment_amount,
        installments_total=debt.installments_total,
        start_date=debt.start_date,
        account_id=debt.account_id,
        recurring_expense_id=debt.recurring_expense_id,
        schedule_rrule=schedule.rrule if schedule else None,
        schedule_first_due_date=schedule.start_date if schedule else None,
        schedule_account_id=schedule.account_id if schedule else None,
        is_active=debt.is_active,
        notes=debt.notes,
        paid_total=money(s.paid_total),
        payments_count=s.payments_count,
        balance=money(s.balance),
        balance_base=money(s.balance / rate) if rate else None,
        progress_pct=Decimal(max(min(progress, 100), 0)).quantize(PCT),
        remaining_installments=s.remaining_installments,
        monthly_payment=money(s.monthly_payment),
        monthly_payment_base=money(s.monthly_payment / rate)
        if s.monthly_payment is not None and rate
        else None,
        total_interest=money(s.total_interest),
        next_due_date=s.next_due_date,
        next_due_amount=s.next_due_amount,
        end_date=schedule.end_date if schedule else None,
    )


def _apply(db: DbSession, user: User, debt: Debt, body: DebtIn) -> None:
    """Copies the body into the debt and keeps its linked installment schedule in sync."""
    if body.account_id is not None:
        get_owned(db, Account, body.account_id, user, "Plataforma de la tarjeta")
    sched = body.schedule
    rule = None
    if sched is not None:
        if sched.account_id is not None:
            get_owned(db, Account, sched.account_id, user, "Plataforma de pago")
        try:
            rule = normalize_rule(sched.rrule)
            end = (
                nth_occurrence(rule, sched.first_due_date, sched.installments_total)
                if sched.installments_total
                else None
            )
        except InvalidRule as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    for field in (
        "name",
        "kind",
        "creditor",
        "currency",
        "original_amount",
        "interest_rate_annual",
        "start_date",
        "account_id",
        "is_active",
        "notes",
    ):
        setattr(debt, field, getattr(body, field))
    debt.installment_amount = sched.installment_amount if sched else None
    debt.installments_total = sched.installments_total if sched else None

    expense = (
        db.get(RecurringExpense, debt.recurring_expense_id) if debt.recurring_expense_id else None
    )
    if sched is None:
        if expense is not None:
            debt.recurring_expense_id = None
            db.flush()
            db.delete(expense)
        return

    # Resolve the category first: its query may autoflush, so nothing half-built can be pending.
    category_id = debt_category(db, user).id
    values = {
        "name": f"Cuota {body.name}",
        "category_id": category_id,
        "account_id": sched.account_id,
        "amount": sched.installment_amount,
        "currency": body.currency,
        "rrule": rule,
        "start_date": sched.first_due_date,
        "end_date": end,
        "is_active": body.is_active,
    }
    if expense is None:
        expense = RecurringExpense(user_id=user.id, **values)
        db.add(expense)
    else:
        for field, value in values.items():
            setattr(expense, field, value)
    db.flush()
    reset_pending(db, expense)
    debt.recurring_expense_id = expense.id


@router.get("", response_model=DebtsSummary)
def list_debts(db: DbSession, user: CurrentUser, include_inactive: bool = False):
    today = date.today()
    sync_obligations(db, user, today + timedelta(days=62))
    q = select(Debt).where(Debt.user_id == user.id).order_by(Debt.is_active.desc(), Debt.name)
    if not include_inactive:
        q = q.where(Debt.is_active)
    rates = RateResolver(db, user)
    items = [_debt_out(db, d, rates, today) for d in db.scalars(q)]

    active = [d for d in items if d.is_active]
    total = sum((d.balance_base for d in active if d.balance_base is not None), Decimal(0))
    monthly = sum(
        (d.monthly_payment_base for d in active if d.monthly_payment_base is not None), Decimal(0)
    )
    income = average_monthly_income(db, user, rates, today)
    ratio = (monthly / income * 100).quantize(PCT) if income else None
    capacity = money(income * MAX_DEBT_RATIO - monthly) if income else None
    return DebtsSummary(
        base_currency=user.base_currency,
        total_balance_base=money(total),
        monthly_payments_base=money(monthly),
        avg_monthly_income_base=money(income),
        debt_ratio_pct=ratio,
        max_ratio_pct=(MAX_DEBT_RATIO * 100).quantize(PCT),
        capacity_base=capacity,
        items=items,
    )


@router.post("", response_model=DebtOut, status_code=status.HTTP_201_CREATED)
def create_debt(body: DebtIn, db: DbSession, user: CurrentUser):
    debt = Debt(user_id=user.id)
    _apply(db, user, debt, body)
    db.add(debt)
    db.commit()
    return _debt_out(db, debt, RateResolver(db, user), date.today())


@router.put("/{debt_id}", response_model=DebtOut)
def replace_debt(debt_id: int, body: DebtIn, db: DbSession, user: CurrentUser):
    debt = get_owned(db, Debt, debt_id, user, "Deuda")
    _apply(db, user, debt, body)
    db.commit()
    return _debt_out(db, debt, RateResolver(db, user), date.today())


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_debt(debt_id: int, db: DbSession, user: CurrentUser):
    """Deletes the debt and its installment schedule. Payments stay as movements."""
    debt = get_owned(db, Debt, debt_id, user, "Deuda")
    expense = (
        db.get(RecurringExpense, debt.recurring_expense_id) if debt.recurring_expense_id else None
    )
    db.delete(debt)
    if expense is not None:
        db.flush()
        db.delete(expense)
    db.commit()


@router.post("/{debt_id}/payments", response_model=DebtOut, status_code=status.HTTP_201_CREATED)
def add_payment(debt_id: int, body: DebtPaymentIn, db: DbSession, user: CurrentUser):
    """Extra payment outside the schedule (abono)."""
    debt = get_owned(db, Debt, debt_id, user, "Deuda")
    account = get_owned(db, Account, body.account_id, user, "Plataforma")

    if debt.kind == DebtKind.CREDIT_CARD:
        card = db.get(Account, debt.account_id)
        if card.id == account.id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Paga desde otra plataforma")
        amount_in = body.amount_in or (body.amount if account.currency == card.currency else None)
        if amount_in is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Indica cuánto llegó a la tarjeta en {card.currency}",
            )
        db.add(
            Transfer(
                user_id=user.id,
                from_account_id=account.id,
                to_account_id=card.id,
                amount_out=body.amount,
                amount_in=amount_in,
                occurred_on=body.occurred_on,
                notes=body.description or f"Pago {debt.name}",
            )
        )
    else:
        db.add(
            Transaction(
                user_id=user.id,
                account_id=account.id,
                kind=TransactionKind.EXPENSE,
                amount=body.amount,
                currency=account.currency,
                fx_rate=body.fx_rate,
                occurred_on=body.occurred_on,
                category_id=debt_category(db, user).id,
                description=body.description or f"Abono {debt.name}",
                debt_id=debt.id,
            )
        )
    db.commit()
    return _debt_out(db, debt, RateResolver(db, user), date.today())
