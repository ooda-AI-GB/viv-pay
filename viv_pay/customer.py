import logging

from .config import is_dev_mode

logger = logging.getLogger("viv-pay")


def create_customer_helpers(StripeCustomer):
    """Factory — creates customer CRUD helpers."""

    def get_customer(db, user_id: int):
        """Look up a StripeCustomer by user_id."""
        return (
            db.query(StripeCustomer)
            .filter(StripeCustomer.user_id == user_id)
            .first()
        )

    def get_or_create_customer(db, user_id: int, email: str):
        """Get existing or create new StripeCustomer."""
        customer = (
            db.query(StripeCustomer)
            .filter(StripeCustomer.user_id == user_id)
            .first()
        )
        if customer:
            return customer

        if is_dev_mode():
            stripe_customer_id = f"cus_dev_{user_id}"
            logger.info(
                f"[viv-pay] DEV MODE — created mock customer "
                f"{stripe_customer_id} for user {user_id}"
            )
        else:
            import stripe

            stripe_cust = stripe.Customer.create(
                email=email,
                metadata={"user_id": str(user_id)},
            )
            stripe_customer_id = stripe_cust.id
            logger.info(
                f"[viv-pay] Created Stripe customer "
                f"{stripe_customer_id} for user {user_id}"
            )

        customer = StripeCustomer(
            user_id=user_id,
            email=email,
            stripe_customer_id=stripe_customer_id,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer

    return get_customer, get_or_create_customer
