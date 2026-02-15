import logging
import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.engine import Engine

from .checkout import create_checkout_helper
from .config import PayConfig, get_stripe_publishable_key, is_dev_mode
from .customer import create_customer_helpers
from .middleware import PaymentRequired, create_require_subscription
from .models import create_pay_models
from .portal import create_portal_helper
from .webhooks import create_webhook_handler

logger = logging.getLogger("viv-pay")

TEMPLATES_DIR = Path(__file__).parent / "templates"


def init_pay(
    app,
    engine: Engine,
    Base,
    get_db,
    app_name: str = "App",
    app_url: str | None = None,
    config: PayConfig | None = None,
):
    """Initialize viv-pay on a FastAPI app.

    Returns (create_checkout, get_customer, require_subscription).
    """
    config = config or PayConfig()

    if app_url is None:
        app_url = os.environ.get("APP_URL", "http://localhost:8000")
    app_url = app_url.rstrip("/")

    # 1. Configure Stripe SDK
    if not is_dev_mode():
        import stripe

        stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
        logger.info("[viv-pay] Stripe configured (live mode)")
    else:
        logger.info("[viv-pay] DEV MODE — Stripe not configured, using mocks")

    # 2. Create models
    StripeCustomer, Subscription, Payment = create_pay_models(Base)

    # 3. Create helpers (take db as first arg)
    get_customer, get_or_create_customer = create_customer_helpers(StripeCustomer)
    _create_checkout = create_checkout_helper(get_or_create_customer, config, app_url)
    _create_portal = create_portal_helper(get_customer, app_url)
    require_subscription = create_require_subscription(
        get_db, StripeCustomer, Subscription, config
    )

    # Public wrappers that manage their own DB session
    def create_checkout(user_id, email, price_id, mode="subscription", metadata=None):
        db = next(get_db())
        try:
            return _create_checkout(db, user_id, email, price_id, mode, metadata)
        finally:
            db.close()

    def get_customer_public(user_id):
        db = next(get_db())
        try:
            return get_customer(db, user_id)
        finally:
            db.close()

    # 4. Mount routes
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    router = APIRouter()

    @router.post("/pay/checkout")
    async def checkout_endpoint(request: Request):
        body = await request.json()
        user_id = body.get("user_id")
        email = body.get("email")
        price_id = body.get("price_id")
        mode = body.get("mode", "subscription")
        metadata = body.get("metadata")

        if not all([user_id, email, price_id]):
            return JSONResponse(
                {"error": "user_id, email, and price_id are required"},
                status_code=400,
            )

        db = next(get_db())
        try:
            url = _create_checkout(
                db,
                user_id=int(user_id),
                email=email,
                price_id=price_id,
                mode=mode,
                metadata=metadata,
            )
        finally:
            db.close()
        return JSONResponse({"url": url})

    webhook_handler = create_webhook_handler(
        get_db, StripeCustomer, Subscription, Payment
    )

    @router.post(config.webhook_path)
    async def webhook_endpoint(request: Request):
        return await webhook_handler(request)

    @router.post("/pay/portal")
    async def portal_endpoint(request: Request):
        body = await request.json()
        user_id = body.get("user_id")
        return_url = body.get("return_url")

        if not user_id:
            return JSONResponse(
                {"error": "user_id is required"}, status_code=400
            )

        db = next(get_db())
        try:
            url = _create_portal(db, user_id=int(user_id), return_url=return_url)
        finally:
            db.close()
        if not url:
            return JSONResponse(
                {"error": "customer not found"}, status_code=404
            )
        return JSONResponse({"url": url})

    @router.get(config.success_path)
    async def success_page(request: Request):
        return templates.TemplateResponse(
            request, "pay/success.html", {"app_name": app_name}
        )

    @router.get(config.cancel_path)
    async def cancel_page(request: Request):
        return templates.TemplateResponse(
            request, "pay/cancel.html", {"app_name": app_name}
        )

    @router.get("/pay/config")
    async def pay_config():
        return JSONResponse(
            {"publishable_key": get_stripe_publishable_key() or ""}
        )

    app.include_router(router)

    # 5. Register exception handler
    @app.exception_handler(PaymentRequired)
    async def payment_required_handler(request: Request, exc: PaymentRequired):
        if request.url.path.startswith("/api"):
            return JSONResponse(
                {"detail": "Subscription required"}, status_code=403
            )
        return HTMLResponse(
            content=(
                '<html><body><script>window.location.href="/pay/checkout";</script>'
                '<p>Redirecting to checkout...</p></body></html>'
            ),
            status_code=403,
        )

    # 6. Create tables
    Base.metadata.create_all(bind=engine)
    logger.info(f"[viv-pay] Initialized for {app_name}")

    return create_checkout, get_customer_public, require_subscription
