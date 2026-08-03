import time
import uuid

import stripe

from .config import settings
from .database import Database


def reconcile_subscriptions(database: Database, job_id: str) -> None:
    stripe.api_key = settings.stripe_secret_key
    last_error = None
    for attempt in range(1, 4):
        try:
            if not settings.stripe_secret_key:
                raise RuntimeError("Stripe test mode is not configured")
            subscriptions = stripe.Subscription.list(status="all", limit=100)
            with database.transaction() as connection:
                for subscription in subscriptions.auto_paging_iter():
                    connection.execute(
                        """UPDATE subscriptions SET status=?, updated_at=CURRENT_TIMESTAMP
                           WHERE stripe_subscription_id=?""",
                        (subscription.status, subscription.id),
                    )
                connection.execute(
                    """UPDATE job_runs SET status='completed', attempts=?,
                       finished_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (attempt, job_id),
                )
            return
        except Exception as exc:
            last_error = str(exc)[:500]
            time.sleep(attempt)
    with database.transaction() as connection:
        connection.execute(
            """UPDATE job_runs SET status='failed', attempts=3, error=?,
               finished_at=CURRENT_TIMESTAMP WHERE id=?""",
            (last_error, job_id),
        )


def create_job(database: Database, job_type: str) -> str:
    job_id = str(uuid.uuid4())
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO job_runs(id,job_type,status) VALUES (?,?,'queued')",
            (job_id, job_type),
        )
    return job_id

