from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.stripe_service as stripe_module
from app.stripe_service import StripeService


def test_invalid_signature_is_rejected(database, monkeypatch):
    monkeypatch.setattr(
        stripe_module,
        "settings",
        SimpleNamespace(stripe_webhook_secret="whsec_test", stripe_secret_key="sk_test"),
    )
    service = StripeService(database)

    def reject(*_args):
        raise stripe_module.stripe.error.SignatureVerificationError("bad", "sig")

    monkeypatch.setattr(stripe_module.stripe.Webhook, "construct_event", reject)
    with pytest.raises(HTTPException) as error:
        service.handle_webhook(b"{}", "forged")
    assert error.value.status_code == 400


def test_duplicate_webhook_updates_subscription_once(database, monkeypatch):
    monkeypatch.setattr(
        stripe_module,
        "settings",
        SimpleNamespace(stripe_webhook_secret="whsec_test", stripe_secret_key="sk_test"),
    )
    event = {
        "id": "evt_123",
        "type": "checkout.session.completed",
        "data": {"object": {
            "metadata": {"tenant_id": "tenant-a"},
            "customer": "cus_123", "subscription": "sub_123",
        }},
    }
    monkeypatch.setattr(
        stripe_module.stripe.Webhook, "construct_event", lambda *_args: event
    )
    service = StripeService(database)
    assert service.handle_webhook(b"{}", "valid")["duplicate"] is False
    assert service.handle_webhook(b"{}", "valid")["duplicate"] is True
    with database.connect() as connection:
        plan = connection.execute(
            "SELECT plan_code FROM subscriptions WHERE tenant_id='tenant-a'"
        ).fetchone()[0]
        count = connection.execute("SELECT COUNT(*) FROM webhook_events").fetchone()[0]
    assert plan == "pro"
    assert count == 1

