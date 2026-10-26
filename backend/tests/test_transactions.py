from decimal import Decimal

from tests.conftest import make_account, make_category


def post_tx(client, **body):
    body.setdefault("occurred_on", "2026-10-05")
    return client.post("/api/transactions", json=body)


def test_expense_requires_category(auth):
    acc = make_account(auth, "Nequi", "COP")
    res = post_tx(auth, account_id=acc["id"], kind="expense", amount="10000")
    assert res.status_code == 422


def test_category_kind_must_match(auth):
    acc = make_account(auth, "Nequi", "COP")
    income_cat = make_category(auth, "Salario", kind="income")
    res = post_tx(
        auth, account_id=acc["id"], kind="expense", amount="10000", category_id=income_cat["id"]
    )
    assert res.status_code == 422


def test_negative_amount_only_for_adjustments(auth):
    acc = make_account(auth, "Nequi", "COP")
    cat = make_category(auth, "Salario", kind="income")
    bad = post_tx(auth, account_id=acc["id"], kind="income", amount="-5", category_id=cat["id"])
    assert bad.status_code == 422
    ok = post_tx(auth, account_id=acc["id"], kind="adjustment", amount="-5")
    assert ok.status_code == 201


def test_amount_base_uses_own_rate_or_reference(auth):
    acc = make_account(auth, "Nequi", "COP")
    cat = make_category(auth, "Mercado")
    auth.put(
        "/api/exchange-rates", json={"currency": "COP", "rate_date": "2026-10-01", "rate": 4000}
    )
    auth.put(
        "/api/exchange-rates", json={"currency": "COP", "rate_date": "2026-10-10", "rate": 5000}
    )

    # Reference rate: latest on or before the date (Oct 1 -> 4000)
    t1 = post_tx(auth, account_id=acc["id"], kind="expense", amount="80000", category_id=cat["id"])
    assert Decimal(t1.json()["amount_base"]) == Decimal("20.00")
    assert t1.json()["currency"] == "COP"

    # Explicit rate on the movement wins
    t2 = post_tx(
        auth,
        account_id=acc["id"],
        kind="expense",
        amount="80000",
        category_id=cat["id"],
        fx_rate="3200",
    )
    assert Decimal(t2.json()["amount_base"]) == Decimal("25.00")

    # Before any rate exists, the earliest one is used
    t3 = post_tx(
        auth,
        account_id=acc["id"],
        kind="expense",
        amount="40000",
        category_id=cat["id"],
        occurred_on="2026-09-01",
    )
    assert Decimal(t3.json()["amount_base"]) == Decimal("10.00")


def test_list_filters_and_update(auth):
    acc = make_account(auth, "Zinli", "USD")
    food = make_category(auth, "Mercado")
    fun = make_category(auth, "Cine", level="lifestyle")
    t = post_tx(auth, account_id=acc["id"], kind="expense", amount="10", category_id=food["id"])
    post_tx(
        auth,
        account_id=acc["id"],
        kind="expense",
        amount="20",
        category_id=fun["id"],
        occurred_on="2026-11-01",
    )

    october = auth.get("/api/transactions", params={"start": "2026-10-01", "end": "2026-10-31"})
    assert [x["amount"] for x in october.json()] == ["10.00000000"]

    res = auth.put(
        f"/api/transactions/{t.json()['id']}",
        json={
            "account_id": acc["id"],
            "kind": "expense",
            "amount": "12",
            "occurred_on": "2026-10-05",
            "category_id": fun["id"],
        },
    )
    assert res.status_code == 200
    assert auth.get("/api/transactions", params={"category_id": fun["id"]}).json().__len__() == 2

    assert auth.delete(f"/api/transactions/{t.json()['id']}").status_code == 204
    assert len(auth.get("/api/transactions").json()) == 1


def test_category_in_use_cannot_be_deleted(auth):
    acc = make_account(auth, "Zinli", "USD")
    cat = make_category(auth, "Mercado")
    post_tx(auth, account_id=acc["id"], kind="expense", amount="10", category_id=cat["id"])
    assert auth.delete(f"/api/categories/{cat['id']}").status_code == 409
    unused = make_category(auth, "Otro")
    assert auth.delete(f"/api/categories/{unused['id']}").status_code == 204


def test_expense_category_needs_level(auth):
    res = auth.post("/api/categories", json={"name": "X", "kind": "expense"})
    assert res.status_code == 422
