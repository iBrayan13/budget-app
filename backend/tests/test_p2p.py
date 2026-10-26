from decimal import Decimal

import pytest

from tests.conftest import make_account

D = Decimal


@pytest.fixture
def platforms(auth):
    return {
        "fb": make_account(auth, "Facebank", "USD", "bank", initial_balance="1000"),
        "bn": make_account(auth, "Binance", "USDT", "exchange"),
        "nq": make_account(auth, "Nequi", "COP"),
    }


def set_cop(auth, rate, day="2026-10-01"):
    auth.put("/api/exchange-rates", json={"currency": "COP", "rate_date": day, "rate": rate})


def step(frm, to, out, inn, fee="0", **extra):
    return {
        "from_account_id": frm["id"],
        "to_account_id": to["id"],
        "amount_out": out,
        "amount_in": inn,
        "fee_amount": fee,
        **extra,
    }


def test_explicit_fee_only(auth, platforms):
    p = platforms
    res = auth.post(
        "/api/transfers",
        json=step(p["fb"], p["bn"], "100", "99", fee="1", occurred_on="2026-10-02"),
    )
    cost = res.json()["cost"]
    assert D(cost["cost"]) == D("1.00")
    assert D(cost["fee"]) == D("1.00")
    assert D(cost["spread"]) == D("0.00")
    assert D(cost["cost_pct"]) == D("1.00")


def test_spread_against_reference_rate(auth, platforms):
    p = platforms
    set_cop(auth, 4100)
    # Sold 99 USDT for 395.000 COP; at 4100 that is 96.34 USD -> 2.66 USD hidden cost
    res = auth.post(
        "/api/transfers", json=step(p["bn"], p["nq"], "99", "395000", occurred_on="2026-10-02")
    )
    cost = res.json()["cost"]
    assert D(cost["value_in"]) == D("96.34")
    assert D(cost["cost"]) == D("2.66")
    assert D(cost["spread"]) == D("2.66")
    assert D(cost["cost_pct"]) == D("2.69")


def test_reference_rate_on_transfer_overrides_table(auth, platforms):
    p = platforms
    set_cop(auth, 4100)
    res = auth.post(
        "/api/transfers",
        json=step(p["bn"], p["nq"], "100", "400000", occurred_on="2026-10-02", ref_rate_in="4000"),
    )
    assert D(res.json()["cost"]["cost"]) == D("0.00")


def test_missing_rate_gives_null_cost(auth, platforms):
    p = platforms
    res = auth.post(
        "/api/transfers", json=step(p["bn"], p["nq"], "99", "395000", occurred_on="2026-10-02")
    )
    assert res.json()["cost"]["cost"] is None
    summary = auth.get("/api/p2p/summary").json()
    assert summary["missing_rates"] == 1
    assert summary["count"] == 0


def test_route_chain_totals_and_balances(auth, platforms):
    p = platforms
    set_cop(auth, 4100)
    res = auth.post(
        "/api/transfer-routes",
        json={
            "name": "Facebank → Nequi",
            "started_on": "2026-10-02",
            "steps": [
                step(p["fb"], p["bn"], "100", "99", fee="1"),
                step(p["bn"], p["nq"], "99", "395000", occurred_on="2026-10-03"),
            ],
        },
    )
    assert res.status_code == 201, res.text
    route = res.json()
    assert [s["step"] for s in route["steps"]] == [1, 2]
    assert route["steps"][1]["occurred_on"] == "2026-10-03"
    assert D(route["cost"]["value_out"]) == D("100.00")
    assert D(route["cost"]["value_in"]) == D("96.34")
    assert D(route["cost"]["cost"]) == D("3.66")
    assert D(route["cost"]["fee"]) == D("1.00")
    assert D(route["cost"]["cost_pct"]) == D("3.66")

    accounts = {a["name"]: a for a in auth.get("/api/accounts").json()["accounts"]}
    assert D(accounts["Facebank"]["balance"]) == D("900")
    assert D(accounts["Binance"]["balance"]) == D("0")
    assert accounts["Binance"]["balance"] == "0.00000000"  # never scientific notation
    assert D(accounts["Nequi"]["balance"]) == D("395000")

    summary = auth.get("/api/p2p/summary", params={"start": "2026-10-01", "end": "2026-10-31"})
    s = summary.json()
    assert s["count"] == 2
    assert D(s["cost"]) == D("3.66")
    assert D(s["fees"]) == D("1.00")
    assert D(s["spread"]) == D("2.66")
    # Volume counts the money once (first step), so the % matches the route's own %
    assert D(s["volume"]) == D("100.00")
    assert D(s["cost_pct"]) == D("3.66")
    assert s["by_pair"][0]["to_account_id"] == p["nq"]["id"]  # most expensive pair first

    # Replace the route with a single direct step
    res = auth.put(
        f"/api/transfer-routes/{route['id']}",
        json={"started_on": "2026-10-02", "steps": [step(p["fb"], p["bn"], "50", "50")]},
    )
    assert len(res.json()["steps"]) == 1
    assert len(auth.get("/api/transfers").json()) == 1

    # Deleting the route removes its steps and restores balances
    assert auth.delete(f"/api/transfer-routes/{route['id']}").status_code == 204
    assert auth.get("/api/transfers").json() == []
    accounts = {a["name"]: a for a in auth.get("/api/accounts").json()["accounts"]}
    assert D(accounts["Facebank"]["balance"]) == D("1000")


def test_transfer_validation(auth, platforms):
    p = platforms
    same = step(p["fb"], p["fb"], "10", "10", occurred_on="2026-10-02")
    assert auth.post("/api/transfers", json=same).status_code == 422
    fee_too_big = step(p["fb"], p["bn"], "10", "10", fee="11", occurred_on="2026-10-02")
    assert auth.post("/api/transfers", json=fee_too_big).status_code == 422


def test_summary_date_filter(auth, platforms):
    p = platforms
    auth.post("/api/transfers", json=step(p["fb"], p["bn"], "100", "99", occurred_on="2026-09-15"))
    auth.post("/api/transfers", json=step(p["fb"], p["bn"], "100", "98", occurred_on="2026-10-15"))
    october = auth.get("/api/p2p/summary", params={"start": "2026-10-01", "end": "2026-10-31"})
    assert D(october.json()["cost"]) == D("2.00")
    assert D(auth.get("/api/p2p/summary").json()["cost"]) == D("3.00")
