from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String


def utcnow():
    return datetime.now(timezone.utc)


def create_pay_models(Base):
    """Factory — creates payment models bound to the app's Base."""

    class StripeCustomer(Base):
        __tablename__ = "stripe_customers"

        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, nullable=False, unique=True, index=True)
        email = Column(String, nullable=False)
        stripe_customer_id = Column(
            String, unique=True, nullable=False, index=True
        )
        created_at = Column(DateTime(timezone=True), default=utcnow)

    class Subscription(Base):
        __tablename__ = "subscriptions"

        id = Column(Integer, primary_key=True)
        customer_id = Column(
            Integer, ForeignKey("stripe_customers.id"), nullable=False
        )
        stripe_subscription_id = Column(
            String, unique=True, nullable=False, index=True
        )
        stripe_price_id = Column(String, nullable=False)
        status = Column(String, nullable=False, default="incomplete")
        current_period_start = Column(DateTime(timezone=True), nullable=True)
        current_period_end = Column(DateTime(timezone=True), nullable=True)
        cancel_at = Column(DateTime(timezone=True), nullable=True)
        created_at = Column(DateTime(timezone=True), default=utcnow)
        updated_at = Column(
            DateTime(timezone=True), default=utcnow, onupdate=utcnow
        )

    class Payment(Base):
        __tablename__ = "payments"

        id = Column(Integer, primary_key=True)
        customer_id = Column(
            Integer, ForeignKey("stripe_customers.id"), nullable=False
        )
        stripe_session_id = Column(String, unique=True, nullable=True)
        stripe_payment_intent_id = Column(
            String, unique=True, nullable=True
        )
        amount_cents = Column(Integer, nullable=False)
        currency = Column(String(3), nullable=False, default="usd")
        status = Column(String, nullable=False, default="pending")
        mode = Column(String, nullable=False, default="payment")
        created_at = Column(DateTime(timezone=True), default=utcnow)

    return StripeCustomer, Subscription, Payment
