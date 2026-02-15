import logging

from .config import is_dev_mode

logger = logging.getLogger("viv-pay")


def create_portal_helper(get_customer, app_url: str):
    """Factory — creates customer portal session helper."""

    def create_portal_session(
        db,
        user_id: int,
        return_url: str | None = None,
    ) -> str | None:
        """Create a Stripe Customer Portal session. Returns the portal URL."""
        customer = get_customer(db, user_id)
        if not customer:
            logger.warning(f"[viv-pay] Portal requested for unknown user {user_id}")
            return None

        effective_return_url = return_url or app_url

        if is_dev_mode():
            fake_url = f"{app_url}/pay/portal-dev?customer={customer.stripe_customer_id}"
            logger.info(
                f"[viv-pay] DEV MODE — mock portal for user {user_id}: {fake_url}"
            )
            return fake_url

        import stripe

        session = stripe.billing_portal.Session.create(
            customer=customer.stripe_customer_id,
            return_url=effective_return_url,
        )

        logger.info(f"[viv-pay] Portal session created for user {user_id}")
        return session.url

    return create_portal_session
