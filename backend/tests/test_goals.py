from datetime import date
from decimal import Decimal

from tests.conftest import make_account

D = Decimal
TODAY = date.today().isoformat()


def _emergency_id(auth):
    plan = auth.get("/api/plan").json()
    return next(g["id"] for g in plan["goals"] if g["kind"] == "emergency_fund")


def _allocate(auth, goal_id, account, amount):
    return auth.post(
        f"/api/goals/{goal_id}/allocations",
        json={"account_id": account["id"], "amount": amount, "allocated_on": TODAY},
    )


def test_cannot_reserve_more_than_the_platform_has(auth):
    nequi = make_account(auth, "Nequi", "COP", initial_balance="100000")
    res = _allocate(auth, _emergency_id(auth), nequi, "100001")
    assert res.status_code == 422
    assert _allocate(auth, _emergency_id(auth), nequi, "100000").status_code == 201
    assert _allocate(auth, _emergency_id(auth), nequi, "1").status_code == 422


def test_cannot_release_more_than_the_goal_holds(auth):
    binance = make_account(auth, "Binance", "USDT", "exchange", initial_balance="500")
    car = auth.post("/api/goals", json={"name": "Carro", "target_amount": "10000"}).json()
    assert _allocate(auth, car["id"], binance, "200").status_code == 201
    assert _allocate(auth, _emergency_id(auth), binance, "100").status_code == 201
    # 100 is in the emergency fund: the car can only release its own 200
    assert _allocate(auth, car["id"], binance, "-250").status_code == 422
    assert _allocate(auth, car["id"], binance, "-200").status_code == 201


def test_reserved_money_is_not_free(auth):
    fb = make_account(auth, "Facebank", "USD", "bank", initial_balance="1000")
    goal = auth.post("/api/goals", json={"name": "PC", "target_amount": "1500"}).json()
    _allocate(auth, goal["id"], fb, "400")
    plan = auth.get("/api/plan").json()
    assert D(plan["accounts_total"]) == D("1000.00")
    assert D(plan["free"]) == D("600.00")
    pc = next(g for g in plan["goals"] if g["id"] == goal["id"])
    assert D(pc["remaining"]) == D("1100.00")
    assert D(pc["progress_pct"]) == D("26.67")


def test_deleting_an_allocation_frees_the_money(auth):
    fb = make_account(auth, "Facebank", "USD", "bank", initial_balance="1000")
    goal = auth.post("/api/goals", json={"name": "PC", "target_amount": "1500"}).json()
    alloc = _allocate(auth, goal["id"], fb, "400").json()
    assert auth.delete(f"/api/goal-allocations/{alloc['id']}").status_code == 204
    assert D(auth.get("/api/plan").json()["free"]) == D("1000.00")


def test_cannot_archive_platform_with_reserved_money(auth):
    fb = make_account(auth, "Facebank", "USD", "bank", initial_balance="1000")
    _allocate(auth, _emergency_id(auth), fb, "100")
    res = auth.patch(f"/api/accounts/{fb['id']}", json={"is_active": False})
    assert res.status_code == 409


def test_emergency_fund_cannot_be_deleted_or_renamed(auth):
    eid = _emergency_id(auth)
    assert auth.delete(f"/api/goals/{eid}").status_code == 409
    body = {"name": "Otro", "target_amount": "10"}
    assert auth.put(f"/api/goals/{eid}", json=body).status_code == 409


def test_savings_goal_crud_and_allocation_list(auth):
    fb = make_account(auth, "Facebank", "USD", "bank", initial_balance="1000")
    goal = auth.post(
        "/api/goals", json={"name": "Moto", "target_amount": "3000", "target_date": "2027-06-30"}
    ).json()
    _allocate(auth, goal["id"], fb, "100")
    rows = auth.get(f"/api/goals/{goal['id']}/allocations").json()
    assert len(rows) == 1 and rows[0]["account_name"] == "Facebank"

    plan = auth.get("/api/plan").json()
    moto = next(g for g in plan["goals"] if g["id"] == goal["id"])
    assert D(moto["monthly_needed"]) > 0

    assert auth.delete(f"/api/goals/{goal['id']}").status_code == 204
    assert auth.get(f"/api/goals/{goal['id']}/allocations").status_code == 404
