from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Obligation, ObligationStatus, RecurringExpense, User
from app.services.recurrence import occurrences

# Obligations are materialized lazily, never further than this into the future.
MAX_HORIZON_DAYS = 400


def sync_obligations(db: Session, user: User, until: date) -> None:
    """Creates the missing obligations of every active fixed expense up to `until`."""
    until = min(until, date.today() + timedelta(days=MAX_HORIZON_DAYS))
    expenses = db.scalars(
        select(RecurringExpense).where(
            RecurringExpense.user_id == user.id, RecurringExpense.is_active
        )
    ).all()
    if not expenses:
        return

    existing = set(
        db.execute(
            select(Obligation.recurring_expense_id, Obligation.due_date).where(
                Obligation.recurring_expense_id.in_([e.id for e in expenses])
            )
        )
        .tuples()
        .all()
    )
    new = []
    for e in expenses:
        horizon = min(until, e.end_date) if e.end_date else until
        for due in occurrences(e.rrule, e.start_date, e.start_date, horizon):
            if (e.id, due) not in existing:
                new.append(
                    {
                        "recurring_expense_id": e.id,
                        "due_date": due,
                        "expected_amount": e.amount,
                        "currency": e.currency,
                        "status": ObligationStatus.PENDING,
                    }
                )
    if new:
        # Concurrent requests may sync the same dates; the unique constraint settles it.
        db.execute(
            insert(Obligation)
            .values(new)
            .on_conflict_do_nothing(index_elements=["recurring_expense_id", "due_date"])
        )
        db.commit()


def reset_pending(db: Session, expense: RecurringExpense) -> None:
    """After the schedule or amount changes, pending obligations are regenerated on next sync.

    Paid and skipped obligations are history and stay untouched.
    """
    db.execute(
        delete(Obligation).where(
            Obligation.recurring_expense_id == expense.id,
            Obligation.status == ObligationStatus.PENDING,
        )
    )
