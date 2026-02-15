from fastapi import Depends


def test_require_subscription_dev_mode_passes(app_with_pay, client):
    app, _, _, require_subscription, _, _ = app_with_pay

    @app.get("/test-premium")
    async def premium(sub=Depends(require_subscription)):
        return {"status": sub.status, "sub_id": sub.stripe_subscription_id}

    resp = client.get("/test-premium?user_id=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert "sub_dev_1" in data["sub_id"]


def test_require_subscription_no_user_id_raises(app_with_pay, client):
    app, _, _, require_subscription, _, _ = app_with_pay

    @app.get("/api/test-locked")
    async def locked(sub=Depends(require_subscription)):
        return {"ok": True}

    resp = client.get("/api/test-locked")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Subscription required"


def test_payment_required_html_redirect(app_with_pay, client):
    app, _, _, require_subscription, _, _ = app_with_pay

    @app.get("/locked-page")
    async def locked_page(sub=Depends(require_subscription)):
        return {"ok": True}

    resp = client.get("/locked-page")
    assert resp.status_code == 403
    assert "/pay/checkout" in resp.text


def test_payment_required_api_json(app_with_pay, client):
    app, _, _, require_subscription, _, _ = app_with_pay

    @app.get("/api/locked")
    async def api_locked(sub=Depends(require_subscription)):
        return {"ok": True}

    resp = client.get("/api/locked")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Subscription required"


def test_success_page_renders(client):
    resp = client.get("/pay/success")
    assert resp.status_code == 200
    assert "Payment Successful" in resp.text
    assert "TestApp" in resp.text


def test_cancel_page_renders(client):
    resp = client.get("/pay/cancel")
    assert resp.status_code == 200
    assert "Payment Cancelled" in resp.text
    assert "TestApp" in resp.text


def test_pay_config_endpoint(client):
    resp = client.get("/pay/config")
    assert resp.status_code == 200
    assert "publishable_key" in resp.json()


def test_portal_requires_user_id(client):
    import json
    resp = client.post("/pay/portal", content=json.dumps({}))
    assert resp.status_code == 400


def test_portal_unknown_user(client):
    import json
    resp = client.post(
        "/pay/portal",
        content=json.dumps({"user_id": 999}),
    )
    assert resp.status_code == 404
