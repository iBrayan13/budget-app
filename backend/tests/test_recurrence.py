from datetime import date
from decimal import Decimal

import pytest

from app.services.debts import amortized_balance
from app.services.recurrence import (
    InvalidRule,
    next_occurrence,
    normalize_rule,
    nth_occurrence,
    occurrences,
    per_month,
)

D = Decimal


def test_monthly_on_31st_clamps_to_month_end():
    dates = occurrences("FREQ=MONTHLY", date(2026, 1, 31), date(2026, 1, 1), date(2026, 5, 31))
    assert dates == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
        date(2026, 5, 31),
    ]


def test_quincena_15_and_last_day():
    rule = "FREQ=MONTHLY;BYMONTHDAY=15,-1"
    dates = occurrences(rule, date(2026, 10, 1), date(2026, 10, 1), date(2026, 11, 30))
    assert dates == [date(2026, 10, 15), date(2026, 10, 31), date(2026, 11, 15), date(2026, 11, 30)]


def test_every_two_months():
    dates = occurrences(
        "FREQ=MONTHLY;INTERVAL=2", date(2026, 1, 10), date(2026, 1, 1), date(2026, 8, 1)
    )
    assert dates == [date(2026, 1, 10), date(2026, 3, 10), date(2026, 5, 10), date(2026, 7, 10)]


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        ("FREQ=MONTHLY", D("1")),
        ("FREQ=MONTHLY;INTERVAL=2", D("0.5")),
        ("FREQ=MONTHLY;BYMONTHDAY=15,-1", D("2")),
        ("FREQ=YEARLY", D("0.0833")),
        ("FREQ=WEEKLY;INTERVAL=2", D("2.1741")),  # 365.25 / 14 / 12
        ("FREQ=WEEKLY;BYDAY=MO,TH", D("8.6964")),
        ("FREQ=DAILY;INTERVAL=15", D("2.0292")),
        ("FREQ=MONTHLY;INTERVAL=3", D("0.3333")),
    ],
)
def test_per_month(rule, expected):
    assert per_month(rule, date(2026, 10, 9)).quantize(D("0.0001")) == expected


def test_normalize_accepts_lowercase_and_prefix():
    assert normalize_rule(" rrule:freq=monthly;interval=2 ") == "FREQ=MONTHLY;INTERVAL=2"


@pytest.mark.parametrize(
    "rule",
    [
        "FREQ=HOURLY",
        "FREQ=MONTHLY;COUNT=12",
        "FREQ=MONTHLY;UNTIL=20270101",
        "FREQ=MONTHLY;INTERVAL=0",
        "MONTHLY",
        "FREQ=MONTHLY;BYMONTHDAY=40",
        "FREQ=MONTHLY;BYMONTHDAY=0",
        "FREQ=MONTHLY;INTERVAL=X",
        "FREQ=YEARLY;BYMONTH=13",
        "FREQ=MONTHLY; DROP TABLE",
        "",
    ],
)
def test_normalize_rejects(rule):
    with pytest.raises(InvalidRule):
        normalize_rule(rule)


def test_nth_and_next_occurrence():
    assert nth_occurrence("FREQ=MONTHLY", date(2026, 11, 5), 12) == date(2027, 10, 5)
    assert next_occurrence("FREQ=MONTHLY", date(2026, 1, 5), date(2026, 10, 9)) == date(2026, 11, 5)
    assert (
        next_occurrence("FREQ=MONTHLY", date(2026, 1, 5), date(2026, 10, 9), date(2026, 10, 31))
        is None
    )


def test_amortized_balance():
    # 1000 at 12 %/year, 12 monthly installments of 88.85 -> paid off
    assert amortized_balance(D(1000), D(12), D(12), D("88.85"), 12) < D("0.10")
    after_six = amortized_balance(D(1000), D(12), D(12), D("88.85"), 6)
    assert D(510) < after_six < D(520)
    # No interest: plain subtraction
    assert amortized_balance(D(1000), D(0), D(12), D(100), 3) == D(700)
