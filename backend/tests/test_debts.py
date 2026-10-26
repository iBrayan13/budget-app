from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.conftest import make_account, make_category

D = Decimal
TODAY = date.today()


@pytest.fixture
def s(auth):
    auth.put(
        "/api/exchange-rates", json={"currency": "COP", "rate_date": "2020-01-01", "rate": 4000}
    )
    return {
        "nequi": make_account(auth, "Nequi", "COP", initial_balance="10000000"),
        "zinli": make_account(auth, "Zinli", "USD", initial_balance="2000"),
    }


def loan_body(s, **overrides):
    body = {
        "name": "Moto",
        "kind": "installment_loan",
        "creditor": "Banco",
        "currency": "COP",
        "original_amount": "1200000",
        "interest_rate_annual": "24",
        "start_date": TODAY.isoformat(),
        "schedule": {
            "installment_amount": "63450",
            "rrule": "FREQ=MONTHLY",
            "first_due_date": TODAY.isoformat(),
            "installments_total": 24,
            "account_id": s["nequi"]["id"],
        },
    }
    return body | overrides


def test_installment_loan_creates_schedule_and_amortizes(auth, s):
    res = auth.post("/api/debts", json=loan_body(s))
    assert res.status_code == 201, res.text
    debt = res.json()
    assert debt["remaining_installments"] == 24
    assert D(debt["total_interest"]) == D("322800.00")  # 24 * 63450 - 1.2M
    assert D(debt["monthly_payment"]) == D("63450.00")
    assert debt["end_date"] is not None

    # The installment shows up as a fixed expense in "Pago de deudas" (essential)
    rec = auth.get("/api/recurring-expenses").json()
    assert [i["name"] for i in rec["items"]] == ["Cuota Moto"]
    assert rec["items"][0]["debt_id"] == debt["id"]
    assert rec["items"][0]["level"] == "essential"

    # Editing that fixed expense directly is blocked
    item = rec["items"][0]
    blocked = auth.put(
        f"/api/recurring-expenses/{item['id']}",
        json={
            "name": "x",
            "category_id": item["category_id"],
            "amount": "1",
            "currency": "COP",
            "rrule": "FREQ=MONTHLY",
            "start_date": TODAY.isoformat(),
        },
    )
    assert blocked.status_code == 409

    # Paying the obligation counts as an installment and lowers the amortized balance
    obs = auth.get(
        "/api/obligations",
        params={"start": TODAY.isoformat(), "end": (TODAY + timedelta(days=5)).isoformat()},
    ).json()
    [ob] = [o for o in obs if o["debt_id"] == debt["id"]]
    auth.post(f"/api/obligations/{ob['id']}/pay", json={"account_id": s["nequi"]["id"]})

    [after] = auth.get("/api/debts").json()["items"]
    assert after["payments_count"] == 1
    assert after["remaining_installments"] == 23
    # 1.2M * 1.02 - 63450 = 1,160,550
    assert D(after["balance"]) == D("1160550.00")
    assert D(after["balance_base"]) == D("290.14")
    assert D("3.0") < D(after["progress_pct"]) < D("3.5")


def test_informal_debt_with_extra_payments(auth, s):
    res = auth.post(
        "/api/debts",
        json={
            "name": "Préstamo de mi hermano",
            "kind": "informal",
            "currency": "USD",
            "original_amount": "500",
            "start_date": TODAY.isoformat(),
        },
    )
    debt = res.json()
    assert debt["recurring_expense_id"] is None
    pay = auth.post(
        f"/api/debts/{debt['id']}/payments",
        json={"account_id": s["zinli"]["id"], "amount": "200", "occurred_on": TODAY.isoformat()},
    )
    assert pay.status_code == 201, pay.text
    assert D(pay.json()["balance"]) == D("300.00")
    assert D(pay.json()["progress_pct"]) == D("40.00")

    # Paying from a COP platform converts at the reference rate (400000 COP = 100 USD)
    pay = auth.post(
        f"/api/debts/{debt['id']}/payments",
        json={"account_id": s["nequi"]["id"], "amount": "400000", "occurred_on": TODAY.isoformat()},
    )
    assert D(pay.json()["balance"]) == D("200.00")


def test_credit_card_balance_comes_from_card_account(auth, s):
    card = make_account(auth, "Tarjeta", "USD", kind="credit_card")
    shopping = make_category(auth, "Tecnología", level="lifestyle")
    auth.post(
        "/api/transactions",
        json={
            "account_id": card["id"],
            "kind": "expense",
            "amount": "300",
            "category_id": shopping["id"],
            "occurred_on": TODAY.isoformat(),
        },
    )
    debt = auth.post(
        "/api/debts",
        json={
            "name": "Visa",
            "kind": "credit_card",
            "currency": "USD",
            "original_amount": "300",
            "start_date": TODAY.isoformat(),
            "account_id": card["id"],
        },
    ).json()
    assert D(debt["balance"]) == D("300.00")

    paid = auth.post(
        f"/api/debts/{debt['id']}/payments",
        json={"account_id": s["zinli"]["id"], "amount": "100", "occurred_on": TODAY.isoformat()},
    )
    assert D(paid.json()["balance"]) == D("200.00")
    # It was a transfer, not an expense: the purchase was already the expense
    assert len(auth.get("/api/transfers").json()) == 1


def test_validation(auth, s):
    no_schedule = loan_body(s)
    no_schedule.pop("schedule")
    assert auth.post("/api/debts", json=no_schedule).status_code == 422
    card_without_account = {
        "name": "Visa",
        "kind": "credit_card",
        "currency": "USD",
        "original_amount": "1",
        "start_date": TODAY.isoformat(),
    }
    assert auth.post("/api/debts", json=card_without_account).status_code == 422


def test_summary_ratio_and_capacity(auth, s):
    salary = make_category(auth, "Salario", kind="income")
    auth.post(
        "/api/transactions",
        json={
            "account_id": s["zinli"]["id"],
            "kind": "income",
            "amount": "1000",
            "category_id": salary["id"],
            "occurred_on": TODAY.isoformat(),
        },
    )
    auth.post("/api/debts", json=loan_body(s))
    summary = auth.get("/api/debts").json()
    # 63450 COP / 4000 = 15.86 USD per month over 1000 income
    assert D(summary["monthly_payments_base"]) == D("15.86")
    assert D(summary["avg_monthly_income_base"]) == D("1000.00")
    assert D(summary["debt_ratio_pct"]) == D("1.59")
    assert D(summary["capacity_base"]) == D("284.14")
    assert D(summary["max_ratio_pct"]) == D("30.00")


def test_update_and_delete_debt(auth, s):
    debt = auth.post("/api/debts", json=loan_body(s)).json()
    body = loan_body(s)
    body["schedule"]["installment_amount"] = "70000"
    updated = auth.put(f"/api/debts/{debt['id']}", json=body).json()
    assert D(updated["installment_amount"]) == D("70000")
    assert updated["recurring_expense_id"] == debt["recurring_expense_id"]
    assert updated["schedule_first_due_date"] == TODAY.isoformat()

    informal = loan_body(s, kind="informal", schedule=None)
    updated = auth.put(f"/api/debts/{debt['id']}", json=informal).json()
    assert updated["recurring_expense_id"] is None
    assert auth.get("/api/recurring-expenses").json()["items"] == []

    assert auth.delete(f"/api/debts/{debt['id']}").status_code == 204
    assert auth.get("/api/debts").json()["items"] == []


def test_debt_in_any_currency(auth, s):
    auth.put(
        "/api/exchange-rates", json={"currency": "VES", "rate_date": "2020-01-01", "rate": "36.5"}
    )
    for currency, amount in (("USDT", "800"), ("VES", "36500")):
        res = auth.post(
            "/api/debts",
            json={
                "name": f"Deuda {currency}",
                "kind": "informal",
                "currency": currency,
                "original_amount": amount,
                "start_date": TODAY.isoformat(),
            },
        )
        assert res.status_code == 201, res.text
        assert res.json()["currency"] == currency
    summary = auth.get("/api/debts").json()
    # 800 USDT (1:1 with USD) + 36500 VES (= 1000 USD at 36.5)
    assert D(summary["total_balance_base"]) == D("1800.00")
