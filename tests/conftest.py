import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

# Save real keys before clearing for dev-mode tests
_saved_stripe_key = os.environ.pop("STRIPE_SECRET_KEY", None)
_saved_webhook_secret = os.environ.pop("STRIPE_WEBHOOK_SECRET", None)
_saved_publishable_key = os.environ.get("STRIPE_PUBLISHABLE_KEY")

from viv_pay import init_pay


def get_saved_stripe_key():
    return _saved_stripe_key


def get_saved_publishable_key():
    return _saved_publishable_key


@pytest.fixture
def db_setup():
    """Create an in-memory SQLite engine with shared connection for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base = declarative_base()
    SessionLocal = sessionmaker(bind=engine)

    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    return engine, Base, get_db, SessionLocal


@pytest.fixture
def app_with_pay(db_setup):
    engine, Base, get_db, SessionLocal = db_setup
    app = FastAPI()

    create_checkout, get_customer, require_subscription = init_pay(
        app, engine, Base, get_db, app_name="TestApp"
    )

    return app, create_checkout, get_customer, require_subscription, engine, SessionLocal


@pytest.fixture
def client(app_with_pay):
    app = app_with_pay[0]
    return TestClient(app)


@pytest.fixture
def db_session(app_with_pay):
    SessionLocal = app_with_pay[5]
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
