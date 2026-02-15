# viv-pay

Drop-in Stripe billing for FastAPI apps built by Viva.

## Install

```bash
pip install git+https://github.com/ooda-AI-GB/viv-pay.git
```

## Quick Start

```python
from fastapi import FastAPI, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from viv_pay import init_pay

app = FastAPI()
engine = create_engine("sqlite:///app.db")
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

create_checkout, get_customer, require_subscription = init_pay(
    app, engine, Base, get_db, app_name="My SaaS"
)

@app.get("/premium", dependencies=[Depends(require_subscription)])
async def premium():
    return {"data": "premium content"}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `STRIPE_SECRET_KEY` | Prod only | Stripe secret key. If unset, runs in dev mode. |
| `STRIPE_PUBLISHABLE_KEY` | No | Exposed via `/pay/config` for frontend JS. |
| `STRIPE_WEBHOOK_SECRET` | Prod only | Webhook signature verification. |
| `APP_URL` | No | Base URL for redirect URLs. Defaults to `http://localhost:8000`. |

## Dev Mode

When `STRIPE_SECRET_KEY` is not set, viv-pay runs in dev mode:
- Checkout returns a fake success URL and logs to stdout
- Webhooks accept payloads without signature verification
- `require_subscription` always passes

## Routes

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/pay/checkout` | Create Checkout Session |
| POST | `/pay/webhook` | Stripe webhook handler |
| POST | `/pay/portal` | Customer Portal session |
| GET | `/pay/success` | Success redirect page |
| GET | `/pay/cancel` | Cancel redirect page |
| GET | `/pay/config` | Publishable key for frontend |

## Returned Functions

- `create_checkout(user_id, email, price_id, mode, metadata)` — Returns checkout URL
- `get_customer(user_id)` — Returns StripeCustomer or None
- `require_subscription` — FastAPI dependency, raises PaymentRequired if no active subscription
