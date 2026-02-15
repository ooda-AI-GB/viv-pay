import json


def _post_webhook(client, event_type, data):
    event = {"type": event_type, "data": {"object": data}}
    return client.post(
        "/pay/webhook",
        content=json.dumps(event),
    )


def test_webhook_checkout_completed(client):
    # First create a customer via checkout
    client.post(
        "/pay/checkout",
        content=json.dumps({
            "user_id": 1,
            "email": "test@example.com",
            "price_id": "price_test",
        }),
    )

    resp = _post_webhook(client, "checkout.session.completed", {
        "id": "cs_test_123",
        "customer": "cus_dev_1",
        "mode": "subscription",
        "subscription": "sub_test_123",
        "amount_total": 2000,
        "currency": "usd",
        "metadata": {"price_id": "price_test"},
    })
    assert resp.status_code == 200
    assert resp.json()["received"] is True


def test_webhook_subscription_updated(client):
    # Create customer + subscription via checkout
    client.post(
        "/pay/checkout",
        content=json.dumps({
            "user_id": 2,
            "email": "sub@example.com",
            "price_id": "price_test",
        }),
    )
    _post_webhook(client, "checkout.session.completed", {
        "id": "cs_test_456",
        "customer": "cus_dev_2",
        "mode": "subscription",
        "subscription": "sub_test_456",
        "amount_total": 2000,
        "currency": "usd",
        "metadata": {"price_id": "price_test"},
    })

    # Now update it
    resp = _post_webhook(client, "customer.subscription.updated", {
        "id": "sub_test_456",
        "status": "past_due",
        "current_period_start": 1700000000,
        "current_period_end": 1702592000,
    })
    assert resp.status_code == 200


def test_webhook_subscription_deleted(client):
    client.post(
        "/pay/checkout",
        content=json.dumps({
            "user_id": 3,
            "email": "del@example.com",
            "price_id": "price_test",
        }),
    )
    _post_webhook(client, "checkout.session.completed", {
        "id": "cs_test_789",
        "customer": "cus_dev_3",
        "mode": "subscription",
        "subscription": "sub_test_789",
        "amount_total": 1000,
        "currency": "usd",
        "metadata": {"price_id": "price_test"},
    })

    resp = _post_webhook(client, "customer.subscription.deleted", {
        "id": "sub_test_789",
    })
    assert resp.status_code == 200


def test_webhook_unknown_event(client):
    resp = _post_webhook(client, "some.unknown.event", {"id": "evt_123"})
    assert resp.status_code == 200
    assert resp.json()["received"] is True


def test_webhook_invalid_payload(client):
    resp = client.post("/pay/webhook", content=b"not json")
    assert resp.status_code == 400
