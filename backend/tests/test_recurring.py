from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.conftest import make_account, make_category

D = Decimal
TODAY = date.today()


def iso(d: date) -> str:
    return d.isoformat()


@pytest.fixture
def setup(auth):
    auth.put(
        "/api/exchange-rates", json={"currency": "COP", "rate_date": "2020-01-01", "rate": 4000}
    )
    return {
        "nequi": make_account(auth, "Nequi", "COP", initial_balance="5000000"),
        "zinli": make_account(auth, "Zinli", "USD", initial_balance="1000"),
        "housing": make_category(auth, "Vivienda"),
        "subs": make_category(auth, "Suscripciones", level="lifestyle"),
    }


def create(auth, **body):
    res = auth.post("/api/recurring-expenses", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def rent(auth, s, start: date, amount="1200000"):
    return create(
        auth,
        name="Arriendo",
        category_id=s["housing"]["id"],
        account_id=s["nequi"]["id"],
        amount=amount,
        currency="COP",
        rrule="FREQ=MONTHLY",
        start_date=iso(start),
    )


def obligations(auth, start: date, end: date, **params):
    res = auth.get("/api/obligations", params={"start": iso(start), "end": iso(end), **params})
    assert res.status_code == 200, res.text
    return res.json()


def test_monthly_equivalents_and_totals(auth, setup):
    s = setup
    rent(auth, s, TODAY)
    create(
        auth,
        name="Hosting",
        category_id=s["subs"]["id"],
        amount="120",
        currency="USD",
        rrule="FREQ=YEARLY",
        start_date=iso(TODAY),
    )
    create(
        auth,
        name="Internet",
        category_id=s["housing"]["id"],
        amount="160000",
        currency="COP",
        rrule="freq=monthly;interval=2",
        start_date=iso(TODAY),
    )
    data = auth.get("/api/recurring-expenses").json()
    by_name = {i["name"]: i for i in data["items"]}
    assert D(by_name["Arriendo"]["monthly_amount_base"]) == D("300.00")
    assert D(by_name["Internet"]["monthly_amount"]) == D("80000.00")
    assert by_name["Internet"]["rrule"] == "FREQ=MONTHLY;INTERVAL=2"
    assert D(by_name["Hosting"]["monthly_amount_base"]) == D("10.00")
    assert D(data["monthly_essential_base"]) == D("320.00")
    assert D(data["monthly_lifestyle_base"]) == D("10.00")
    assert D(data["monthly_total_base"]) == D("330.00")


def test_invalid_rule_and_category(auth, setup):
    s = setup
    bad_rule = auth.post(
        "/api/recurring-expenses",
        json={
            "name": "X",
            "category_id": s["housing"]["id"],
            "amount": "1",
            "currency": "USD",
            "rrule": "FREQ=MONTHLY;COUNT=3",
            "start_date": iso(TODAY),
        },
    )
    assert bad_rule.status_code == 422
    income = make_category(auth, "Salario", kind="income")
    bad_cat = auth.post(
        "/api/recurring-expenses",
        json={
            "name": "X",
            "category_id": income["id"],
            "amount": "1",
            "currency": "USD",
            "rrule": "FREQ=MONTHLY",
            "start_date": iso(TODAY),
        },
    )
    assert bad_cat.status_code == 422


def test_preview(auth):
    res = auth.post(
        "/api/recurring-expenses/preview",
        json={"rrule": "FREQ=MONTHLY;BYMONTHDAY=15,-1", "start_date": "2026-10-01", "count": 3},
    )
    assert res.json()["dates"] == ["2026-10-15", "2026-10-31", "2026-11-15"]
    assert D(res.json()["per_month"]) == D("2")


def test_pay_obligation_creates_expense_and_reopen_reverts(auth, setup):
    s = setup
    rent(auth, s, TODAY)
    [ob] = obligations(auth, TODAY, TODAY + timedelta(days=20))
    assert ob["status"] == "pending"
    assert D(ob["expected_base"]) == D("300.00")

    paid = auth.post(f"/api/obligations/{ob['id']}/pay", json={"account_id": s["nequi"]["id"]})
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert D(paid.json()["paid_amount"]) == D("1200000")

    [tx] = auth.get("/api/transactions").json()
    assert tx["kind"] == "expense"
    assert tx["category_id"] == s["housing"]["id"]
    nequi = next(a for a in auth.get("/api/accounts").json()["accounts"] if a["name"] == "Nequi")
    assert D(nequi["balance"]) == D("3800000")

    # Cannot pay twice
    again = auth.post(f"/api/obligations/{ob['id']}/pay", json={"account_id": s["nequi"]["id"]})
    assert again.status_code == 409

    # Deleting the movement makes the obligation pending again
    assert auth.delete(f"/api/transactions/{tx['id']}").status_code == 204
    [ob] = obligations(auth, TODAY, TODAY + timedelta(days=20))
    assert ob["status"] == "pending"

    # Pay again, then reopen: the movement is removed
    auth.post(f"/api/obligations/{ob['id']}/pay", json={"account_id": s["nequi"]["id"]})
    assert auth.post(f"/api/obligations/{ob['id']}/reopen").json()["status"] == "pending"
    assert auth.get("/api/transactions").json() == []


def test_pay_from_other_currency_requires_amount(auth, setup):
    s = setup
    rent(auth, s, TODAY)
    [ob] = obligations(auth, TODAY, TODAY + timedelta(days=20))
    res = auth.post(f"/api/obligations/{ob['id']}/pay", json={"account_id": s["zinli"]["id"]})
    assert res.status_code == 422
    res = auth.post(
        f"/api/obligations/{ob['id']}/pay",
        json={"account_id": s["zinli"]["id"], "amount": "305", "occurred_on": iso(TODAY)},
    )
    assert res.status_code == 200
    assert res.json()["paid_currency"] == "USD"


def test_overdue_skip_and_schedule_change(auth, setup):
    s = setup
    start = TODAY - timedelta(days=65)
    expense = rent(auth, s, start)

    window = obligations(auth, TODAY, TODAY + timedelta(days=31))
    overdue = [o for o in window if o["is_overdue"]]
    assert len(overdue) >= 2  # previous months still unpaid show up

    oldest = overdue[0]
    assert auth.post(f"/api/obligations/{oldest['id']}/skip").json()["status"] == "skipped"
    auth.post(f"/api/obligations/{overdue[1]['id']}/pay", json={"account_id": s["nequi"]["id"]})

    # Raise the rent: pending obligations get the new amount, history stays
    res = auth.put(
        f"/api/recurring-expenses/{expense['id']}",
        json={
            "name": "Arriendo",
            "category_id": s["housing"]["id"],
            "account_id": s["nequi"]["id"],
            "amount": "1300000",
            "currency": "COP",
            "rrule": "FREQ=MONTHLY",
            "start_date": iso(start),
        },
    )
    assert res.status_code == 200
    everything = obligations(auth, start, TODAY + timedelta(days=31))
    by_status = {}
    for o in everything:
        by_status.setdefault(o["status"], []).append(D(o["expected_amount"]))
    assert by_status["skipped"] == [D(1200000)]
    assert by_status["paid"] == [D(1200000)]
    assert all(a == D(1300000) for a in by_status["pending"])


def test_deactivated_expense_stops_generating(auth, setup):
    s = setup
    e = rent(auth, s, TODAY)
    auth.put(
        f"/api/recurring-expenses/{e['id']}",
        json={
            "name": "Arriendo",
            "category_id": s["housing"]["id"],
            "amount": "1200000",
            "currency": "COP",
            "rrule": "FREQ=MONTHLY",
            "start_date": iso(TODAY),
            "is_active": False,
        },
    )
    assert obligations(auth, TODAY, TODAY + timedelta(days=90)) == []
    assert auth.get("/api/recurring-expenses").json()["items"] == []
    assert len(auth.get("/api/recurring-expenses?include_inactive=true").json()["items"]) == 1
