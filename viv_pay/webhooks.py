import json
import logging
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse

from .config import get_stripe_webhook_secret, is_dev_mode

logger = logging.getLogger("viv-pay")


def create_webhook_handler(get_db, StripeCustomer, Subscription, Payment):
    """Factory — creates the Stripe webhook endpoint handler."""

    async def handle_stripe_webhook(request: Request):
        payload = await request.body()
        sig = request.headers.get("stripe-signature")

        if is_dev_mode():
            try:
                event = json.loads(payload)
            except (json.JSONDecodeError, Exception):
                logger.warning("[viv-pay] DEV MODE — invalid webhook payload")
                return JSONResponse({"error": "invalid payload"}, status_code=400)
            logger.info(
                f"[viv-pay] DEV MODE — webhook received: {event.get('type', 'unknown')}"
            )
        else:
            import stripe

            webhook_secret = get_stripe_webhook_secret()
            if not webhook_secret:
                logger.error("[viv-pay] STRIPE_WEBHOOK_SECRET not set")
                return JSONResponse(
                    {"error": "webhook not configured"}, status_code=500
                )
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig, webhook_secret
                )
            except stripe.SignatureVerificationError:
                logger.warning("[viv-pay] Webhook signature verification failed")
                return JSONResponse({"error": "invalid signature"}, status_code=400)

        event_type = event.get("type", "") if isinstance(event, dict) else event["type"]
        data_obj = event.get("data", {}).get("object", {}) if isinstance(event, dict) else event["data"]["object"]

        db = next(get_db())
        try:
            if event_type == "checkout.session.completed":
                _handle_checkout_completed(db, data_obj, StripeCustomer, Subscription, Payment)
            elif event_type == "customer.subscription.updated":
                _handle_subscription_updated(db, data_obj, Subscription)
            elif event_type == "customer.subscription.deleted":
                _handle_subscription_deleted(db, data_obj, Subscription)
            elif event_type == "invoice.payment_failed":
                _handle_payment_failed(db, data_obj, StripeCustomer, Subscription)
            elif event_type == "charge.refunded":
                _handle_refund(db, data_obj, StripeCustomer, Payment)
            else:
                logger.info(f"[viv-pay] Unhandled webhook event: {event_type}")
        except Exception:
            logger.exception(f"[viv-pay] Error processing webhook {event_type}")
            db.rollback()
            return JSONResponse({"error": "processing failed"}, status_code=500)
        finally:
            db.close()

        return JSONResponse({"received": True})

    return handle_stripe_webhook


def _handle_checkout_completed(db, data, StripeCustomer, Subscription, Payment):
    stripe_customer_id = data.get("customer")
    session_id = data.get("id")
    mode = data.get("mode", "payment")

    customer = (
        db.query(StripeCustomer)
        .filter(StripeCustomer.stripe_customer_id == stripe_customer_id)
        .first()
    )
    if not customer:
        logger.warning(
            f"[viv-pay] Checkout completed for unknown customer {stripe_customer_id}"
        )
        return

    if mode == "subscription":
        sub_id = data.get("subscription")
        if sub_id:
            existing = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == sub_id)
                .first()
            )
            if not existing:
                sub = Subscription(
                    customer_id=customer.id,
                    stripe_subscription_id=sub_id,
                    stripe_price_id=data.get("metadata", {}).get("price_id", "unknown"),
                    status="active",
                )
                db.add(sub)
                logger.info(f"[viv-pay] Subscription {sub_id} created for customer {customer.id}")

    amount = data.get("amount_total", 0)
    currency = data.get("currency", "usd")
    payment = Payment(
        customer_id=customer.id,
        stripe_session_id=session_id,
        amount_cents=amount,
        currency=currency,
        status="completed",
        mode=mode,
    )
    db.add(payment)
    db.commit()
    logger.info(f"[viv-pay] Payment recorded: {amount} {currency} for customer {customer.id}")


def _handle_subscription_updated(db, data, Subscription):
    sub_id = data.get("id")
    sub = (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == sub_id)
        .first()
    )
    if not sub:
        logger.warning(f"[viv-pay] Subscription update for unknown sub {sub_id}")
        return

    sub.status = data.get("status", sub.status)
    period = data.get("current_period_start")
    if period:
        sub.current_period_start = datetime.fromtimestamp(period, tz=timezone.utc)
    period_end = data.get("current_period_end")
    if period_end:
        sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)
    cancel_at = data.get("cancel_at")
    sub.cancel_at = (
        datetime.fromtimestamp(cancel_at, tz=timezone.utc) if cancel_at else None
    )
    db.commit()
    logger.info(f"[viv-pay] Subscription {sub_id} updated: status={sub.status}")


def _handle_subscription_deleted(db, data, Subscription):
    sub_id = data.get("id")
    sub = (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == sub_id)
        .first()
    )
    if not sub:
        logger.warning(f"[viv-pay] Subscription delete for unknown sub {sub_id}")
        return

    sub.status = "canceled"
    db.commit()
    logger.info(f"[viv-pay] Subscription {sub_id} canceled")


def _handle_payment_failed(db, data, StripeCustomer, Subscription):
    stripe_customer_id = data.get("customer")
    sub_id = data.get("subscription")

    if sub_id:
        sub = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == sub_id)
            .first()
        )
        if sub:
            sub.status = "past_due"
            db.commit()
            logger.info(f"[viv-pay] Subscription {sub_id} marked past_due (payment failed)")
    else:
        logger.warning(
            f"[viv-pay] Payment failed for customer {stripe_customer_id}, no subscription"
        )


def _handle_refund(db, data, StripeCustomer, Payment):
    payment_intent_id = data.get("payment_intent")
    if not payment_intent_id:
        return

    payment = (
        db.query(Payment)
        .filter(Payment.stripe_payment_intent_id == payment_intent_id)
        .first()
    )
    if payment:
        payment.status = "refunded"
        db.commit()
        logger.info(f"[viv-pay] Payment {payment_intent_id} refunded")
    else:
        logger.info(f"[viv-pay] Refund for unknown payment_intent {payment_intent_id}")
