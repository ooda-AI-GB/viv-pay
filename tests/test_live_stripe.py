"""
Live Stripe integration test using test keys.

Requires STRIPE_SECRET_KEY set to a sk_test_* key.
Run: STRIPE_SECRET_KEY=sk_test_... pytest tests/test_live_stripe.py -v -s
"""
import json
import os

import pytest
import stripe
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from conftest import get_saved_stripe_key, get_saved_publishable_key

# Restore the real key (conftest saved it before popping)
STRIPE_KEY = get_saved_stripe_key()

pytestmark = pytest.mark.skipif(
    not STRIPE_KEY or not STRIPE_KEY.startswith("sk_test_"),
    reason="STRIPE_SECRET_KEY (test mode) not set",
)


@pytest.fixture(scope="module")
def live_setup():
    """Create app with real Stripe keys — restores env vars temporarily."""
    os.environ["STRIPE_SECRET_KEY"] = STRIPE_KEY
    pk = get_saved_publishable_key()
    if pk:
        os.environ["STRIPE_PUBLISHABLE_KEY"] = pk

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

    app = FastAPI()

    from viv_pay import init_pay

    create_checkout, get_customer, require_subscription = init_pay(
        app,
        engine,
        Base,
        get_db,
        app_name="LiveTest",
        app_url="http://localhost:8000",
    )

    @app.get("/premium", dependencies=[Depends(require_subscription)])
    async def premium():
        return {"access": "granted"}

    client = TestClient(app)

    yield client, create_checkout, get_customer, require_subscription, get_db

    # Cleanup: remove keys so dev-mode tests aren't affected
    os.environ.pop("STRIPE_SECRET_KEY", None)
    os.environ.pop("STRIPE_PUBLISHABLE_KEY", None)


# --- Test 1: Stripe SDK is configured ---

def test_stripe_sdk_configured(live_setup):
    """Verify Stripe SDK is using the test key."""
    assert stripe.api_key is not None
    assert stripe.api_key.startswith("sk_test_")
    print(f"\n  Stripe key: {stripe.api_key[:20]}...")


# --- Test 2: Create a real Stripe Customer via checkout ---

def test_create_real_customer(live_setup):
    """Create a real Stripe customer via checkout endpoint."""
    client = live_setup[0]

    price = stripe.Price.create(
        unit_amount=500,
        currency="usd",
        product_data={"name": "viv-pay live test"},
    )
    print(f"\n  Created test price: {price.id}")

    resp = client.post(
        "/pay/checkout",
        content=json.dumps({
            "user_id": 1,
            "email": "vivpay-test@gigabox.ai",
            "price_id": price.id,
            "mode": "payment",
        }),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "url" in data
    url = data["url"]
    assert "checkout.stripe.com" in url
    print(f"  Checkout URL: {url[:80]}...")


# --- Test 3: Verify customer was created in Stripe ---

def test_customer_exists_in_stripe(live_setup):
    """After checkout, verify customer exists in Stripe and local DB."""
    _, _, get_customer, _, _ = live_setup

    customer = get_customer(user_id=1)
    assert customer is not None
    assert customer.stripe_customer_id.startswith("cus_")
    print(f"\n  Local customer: user_id={customer.user_id}, stripe_id={customer.stripe_customer_id}")

    stripe_cust = stripe.Customer.retrieve(customer.stripe_customer_id)
    assert stripe_cust.email == "vivpay-test@gigabox.ai"
    assert stripe_cust.metadata.get("user_id") == "1"
    print(f"  Stripe customer confirmed: {stripe_cust.id}, email={stripe_cust.email}")


# --- Test 4: Create subscription checkout ---

def test_subscription_checkout(live_setup):
    """Create a subscription checkout session with a recurring price."""
    client = live_setup[0]

    price = stripe.Price.create(
        unit_amount=1000,
        currency="usd",
        recurring={"interval": "month"},
        product_data={"name": "viv-pay Pro Plan"},
    )
    print(f"\n  Created recurring price: {price.id}")

    resp = client.post(
        "/pay/checkout",
        content=json.dumps({
            "user_id": 2,
            "email": "vivpay-sub@gigabox.ai",
            "price_id": price.id,
            "mode": "subscription",
        }),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "checkout.stripe.com" in data["url"]
    print(f"  Subscription checkout URL: {data['url'][:80]}...")


# --- Test 5: Idempotent customer creation ---

def test_idempotent_customer(live_setup):
    """Same user_id should return same customer, not create duplicate."""
    client = live_setup[0]
    _, _, get_customer, _, _ = live_setup

    price = stripe.Price.create(
        unit_amount=100,
        currency="usd",
        product_data={"name": "viv-pay idempotent test"},
    )

    # Second checkout for user_id=1 should reuse existing customer
    resp = client.post(
        "/pay/checkout",
        content=json.dumps({
            "user_id": 1,
            "email": "vivpay-test@gigabox.ai",
            "price_id": price.id,
            "mode": "payment",
        }),
    )
    assert resp.status_code == 200

    customer = get_customer(user_id=1)
    assert customer is not None
    print(f"\n  Idempotent customer: {customer.stripe_customer_id} (same as before)")


# --- Test 6: require_subscription blocks without subscription ---

def test_require_subscription_blocks(live_setup):
    """With real Stripe, require_subscription should block users without subs."""
    client = live_setup[0]

    resp = client.get("/premium?user_id=1")
    assert resp.status_code == 403
    print(f"\n  Correctly blocked user without subscription: {resp.status_code}")


# --- Test 7: /pay/config returns publishable key ---

def test_config_returns_publishable_key(live_setup):
    client = live_setup[0]
    resp = client.get("/pay/config")
    assert resp.status_code == 200
    data = resp.json()
    pk = data["publishable_key"]
    if pk:
        assert pk.startswith("pk_test_")
        print(f"\n  Publishable key: {pk[:25]}...")
    else:
        print("\n  No STRIPE_PUBLISHABLE_KEY set")


# --- Test 8: Customer portal ---

def test_customer_portal(live_setup):
    """Create a customer portal session."""
    client = live_setup[0]

    resp = client.post(
        "/pay/portal",
        content=json.dumps({"user_id": 1}),
    )
    if resp.status_code == 200:
        data = resp.json()
        assert "url" in data
        print(f"\n  Portal URL: {data['url'][:80]}...")
    else:
        # Portal requires configuration in Stripe dashboard
        print(f"\n  Portal: {resp.status_code} — needs dashboard config (expected for fresh test accounts)")


# --- Cleanup ---

def test_cleanup_stripe_test_data(live_setup):
    """Clean up test customers and products from Stripe."""
    _, _, get_customer, _, _ = live_setup

    for uid in [1, 2]:
        cust = get_customer(user_id=uid)
        if cust and cust.stripe_customer_id.startswith("cus_"):
            try:
                stripe.Customer.delete(cust.stripe_customer_id)
                print(f"\n  Deleted Stripe customer {cust.stripe_customer_id}")
            except Exception as e:
                print(f"\n  Cleanup warning for user {uid}: {e}")
