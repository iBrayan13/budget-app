import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-123")
os.environ["ENVIRONMENT"] = "test"

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, make_url, text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, User  # noqa: E402

TEST_PASSWORD = "una-clave-segura-123"


def _ensure_test_database() -> str:
    settings = get_settings()
    url = make_url(settings.test_database_url)
    # drop_all runs on this database: never let it be the real one.
    assert url.database != settings.postgres_db, "POSTGRES_TEST_DB no puede ser la base real"
    server = create_engine(settings.maintenance_url, isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    server.dispose()
    return settings.test_database_url


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(_ensure_test_database())
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(engine) -> Iterator[Session]:
    """Each test runs inside a transaction that is rolled back at the end."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def user(db: Session) -> User:
    user = User(
        email="brayan@example.com", full_name="Brayan", hashed_password=hash_password(TEST_PASSWORD)
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def auth(client: TestClient, user: User) -> TestClient:
    """Client logged in as `user`."""
    res = client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert res.status_code == 200
    return client


@pytest.fixture
def other_user(db: Session) -> User:
    other = User(email="otro@example.com", hashed_password=hash_password(TEST_PASSWORD))
    db.add(other)
    db.commit()
    return other


def make_account(client: TestClient, name: str, currency: str, kind: str = "wallet", **extra):
    res = client.post(
        "/api/accounts", json={"name": name, "kind": kind, "currency": currency, **extra}
    )
    assert res.status_code == 201, res.text
    return res.json()


def make_category(client: TestClient, name: str, kind: str = "expense", level="essential"):
    body = {"name": name, "kind": kind, "level": level if kind == "expense" else None}
    res = client.post("/api/categories", json=body)
    assert res.status_code == 201, res.text
    return res.json()
