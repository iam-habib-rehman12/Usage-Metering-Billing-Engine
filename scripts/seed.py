import hashlib
import os
import uuid

from app.config import settings
from app.database import Database


def hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> None:
    if not settings.demo_tenant_api_key:
        raise SystemExit("DEMO_TENANT_API_KEY must be set")
    db = Database(settings.database_path)
    db.migrate()
    tenant_id = "demo-tenant"
    with db.transaction() as connection:
        connection.executemany(
            "INSERT OR IGNORE INTO plans(code,api_call_limit,ai_token_limit) VALUES (?,?,?)",
            [("free", 1000, 100_000), ("pro", 100_000, 10_000_000)],
        )
        connection.execute(
            "INSERT OR IGNORE INTO tenants(id,name,api_key_hash) VALUES (?,?,?)",
            (tenant_id, "Demo Tenant", hash_key(settings.demo_tenant_api_key)),
        )
        connection.execute(
            """INSERT OR IGNORE INTO subscriptions(tenant_id,plan_code,status)
               VALUES (?,'free','active')""",
            (tenant_id,),
        )
    print(f"Seeded tenant: {tenant_id}")
    print("Use DEMO_TENANT_API_KEY from your local .env; it is never printed.")


if __name__ == "__main__":
    main()

