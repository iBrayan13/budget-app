from datetime import date
from decimal import Decimal

from tests.conftest import make_account, make_category

D = Decimal
MONTH = "2026-10-01"


def _tx(auth, account, kind, amount, category, on):
    body = {"account_id": account["id"], "kind": kind, "amount": amount, "occurred_on": on}
    if category is not None:
        body["category_id"] = category["id"]
    assert auth.post("/api/transactions", json=body).status_code == 201


def _setup(auth):
    """Income 1000/month in Jul-Sep, 300 essential and 60 lifestyle spent in the window."""
    fb = make_account(auth, "Facebank", "USD", "bank", initial_balance="5000")
    salary = make_category(auth, "Salario", kind="income")
    mercado = make_category(auth, "Mercado")
    cine = make_category(auth, "Cine", level="lifestyle")
    for on in ("2026-07-10", "2026-08-10", "2026-09-10"):
        _tx(auth, fb, "income", "1000", salary, on)
    _tx(auth, fb, "expense", "300", mercado, "2026-08-15")
    _tx(auth, fb, "expense", "60", cine, "2026-09-15")
    return fb


def _emergency_id(auth):
    plan = auth.get("/api/plan", params={"month": MONTH}).json()
    return next(g["id"] for g in plan["goals"] if g["kind"] == "emergency_fund")


def test_survive_live_and_fund_from_averages(auth):
    _setup(auth)
    plan = auth.get("/api/plan", params={"month": MONTH}).json()
    assert D(plan["income_avg"]) == D("1000.00")
    assert D(plan["survive"]) == D("100.00")  # 300 essential / 3 months
    assert D(plan["live"]) == D("120.00")  # + 60 lifestyle / 3 months
    assert D(plan["savings_capacity"]) == D("880.00")
    assert D(plan["fund_target"]) == D("600.00")  # 6 months x 100
    assert D(plan["fund_missing"]) == D("600.00")
    assert D(plan["fund_current"]) == D("0.00")
    assert D(plan["accounts_total"]) == D("7640.00")
    assert D(plan["rule_essential_pct"]) == D("10.00")
    assert D(plan["rule_lifestyle_pct"]) == D("2.00")  # 20 of 1000
    assert D(plan["rule_savings_pct"]) == D("88.00")


def test_fund_progress_free_balance_and_eta(auth):
    fb = _setup(auth)
    res = auth.post(
        f"/api/goals/{_emergency_id(auth)}/allocations",
        json={"account_id": fb["id"], "amount": "200", "allocated_on": date.today().isoformat()},
    )
    assert res.status_code == 201, res.text

    plan = auth.get("/api/plan", params={"month": MONTH}).json()
    assert D(plan["fund_current"]) == D("200.00")
    assert D(plan["fund_missing"]) == D("400.00")
    assert plan["fund_months_covered"] == "2.00"
    assert D(plan["reserved"]) == D("200.00")
    assert D(plan["free"]) == D("7440.00")
    assert D(plan["pace"]) == D("66.67")  # 200 contributed this quarter / 3
    assert plan["fund_eta"] is not None


def test_scenario_numbers(auth):
    fb = _setup(auth)
    auth.post(
        f"/api/goals/{_emergency_id(auth)}/allocations",
        json={"account_id": fb["id"], "amount": "200", "allocated_on": date.today().isoformat()},
    )
    s = auth.post(
        "/api/plan/scenario", params={"month": MONTH}, json={"lifestyle_target": "220"}
    ).json()
    # live target 100 + 220 = 320; capacity 1000 - 320 = 680; missing 400 -> 0.59 months
    assert D(s["live_target"]) == D("320.00")
    assert D(s["savings_capacity"]) == D("680.00")
    assert D(s["fund_months"]) == D("0.59")
    assert D(s["required_income"]) == D("386.67")  # 320 + pace 66.67
    assert D(s["max_lifestyle"]) == D("833.33")  # 1000 - 100 - 66.67


def test_scenario_without_capacity_has_no_fund_date(auth):
    _setup(auth)
    s = auth.post(
        "/api/plan/scenario", params={"month": MONTH}, json={"lifestyle_target": "950"}
    ).json()
    assert s["fund_months"] is None  # 1000 - (100 + 950) < 0


def test_emergency_months_setting_changes_target(auth):
    _setup(auth)
    assert auth.patch("/api/plan/settings", json={"emergency_fund_months": 3}).status_code == 200
    plan = auth.get("/api/plan", params={"month": MONTH}).json()
    assert plan["emergency_months"] == 3
    assert D(plan["fund_target"]) == D("300.00")
    assert auth.patch("/api/plan/settings", json={"emergency_fund_months": 0}).status_code == 422


def test_month_costs_include_paid_and_pending_fixed(auth):
    fb = _setup(auth)
    housing = make_category(auth, "Vivienda")
    auth.post(
        "/api/recurring-expenses",
        json={
            "name": "Arriendo",
            "category_id": housing["id"],
            "account_id": fb["id"],
            "amount": "200",
            "currency": "USD",
            "rrule": "FREQ=MONTHLY",
            "start_date": "2026-10-05",
        },
    )
    plan = auth.get("/api/plan", params={"month": MONTH}).json()
    # Nothing paid yet: the 200 due on Oct 5 is pending, so it is already a cost of the month
    assert D(plan["costs_month"]) == D("200.00")
    assert D(plan["net_month"]) == D("-200.00")
    assert D(plan["income_month"]) == D("0.00")
    assert D(plan["fixed_essential"]) == D("200.00")
    assert D(plan["survive"]) == D("300.00")  # 100 variable + 200 rent
