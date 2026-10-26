from decimal import Decimal

from tests.conftest import make_account, make_category


def test_venezuelan_account_in_bolivares_is_valued_with_its_rate(auth):
    banco = make_account(auth, "Banesco", "VES", "bank", initial_balance="36500")
    cat = make_category(auth, "Mercado")
    auth.put(
        "/api/exchange-rates", json={"currency": "VES", "rate_date": "2026-10-01", "rate": "36.5"}
    )
    auth.put(
        "/api/exchange-rates", json={"currency": "COP", "rate_date": "2026-10-01", "rate": "3900"}
    )

    res = auth.post(
        "/api/transactions",
        json={
            "account_id": banco["id"],
            "kind": "expense",
            "amount": "365",
            "category_id": cat["id"],
            "occurred_on": "2026-10-05",
        },
    )
    assert res.status_code == 201, res.text
    # 365 VES at 36.5 per USD = 10 USD
    assert Decimal(res.json()["amount_base"]) == Decimal("10.00")

    accounts = {a["name"]: a for a in auth.get("/api/accounts").json()["accounts"]}
    assert Decimal(accounts["Banesco"]["balance"]) == Decimal("36135")
    assert Decimal(accounts["Banesco"]["balance_base"]) == Decimal("990.00")


def test_p2p_between_colombia_and_venezuela_costs_spread_in_usd(auth):
    cop = make_account(auth, "Nequi", "COP", initial_balance="4000000")
    ves = make_account(auth, "Banesco", "VES")
    auth.put(
        "/api/exchange-rates", json={"currency": "COP", "rate_date": "2026-10-01", "rate": "3900"}
    )
    auth.put(
        "/api/exchange-rates", json={"currency": "VES", "rate_date": "2026-10-01", "rate": "36.5"}
    )

    # 390.000 COP (= 100 USD) sent, 3.285 VES received (= 90 USD) -> 10 USD cost
    res = auth.post(
        "/api/transfers",
        json={
            "from_account_id": cop["id"],
            "to_account_id": ves["id"],
            "amount_out": "390000",
            "amount_in": "3285",
            "occurred_on": "2026-10-05",
        },
    )
    assert res.status_code == 201, res.text
    assert Decimal(res.json()["cost"]["cost"]) == Decimal("10.00")
    assert Decimal(res.json()["cost"]["cost_pct"]) == Decimal("10.00")
