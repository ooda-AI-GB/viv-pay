import logging

from fastapi import Request

from .config import PayConfig, is_dev_mode

logger = logging.getLogger("viv-pay")


class PaymentRequired(Exception):
    """Raised when user has no active subscription."""

    pass


class MockSubscription:
    """Returned in dev mode when no real subscription exists."""

    def __init__(self, user_id: int):
        self.id = 0
        self.customer_id = 0
        self.stripe_subscription_id = f"sub_dev_{user_id}"
        self.stripe_price_id = "price_dev"
        self.status = "active"
        self.current_period_start = None
        self.current_period_end = None
        self.cancel_at = None


def create_require_subscription(
    get_db, StripeCustomer, Subscription, config: PayConfig
):
    """Factory — creates FastAPI dependency that checks for active subscription."""

    async def require_subscription(
        request: Request, user_id: int | None = None
    ):
        # Try to get user_id from query param, header, or cookie
        if user_id is None:
            user_id = request.query_params.get("user_id")
        if user_id is None:
            user_id = request.headers.get("x-user-id")
        if user_id is None:
            user_id = request.cookies.get("user_id")

        if user_id is None:
            raise PaymentRequired()

        user_id = int(user_id)

        if is_dev_mode():
            logger.info(
                f"[viv-pay] DEV MODE — subscription check passed for user {user_id}"
            )
            return MockSubscription(user_id)

        db = next(get_db())
        try:
            customer = (
                db.query(StripeCustomer)
                .filter(StripeCustomer.user_id == user_id)
                .first()
            )
            if not customer:
                raise PaymentRequired()

            sub = (
                db.query(Subscription)
                .filter(
                    Subscription.customer_id == customer.id,
                    Subscription.status.in_(config.allowed_statuses),
                )
                .first()
            )
            if not sub:
                raise PaymentRequired()

            return sub
        finally:
            db.close()

    return require_subscription
