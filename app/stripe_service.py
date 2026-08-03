import json

import stripe
from fastapi import HTTPException

from .config import settings
from .database import Database


class StripeService:
    def __init__(self, database: Database):
        self.db = database
        stripe.api_key = settings.stripe_secret_key

    def checkout(self, tenant_id: str, success_url: str, cancel_url: str) -> str:
        if not settings.stripe_secret_key or not settings.stripe_pro_price_id:
            raise HTTPException(status_code=503, detail="Stripe test mode is not configured")
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": settings.stripe_pro_price_id, "quantity": 1}],
            success_url=success_url, cancel_url=cancel_url,
            client_reference_id=tenant_id, metadata={"tenant_id": tenant_id},
        )
        return session.url

    def handle_webhook(self, raw_body: bytes, signature: str) -> dict:
        if not settings.stripe_webhook_secret:
            raise HTTPException(status_code=503, detail="Stripe webhook is not configured")
        try:
            event = stripe.Webhook.construct_event(
                raw_body, signature, settings.stripe_webhook_secret
            )
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            raise HTTPException(status_code=400, detail="Invalid Stripe signature") from exc

        event_id, event_type = event["id"], event["type"]
        with self.db.transaction() as connection:
            duplicate = connection.execute(
                "SELECT 1 FROM webhook_events WHERE stripe_event_id=?", (event_id,)
            ).fetchone()
            if duplicate:
                return {"received": True, "duplicate": True}

            obj = event["data"]["object"]
            tenant_id = (obj.get("metadata") or {}).get("tenant_id") or obj.get("client_reference_id")
            if event_type == "checkout.session.completed" and tenant_id:
                connection.execute(
                    """UPDATE subscriptions SET plan_code='pro', status='active',
                       stripe_customer_id=?, stripe_subscription_id=?, updated_at=CURRENT_TIMESTAMP
                       WHERE tenant_id=?""",
                    (obj.get("customer"), obj.get("subscription"), tenant_id),
                )
            elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
                row = connection.execute(
                    "SELECT tenant_id FROM subscriptions WHERE stripe_subscription_id=?",
                    (obj.get("id"),),
                ).fetchone()
                if row:
                    status = "canceled" if event_type.endswith("deleted") else obj.get("status", "past_due")
                    connection.execute(
                        "UPDATE subscriptions SET status=?, updated_at=CURRENT_TIMESTAMP WHERE tenant_id=?",
                        (status, row["tenant_id"]),
                    )
            connection.execute(
                "INSERT INTO webhook_events(stripe_event_id,event_type) VALUES (?,?)",
                (event_id, event_type),
            )
        return {"received": True, "duplicate": False}

