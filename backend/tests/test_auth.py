from tests.conftest import TEST_PASSWORD


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_me_requires_login(client):
    assert client.get("/api/auth/me").status_code == 401


def test_login_sets_httponly_cookie_and_me_works(client, user):
    res = client.post(
        "/api/auth/login", json={"email": "Brayan@Example.com", "password": TEST_PASSWORD}
    )
    assert res.status_code == 200
    assert res.json()["base_currency"] == "USD"
    assert res.json()["emergency_fund_months"] == 6
    assert "httponly" in res.headers["set-cookie"].lower()

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "brayan@example.com"


def test_login_wrong_password(client, user):
    res = client.post("/api/auth/login", json={"email": user.email, "password": "incorrecta"})
    assert res.status_code == 401


def test_login_unknown_email(client):
    res = client.post("/api/auth/login", json={"email": "nadie@example.com", "password": "x"})
    assert res.status_code == 401


def test_logout_clears_session(client, user):
    client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_tampered_token_rejected(client, user):
    client.cookies.set("budget_session", "not-a-jwt")
    assert client.get("/api/auth/me").status_code == 401
