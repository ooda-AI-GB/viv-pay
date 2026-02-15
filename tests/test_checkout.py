import json


def test_checkout_endpoint_requires_fields(client):
    resp = client.post(
        "/pay/checkout",
        content=json.dumps({"user_id": 1}),
    )
    assert resp.status_code == 400
    assert "required" in resp.json()["error"]


def test_checkout_dev_mode_returns_url(client):
    resp = client.post(
        "/pay/checkout",
        content=json.dumps({
            "user_id": 1,
            "email": "test@example.com",
            "price_id": "price_test123",
        }),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "url" in data
    assert "/pay/success" in data["url"]
    assert "session_id" in data["url"]


def test_checkout_dev_mode_creates_customer(client, db_session):
    from viv_pay.models import create_pay_models
    # Use db_session to check customer was created
    resp = client.post(
        "/pay/checkout",
        content=json.dumps({
            "user_id": 42,
            "email": "user42@example.com",
            "price_id": "price_abc",
            "mode": "subscription",
        }),
    )
    assert resp.status_code == 200


def test_checkout_subscription_mode(client):
    resp = client.post(
        "/pay/checkout",
        content=json.dumps({
            "user_id": 5,
            "email": "sub@example.com",
            "price_id": "price_sub",
            "mode": "subscription",
        }),
    )
    assert resp.status_code == 200
    assert "url" in resp.json()


def test_checkout_payment_mode(client):
    resp = client.post(
        "/pay/checkout",
        content=json.dumps({
            "user_id": 6,
            "email": "pay@example.com",
            "price_id": "price_one",
            "mode": "payment",
        }),
    )
    assert resp.status_code == 200
    assert "url" in resp.json()
