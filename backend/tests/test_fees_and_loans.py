from decimal import Decimal

from tests.conftest import make_account

D = Decimal


def test_external_fee_is_charged_from_its_own_platform_and_currency(auth):
    fb = make_account(auth, "Facebank", "USD", "bank", initial_balance="1000")
    bn = make_account(auth, "Binance", "USDT", "exchange", initial_balance="50")
    res = auth.post(
        "/api/transfers",
        json={
            "from_account_id": fb["id"],
            "to_account_id": bn["id"],
            "amount_out": "100",
            "amount_in": "99",
            "fee_amount": "1",
            "fee_account_id": bn["id"],
            "occurred_on": "2026-10-05",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["fee_currency"] == "USDT"
    # 100 USD sent + 1 USDT fee = 101 of value; 99 USDT arrived -> cost 2, of which 1 is fee
    assert D(body["cost"]["cost"]) == D("2.00")
    assert D(body["cost"]["fee"]) == D("1.00")
    assert D(body["cost"]["spread"]) == D("1.00")

    accounts = {a["name"]: a for a in auth.get("/api/accounts").json()["accounts"]}
    assert D(accounts["Facebank"]["balance"]) == D("900")
    assert D(accounts["Binance"]["balance"]) == D("148")  # 50 + 99 - 1


def test_fee_from_same_platform_is_an_extra_debit(auth):
    fb = make_account(auth, "Facebank", "USD", "bank", initial_balance="1000")
    bn = make_account(auth, "Binance", "USDT", "exchange")
    res = auth.post(
        "/api/transfers",
        json={
            "from_account_id": fb["id"],
            "to_account_id": bn["id"],
            "amount_out": "100",
            "amount_in": "99",
            "fee_amount": "1",
            "fee_account_id": fb["id"],
            "occurred_on": "2026-10-05",
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["fee_account_id"] == fb["id"]
    assert D(res.json()["cost"]["cost"]) == D("2.00")
    accounts = {a["name"]: a for a in auth.get("/api/accounts").json()["accounts"]}
    assert D(accounts["Facebank"]["balance"]) == D("899")


def test_legacy_inside_fee_stays_part_of_the_amount_sent(auth):
    fb = make_account(auth, "Facebank", "USD", "bank", initial_balance="1000")
    bn = make_account(auth, "Binance", "USDT", "exchange")
    res = auth.post(
        "/api/transfers",
        json={
            "from_account_id": fb["id"],
            "to_account_id": bn["id"],
            "amount_out": "100",
            "amount_in": "99",
            "fee_amount": "1",
            "occurred_on": "2026-10-05",
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["fee_account_id"] is None
    assert D(res.json()["cost"]["cost"]) == D("1.00")
    accounts = {a["name"]: a for a in auth.get("/api/accounts").json()["accounts"]}
    assert D(accounts["Facebank"]["balance"]) == D("900")


def test_inside_fee_cannot_exceed_amount_sent(auth):
    fb = make_account(auth, "Facebank", "USD", "bank", initial_balance="1000")
    bn = make_account(auth, "Binance", "USDT", "exchange")
    res = auth.post(
        "/api/transfers",
        json={
            "from_account_id": fb["id"],
            "to_account_id": bn["id"],
            "amount_out": "10",
            "amount_in": "9",
            "fee_amount": "11",
            "occurred_on": "2026-10-05",
        },
    )
    assert res.status_code == 422


def test_loan_moves_money_out_and_payments_back(auth):
    fb = make_account(auth, "Facebank", "USD", "bank", initial_balance="1000")
    zinli = make_account(auth, "Zinli", "USD", "wallet")
    nequi = make_account(auth, "Nequi", "COP", "wallet", initial_balance="1000000")

    loan = auth.post(
        "/api/loans",
        json={
            "borrower": "Carlos",
            "account_id": fb["id"],
            "amount": "300",
            "start_date": "2026-10-01",
        },
    )
    assert loan.status_code == 201, loan.text
    lid = loan.json()["id"]

    summary = auth.get("/api/loans").json()
    assert D(summary["total_balance_base"]) == D("300.00")
    assert D(summary["items"][0]["balance"]) == D("300.00")

    accounts = {a["name"]: a for a in auth.get("/api/accounts").json()["accounts"]}
    assert D(accounts["Facebank"]["balance"]) == D("700")

    # Paying back in another currency is refused
    bad = auth.post(
        f"/api/loans/{lid}/payments",
        json={"account_id": nequi["id"], "amount": "10", "occurred_on": "2026-10-10"},
    )
    assert bad.status_code == 422

    ok = auth.post(
        f"/api/loans/{lid}/payments",
        json={"account_id": zinli["id"], "amount": "100", "occurred_on": "2026-10-10"},
    )
    assert ok.status_code == 201, ok.text
    item = auth.get("/api/loans").json()["items"][0]
    assert D(item["balance"]) == D("200.00")
    assert D(item["progress_pct"]) == D("33.33")

    # Cannot collect more than is owed
    assert (
        auth.post(
            f"/api/loans/{lid}/payments",
            json={"account_id": zinli["id"], "amount": "201", "occurred_on": "2026-10-11"},
        ).status_code
        == 422
    )

    # Cannot lend more than is free
    assert (
        auth.post(
            "/api/loans",
            json={
                "borrower": "Ana",
                "account_id": fb["id"],
                "amount": "701",
                "start_date": "2026-10-01",
            },
        ).status_code
        == 422
    )

    # Loan and payments do not count as income or spending
    plan = auth.get("/api/plan", params={"month": "2026-10-01"}).json()
    assert D(plan["costs_month"]) == D("0.00")
    assert D(plan["income_month"]) == D("0.00")

    # Loans in different currencies are added up in base currency, not by raw amount
    cop = make_account(auth, "Nequi 2", "COP", "wallet", initial_balance="1000000")
    auth.put(
        "/api/exchange-rates", json={"currency": "COP", "rate_date": "2026-10-01", "rate": "3900"}
    )
    luis = auth.post(
        "/api/loans",
        json={
            "borrower": "Luis",
            "account_id": cop["id"],
            "amount": "680000",
            "start_date": "2026-10-01",
        },
    )
    assert luis.status_code == 201, luis.text
    summary = auth.get("/api/loans").json()
    assert D(summary["principal_total_base"]) == D("474.36")  # 300 USD + 680000 COP at 3900
    assert D(summary["total_balance_base"]) == D(
        "374.36"
    )  # 200 USD + 680000 COP, nothing paid there

    # Deleting the loan undoes it
    assert auth.delete(f"/api/loans/{lid}").status_code == 204
    accounts = {a["name"]: a for a in auth.get("/api/accounts").json()["accounts"]}
    assert D(accounts["Facebank"]["balance"]) == D("1000")
    assert D(accounts["Zinli"]["balance"]) == D("0")
    assert auth.delete(f"/api/loans/{luis.json()['id']}").status_code == 204
    assert auth.get("/api/loans").json()["items"] == []
