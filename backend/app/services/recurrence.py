"""Schedules of fixed expenses as RFC 5545 rules (without DTSTART: start_date plays that role).

Examples:  FREQ=MONTHLY                     every month on the start day
           FREQ=MONTHLY;INTERVAL=2          every 2 months
           FREQ=MONTHLY;BYMONTHDAY=15,-1    days 15 and last of the month (quincena)
           FREQ=WEEKLY;INTERVAL=2           every 14 days
           FREQ=YEARLY                      once a year
"""

import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, rrulestr

ALLOWED_FREQ = {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}
FORBIDDEN_PARTS = {"DTSTART", "UNTIL", "COUNT"}  # dates come from start_date / end_date
_RULE_CHARS = re.compile(r"^[A-Z0-9=;,+\-]+$")

# Long window so bimonthly/yearly rules and leap years average out.
_FACTOR_YEARS = 4
_DAYS_PER_YEAR = Decimal("365.25")


class InvalidRule(ValueError):
    pass


def _int_list(value: str, lo: int, hi: int) -> bool:
    try:
        numbers = [int(v) for v in value.split(",")]
    except ValueError:
        return False
    return all(lo <= n <= hi and n != 0 for n in numbers)


def normalize_rule(rule: str) -> str:
    rule = rule.strip().upper().removeprefix("RRULE:")
    if not rule or len(rule) > 255 or not _RULE_CHARS.match(rule):
        raise InvalidRule("Regla de recurrencia inválida")
    parts = dict(p.split("=", 1) for p in rule.split(";") if "=" in p)
    if len(parts) != len(rule.split(";")):
        raise InvalidRule("Regla de recurrencia inválida")
    if parts.get("FREQ") not in ALLOWED_FREQ:
        raise InvalidRule("La frecuencia debe ser diaria, semanal, mensual o anual")
    if FORBIDDEN_PARTS & parts.keys():
        raise InvalidRule(
            "Usa la fecha de inicio y la fecha de fin en lugar de DTSTART/UNTIL/COUNT"
        )
    if not _int_list(parts.get("INTERVAL", "1"), 1, 999):
        raise InvalidRule("El intervalo debe ser un número entre 1 y 999")
    # dateutil silently accepts out-of-range values (e.g. BYMONTHDAY=40 never happens).
    for key, lo, hi in (("BYMONTHDAY", -31, 31), ("BYMONTH", 1, 12), ("BYSETPOS", -366, 366)):
        if key in parts and not _int_list(parts[key], lo, hi):
            raise InvalidRule(f"Valor fuera de rango en {key}")
    build_rule(rule, date(2026, 1, 31))  # parses with dateutil, raising on bad parts
    return rule


def build_rule(rule: str, start: date) -> rrule:
    try:
        rr = rrulestr(rule, dtstart=datetime.combine(start, time()))
    except (ValueError, TypeError) as exc:
        raise InvalidRule(f"Regla de recurrencia inválida: {exc}") from exc
    if not isinstance(rr, rrule):
        raise InvalidRule("Regla de recurrencia inválida")

    parts = dict(p.split("=", 1) for p in rule.split(";"))
    plain_monthly = parts["FREQ"] == "MONTHLY" and not (
        {"BYMONTHDAY", "BYDAY", "BYSETPOS"} & parts.keys()
    )
    if plain_monthly and start.day > 28:
        # "Every month on the 31st" would skip short months; clamp to the month's last day instead.
        rr = rr.replace(bymonthday=tuple(range(28, start.day + 1)), bysetpos=-1)
    return rr


def occurrences(rule: str, start: date, window_start: date, window_end: date) -> list[date]:
    if window_end < window_start:
        return []
    rr = build_rule(rule, start)
    lo = datetime.combine(max(window_start, start), time())
    hi = datetime.combine(window_end, time())
    return [d.date() for d in rr.between(lo, hi, inc=True)]


def next_occurrence(rule: str, start: date, after: date, end: date | None = None) -> date | None:
    rr = build_rule(rule, start)
    nxt = rr.after(datetime.combine(after, time()), inc=True)
    if nxt is None or (end is not None and nxt.date() > end):
        return None
    return nxt.date()


def nth_occurrence(rule: str, start: date, n: int) -> date:
    """Date of the n-th occurrence (1-based), e.g. the last installment of a loan."""
    rr = build_rule(rule, start)
    for i, d in enumerate(rr, start=1):
        if i == n:
            return d.date()
    raise InvalidRule("La regla no produce suficientes fechas")


def per_month(rule: str, start: date) -> Decimal:
    """Average number of occurrences per month (monthly = 1, bimonthly = 0.5, quincena = 2)."""
    parts = dict(p.split("=", 1) for p in rule.split(";"))
    interval = Decimal(parts.get("INTERVAL", "1"))
    simple = parts.keys() <= {"FREQ", "INTERVAL", "BYDAY", "WKST"}
    # Day/week based rules do not fit whole months: use the exact average year.
    if simple and parts["FREQ"] == "DAILY" and "BYDAY" not in parts:
        return _DAYS_PER_YEAR / 12 / interval
    if simple and parts["FREQ"] == "WEEKLY":
        days = len(parts["BYDAY"].split(",")) if "BYDAY" in parts else 1
        return _DAYS_PER_YEAR / 7 / 12 * days / interval
    # Month/year based rules repeat exactly every few years: count them.
    end = start + relativedelta(years=_FACTOR_YEARS) - timedelta(days=1)
    count = len(occurrences(rule, start, start, end))
    return Decimal(count) / Decimal(12 * _FACTOR_YEARS)


def per_year(rule: str, start: date) -> Decimal:
    return per_month(rule, start) * 12
