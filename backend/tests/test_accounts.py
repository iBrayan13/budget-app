from decimal import Decimal

from app.models import Account
from tests.conftest import make_account, make_category


def balances(client):
    data = client.get("/api/accounts").json()
    return data, {a["name"]: a for a in data["accounts"]}


def test_seed_defaults_is_idempotent(auth):
    first = auth.post("/api/setup/defaults").json()
    assert first == {"accounts": 6, "categories": 23}
    assert auth.post("/api/setup/defaults").json() == {"accounts": 0, "categories": 0}

    _, by_name = balances(auth)
    assert by_name["Nequi"]["currency"] == "COP"
    assert by_name["Binance"]["currency"] == "USDT"


def test_duplicate_account_name_conflict(auth):
    make_account(auth, "Zinli", "usd")
    res = auth.post("/api/accounts", json={"name": "Zinli", "kind": "wallet", "currency": "USD"})
    assert res.status_code == 409


def test_balance_combines_transactions_and_transfers(auth):
    fb = make_account(auth, "Facebank", "USD", "bank", initial_balance="1000")
    nequi = make_account(auth, "Nequi", "COP")
    salary = make_category(auth, "Salario", kind="income")
    food = make_category(auth, "Mercado")

    def tx(account, kind, amount, category=None):
        body = {
            "account_id": account["id"],
            "kind": kind,
            "amount": amount,
            "occurred_on": "2026-10-01",
            "category_id": category["id"] if category else None,
        }
        assert auth.post("/api/transactions", json=body).status_code == 201

    tx(fb, "income", "500", salary)
    tx(fb, "expense", "120.50", food)
    tx(fb, "adjustment", "-0.50")
    res = auth.post(
        "/api/transfers",
        json={
            "from_account_id": fb["id"],
            "to_account_id": nequi["id"],
            "amount_out": "100",
            "amount_in": "395000",
            "occurred_on": "2026-10-02",
        },
    )
    assert res.status_code == 201

    data, by_name = balances(auth)
    assert Decimal(by_name["Facebank"]["balance"]) == Decimal("1279")
    assert Decimal(by_name["Nequi"]["balance"]) == Decimal("395000")
    # Without a COP rate the Nequi balance cannot be valued in USD.
    assert by_name["Nequi"]["balance_base"] is None
    assert data["accounts_without_rate"] == ["Nequi"]

    auth.put(
        "/api/exchange-rates", json={"currency": "COP", "rate_date": "2026-10-01", "rate": 4000}
    )
    data, by_name = balances(auth)
    assert Decimal(by_name["Nequi"]["balance_base"]) == Decimal("98.75")
    assert Decimal(data["total_base"]) == Decimal("1377.75")
    assert data["accounts_without_rate"] == []


def test_account_with_movements_cannot_be_deleted(auth):
    acc = make_account(auth, "Binance", "USDT", "exchange")
    auth.post(
        "/api/transactions",
        json={
            "account_id": acc["id"],
            "kind": "adjustment",
            "amount": "5",
            "occurred_on": "2026-10-01",
        },
    )
    assert auth.delete(f"/api/accounts/{acc['id']}").status_code == 409

    assert auth.patch(f"/api/accounts/{acc['id']}", json={"is_active": False}).status_code == 200
    _, by_name = balances(auth)
    assert "Binance" not in by_name


def test_cannot_touch_other_users_account(auth, db, other_user):
    foreign = Account(user_id=other_user.id, name="Ajena", kind="wallet", currency="USD")
    db.add(foreign)
    db.commit()

    assert auth.patch(f"/api/accounts/{foreign.id}", json={"name": "Mía"}).status_code == 404
    assert auth.delete(f"/api/accounts/{foreign.id}").status_code == 404
    res = auth.post(
        "/api/transactions",
        json={
            "account_id": foreign.id,
            "kind": "adjustment",
            "amount": "5",
            "occurred_on": "2026-10-01",
        },
    )
    assert res.status_code == 404
    assert balances(auth)[1] == {}


def test_requires_login(client):
    assert client.get("/api/accounts").status_code == 401


def test_load_categories_works_with_platforms_created_by_hand(auth):
    make_account(auth, "Nequi", "COP")
    assert auth.post("/api/setup/categories").json() == {"categories": 23}
    assert auth.post("/api/setup/categories").json() == {"categories": 0}
    assert len(auth.get("/api/categories").json()) == 23
