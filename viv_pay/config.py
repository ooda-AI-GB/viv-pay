import os
from dataclasses import dataclass, field


@dataclass
class PayConfig:
    success_path: str = "/pay/success"
    cancel_path: str = "/pay/cancel"
    webhook_path: str = "/pay/webhook"
    auto_create_customer: bool = True
    allowed_statuses: list[str] = field(
        default_factory=lambda: ["active", "trialing"]
    )


def get_stripe_secret_key() -> str | None:
    return os.environ.get("STRIPE_SECRET_KEY")


def get_stripe_publishable_key() -> str | None:
    return os.environ.get("STRIPE_PUBLISHABLE_KEY")


def get_stripe_webhook_secret() -> str | None:
    return os.environ.get("STRIPE_WEBHOOK_SECRET")


def is_dev_mode() -> bool:
    return get_stripe_secret_key() is None
