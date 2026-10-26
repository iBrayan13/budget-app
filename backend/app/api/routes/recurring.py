from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, get_owned
from app.models import (
    Account,
    Category,
    CategoryKind,
    Debt,
    ExpenseLevel,
    Obligation,
    ObligationStatus,
    RecurringExpense,
    Transaction,
    TransactionKind,
    User,
)
from app.schemas.recurring import (
    ObligationOut,
    PayObligationIn,
    RecurringExpenseIn,
    RecurringExpenseOut,
    RecurringSummary,
    SchedulePreviewIn,
    SchedulePreviewOut,
)
from app.services.fx import RateResolver, money
from app.services.obligations import reset_pending, sync_obligations
from app.services.recurrence import (
    InvalidRule,
    next_occurrence,
    normalize_rule,
    occurrences,
    per_month,
)

router = APIRouter(tags=["recurring"])


def _rule_or_422(rule: str) -> str:
    try:
        return normalize_rule(rule)
    except InvalidRule as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


def _check_refs(db: DbSession, user: User, category_id: int, account_id: int | None) -> Category:
    category = get_owned(db, Category, category_id, user, "Categoría")
    if category.kind != CategoryKind.EXPENSE:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Un gasto fijo necesita una categoría de gasto"
        )
    if account_id is not None:
        get_owned(db, Account, account_id, user, "Plataforma")
    return category


def _debt_ids(db: DbSession, expense_ids: list[int]) -> dict[int, int]:
    if not expense_ids:
        return {}
    rows = db.execute(
        select(Debt.recurring_expense_id, Debt.id).where(Debt.recurring_expense_id.in_(expense_ids))
    ).all()
    return dict(rows)


def recurring_out(
    e: RecurringExpense,
    level: ExpenseLevel | None,
    debt_id: int | None,
    rates: RateResolver,
    today: date,
) -> RecurringExpenseOut:
    factor = per_month(e.rrule, e.start_date)
    monthly = e.amount * factor
    rate = rates.rate(e.currency, today)
    return RecurringExpenseOut(
        id=e.id,
        name=e.name,
        category_id=e.category_id,
        level=level,
        account_id=e.account_id,
        amount=e.amount,
        currency=e.currency,
        rrule=e.rrule,
        start_date=e.start_date,
        end_date=e.end_date,
        is_active=e.is_active,
        notes=e.notes,
        debt_id=debt_id,
        per_month=factor.quantize(Decimal("0.0001")),
        monthly_amount=money(monthly),
        monthly_amount_base=money(monthly / rate) if rate else None,
        next_due_date=next_occurrence(e.rrule, e.start_date, today, e.end_date)
        if e.is_active
        else None,
    )


# --- Fixed expenses ---------------------------------------------------------------------------


@router.get("/recurring-expenses", response_model=RecurringSummary)
def list_recurring(db: DbSession, user: CurrentUser, include_inactive: bool = False):
    q = (
        select(RecurringExpense, Category.level)
        .join(Category, Category.id == RecurringExpense.category_id)
        .where(RecurringExpense.user_id == user.id)
        .order_by(RecurringExpense.name)
    )
    if not include_inactive:
        q = q.where(RecurringExpense.is_active)
    rows = db.execute(q).all()
    debts = _debt_ids(db, [e.id for e, _ in rows])
    rates = RateResolver(db, user)
    today = date.today()
    items = [recurring_out(e, level, debts.get(e.id), rates, today) for e, level in rows]

    totals = {ExpenseLevel.ESSENTIAL: Decimal(0), ExpenseLevel.LIFESTYLE: Decimal(0)}
    without_rate = []
    for item in items:
        if not item.is_active or (item.end_date and item.end_date < today):
            continue
        if item.monthly_amount_base is None:
            without_rate.append(item.name)
        else:
            totals[item.level or ExpenseLevel.LIFESTYLE] += item.monthly_amount_base
    return RecurringSummary(
        base_currency=user.base_currency,
        monthly_total_base=sum(totals.values(), Decimal(0)),
        monthly_essential_base=totals[ExpenseLevel.ESSENTIAL],
        monthly_lifestyle_base=totals[ExpenseLevel.LIFESTYLE],
        without_rate=without_rate,
        items=items,
    )


@router.post("/recurring-expenses/preview", response_model=SchedulePreviewOut)
def preview_schedule(body: SchedulePreviewIn, user: CurrentUser):
    rule = _rule_or_422(body.rrule)
    horizon = body.end_date or body.start_date + timedelta(days=366 * 5)
    dates = occurrences(rule, body.start_date, body.start_date, horizon)[: body.count]
    return SchedulePreviewOut(
        rrule=rule,
        dates=dates,
        per_month=per_month(rule, body.start_date).quantize(Decimal("0.0001")),
    )


@router.post(
    "/recurring-expenses", response_model=RecurringExpenseOut, status_code=status.HTTP_201_CREATED
)
def create_recurring(body: RecurringExpenseIn, db: DbSession, user: CurrentUser):
    category = _check_refs(db, user, body.category_id, body.account_id)
    data = body.model_dump() | {"rrule": _rule_or_422(body.rrule)}
    expense = RecurringExpense(user_id=user.id, **data)
    db.add(expense)
    db.commit()
    return recurring_out(expense, category.level, None, RateResolver(db, user), date.today())


@router.put("/recurring-expenses/{expense_id}", response_model=RecurringExpenseOut)
def replace_recurring(expense_id: int, body: RecurringExpenseIn, db: DbSession, user: CurrentUser):
    expense = get_owned(db, RecurringExpense, expense_id, user, "Gasto fijo")
    debt_id = _debt_ids(db, [expense.id]).get(expense.id)
    if debt_id is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Este gasto es la cuota de una deuda; edítalo desde Deudas"
        )
    category = _check_refs(db, user, body.category_id, body.account_id)
    data = body.model_dump() | {"rrule": _rule_or_422(body.rrule)}
    for field, value in data.items():
        setattr(expense, field, value)
    reset_pending(db, expense)
    db.commit()
    return recurring_out(expense, category.level, None, RateResolver(db, user), date.today())


@router.delete("/recurring-expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring(expense_id: int, db: DbSession, user: CurrentUser):
    """Deletes the schedule and its obligations. Payments already made stay as movements."""
    expense = get_owned(db, RecurringExpense, expense_id, user, "Gasto fijo")
    if _debt_ids(db, [expense.id]):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Este gasto es la cuota de una deuda; bórralo desde Deudas"
        )
    db.delete(expense)
    db.commit()


# --- Obligations ------------------------------------------------------------------------------


def _obligations_query(user: User):
    return (
        select(Obligation, RecurringExpense, Transaction)
        .join(RecurringExpense, RecurringExpense.id == Obligation.recurring_expense_id)
        .outerjoin(Transaction, Transaction.obligation_id == Obligation.id)
        .where(RecurringExpense.user_id == user.id)
    )


def _obligation_out(o, e, t, debt_id, rates: RateResolver, today: date) -> ObligationOut:
    rate = rates.rate(o.currency, o.due_date)
    return ObligationOut(
        id=o.id,
        recurring_expense_id=e.id,
        name=e.name,
        category_id=e.category_id,
        account_id=e.account_id,
        debt_id=debt_id,
        due_date=o.due_date,
        expected_amount=o.expected_amount,
        currency=o.currency,
        expected_base=money(o.expected_amount / rate) if rate else None,
        status=o.status,
        is_overdue=o.status == ObligationStatus.PENDING and o.due_date < today,
        transaction_id=t.id if t else None,
        paid_amount=t.amount if t else None,
        paid_currency=t.currency if t else None,
    )


def _load_obligation_out(db: DbSession, user: User, obligation_id: int) -> ObligationOut:
    row = db.execute(_obligations_query(user).where(Obligation.id == obligation_id)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pago no encontrado")
    o, e, t = row
    debt_id = _debt_ids(db, [e.id]).get(e.id)
    return _obligation_out(o, e, t, debt_id, RateResolver(db, user), date.today())


@router.get("/obligations", response_model=list[ObligationOut])
def list_obligations(
    db: DbSession,
    user: CurrentUser,
    start: date | None = None,
    end: date | None = None,
    include_overdue: bool = True,
    obligation_status: ObligationStatus | None = None,
):
    """Fixed-expense payments due in [start, end], plus older unpaid ones if include_overdue."""
    today = date.today()
    start = start or today.replace(day=1)
    end = end or start + timedelta(days=31)
    if end < start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Rango de fechas inválido")
    sync_obligations(db, user, end)

    in_range = (Obligation.due_date >= start) & (Obligation.due_date <= end)
    if include_overdue:
        overdue = (Obligation.due_date < start) & (Obligation.status == ObligationStatus.PENDING)
        in_range = in_range | overdue
    q = _obligations_query(user).where(in_range)
    if obligation_status:
        q = q.where(Obligation.status == obligation_status)
    rows = db.execute(q.order_by(Obligation.due_date, RecurringExpense.name)).all()

    debts = _debt_ids(db, list({e.id for _, e, _ in rows}))
    rates = RateResolver(db, user)
    return [_obligation_out(o, e, t, debts.get(e.id), rates, today) for o, e, t in rows]


def _owned_obligation(db: DbSession, user: User, obligation_id: int) -> Obligation:
    obligation = db.get(Obligation, obligation_id)
    if obligation is not None:
        expense = db.get(RecurringExpense, obligation.recurring_expense_id)
        if expense.user_id == user.id:
            return obligation
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Pago no encontrado")


@router.post("/obligations/{obligation_id}/pay", response_model=ObligationOut)
def pay_obligation(obligation_id: int, body: PayObligationIn, db: DbSession, user: CurrentUser):
    """Registers the payment as an expense movement linked to the obligation."""
    obligation = _owned_obligation(db, user, obligation_id)
    if obligation.status != ObligationStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este pago ya no está pendiente")
    account = get_owned(db, Account, body.account_id, user, "Plataforma")
    amount = body.amount
    if amount is None:
        if account.currency != obligation.currency:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Indica cuánto salió en {account.currency}: el pago es en {obligation.currency}",
            )
        amount = obligation.expected_amount

    expense = db.get(RecurringExpense, obligation.recurring_expense_id)
    debt_id = _debt_ids(db, [expense.id]).get(expense.id)
    db.add(
        Transaction(
            user_id=user.id,
            account_id=account.id,
            kind=TransactionKind.EXPENSE,
            amount=amount,
            currency=account.currency,
            fx_rate=body.fx_rate,
            occurred_on=body.occurred_on or date.today(),
            category_id=expense.category_id,
            description=body.description or expense.name,
            obligation_id=obligation.id,
            debt_id=debt_id,
        )
    )
    obligation.status = ObligationStatus.PAID
    db.commit()
    return _load_obligation_out(db, user, obligation.id)


@router.post("/obligations/{obligation_id}/skip", response_model=ObligationOut)
def skip_obligation(obligation_id: int, db: DbSession, user: CurrentUser):
    """For dates that will not be paid (already paid before using the app, waived...)."""
    obligation = _owned_obligation(db, user, obligation_id)
    if obligation.status != ObligationStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este pago ya no está pendiente")
    obligation.status = ObligationStatus.SKIPPED
    db.commit()
    return _load_obligation_out(db, user, obligation.id)


@router.post("/obligations/{obligation_id}/reopen", response_model=ObligationOut)
def reopen_obligation(obligation_id: int, db: DbSession, user: CurrentUser):
    """Back to pending. If it was paid, the linked expense movement is deleted."""
    obligation = _owned_obligation(db, user, obligation_id)
    tx = db.scalar(select(Transaction).where(Transaction.obligation_id == obligation.id))
    if tx is not None:
        db.delete(tx)
    obligation.status = ObligationStatus.PENDING
    db.commit()
    return _load_obligation_out(db, user, obligation.id)
