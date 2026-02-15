import logging

from .config import PayConfig, is_dev_mode

logger = logging.getLogger("viv-pay")


def create_checkout_helper(get_or_create_customer, config: PayConfig, app_url: str):
    """Factory — creates checkout session helper."""

    def create_checkout(
        db,
        user_id: int,
        email: str,
        price_id: str,
        mode: str = "subscription",
        metadata: dict | None = None,
    ) -> str:
        """Create a Stripe Checkout Session. Returns the checkout URL."""
        customer = get_or_create_customer(db, user_id, email)

        if is_dev_mode():
            fake_url = f"{app_url}{config.success_path}?session_id=cs_dev_{user_id}"
            logger.info(
                f"[viv-pay] DEV MODE — mock checkout for user {user_id}, "
                f"price {price_id}, mode {mode}"
            )
            logger.info(f"[viv-pay] DEV MODE — checkout URL: {fake_url}")
            return fake_url

        import stripe

        session_metadata = {"user_id": str(user_id)}
        if metadata:
            session_metadata.update(metadata)

        session = stripe.checkout.Session.create(
            customer=customer.stripe_customer_id,
            mode=mode,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{app_url}{config.success_path}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{app_url}{config.cancel_path}",
            metadata=session_metadata,
        )

        logger.info(
            f"[viv-pay] Created checkout session {session.id} for user {user_id}"
        )
        return session.url

    return create_checkout
