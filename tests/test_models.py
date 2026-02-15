from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from viv_pay.models import create_pay_models


def test_create_models_returns_three_classes():
    Base = declarative_base()
    StripeCustomer, Subscription, Payment = create_pay_models(Base)

    assert StripeCustomer.__tablename__ == "stripe_customers"
    assert Subscription.__tablename__ == "subscriptions"
    assert Payment.__tablename__ == "payments"


def test_stripe_customer_creation():
    engine = create_engine("sqlite:///:memory:")
    Base = declarative_base()
    StripeCustomer, _, _ = create_pay_models(Base)
    Base.metadata.create_all(bind=engine)

    Session = sessionmaker(bind=engine)
    db = Session()

    customer = StripeCustomer(
        user_id=1, email="test@example.com", stripe_customer_id="cus_test123"
    )
    db.add(customer)
    db.commit()

    result = db.query(StripeCustomer).first()
    assert result.user_id == 1
    assert result.email == "test@example.com"
    assert result.stripe_customer_id == "cus_test123"
    assert result.created_at is not None
    db.close()


def test_subscription_creation():
    engine = create_engine("sqlite:///:memory:")
    Base = declarative_base()
    StripeCustomer, Subscription, _ = create_pay_models(Base)
    Base.metadata.create_all(bind=engine)

    Session = sessionmaker(bind=engine)
    db = Session()

    customer = StripeCustomer(
        user_id=1, email="test@example.com", stripe_customer_id="cus_test123"
    )
    db.add(customer)
    db.commit()

    sub = Subscription(
        customer_id=customer.id,
        stripe_subscription_id="sub_test123",
        stripe_price_id="price_test",
        status="active",
    )
    db.add(sub)
    db.commit()

    result = db.query(Subscription).first()
    assert result.status == "active"
    assert result.stripe_subscription_id == "sub_test123"
    db.close()


def test_payment_creation():
    engine = create_engine("sqlite:///:memory:")
    Base = declarative_base()
    StripeCustomer, _, Payment = create_pay_models(Base)
    Base.metadata.create_all(bind=engine)

    Session = sessionmaker(bind=engine)
    db = Session()

    customer = StripeCustomer(
        user_id=1, email="test@example.com", stripe_customer_id="cus_test123"
    )
    db.add(customer)
    db.commit()

    payment = Payment(
        customer_id=customer.id,
        stripe_session_id="cs_test123",
        amount_cents=2000,
        currency="usd",
        status="completed",
        mode="subscription",
    )
    db.add(payment)
    db.commit()

    result = db.query(Payment).first()
    assert result.amount_cents == 2000
    assert result.currency == "usd"
    assert result.status == "completed"
    db.close()


def test_customer_user_id_unique():
    engine = create_engine("sqlite:///:memory:")
    Base = declarative_base()
    StripeCustomer, _, _ = create_pay_models(Base)
    Base.metadata.create_all(bind=engine)

    Session = sessionmaker(bind=engine)
    db = Session()

    c1 = StripeCustomer(
        user_id=1, email="a@example.com", stripe_customer_id="cus_1"
    )
    db.add(c1)
    db.commit()

    c2 = StripeCustomer(
        user_id=1, email="b@example.com", stripe_customer_id="cus_2"
    )
    db.add(c2)

    import sqlalchemy
    import pytest

    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db.commit()
    db.close()
