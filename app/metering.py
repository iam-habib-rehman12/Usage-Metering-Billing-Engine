import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from fastapi import HTTPException

from .auth import verify_tenant_key
from .database import Database
from .pricing import api_call_cost_microdollars, token_cost_microdollars
from .schemas import GenerateRequest


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    plan_code: str
    status: str
    api_call_limit: int
    ai_token_limit: int


class MeteringService:
    def __init__(self, database: Database):
        self.db = database

    def authenticate(self, tenant_id: str, api_key: str) -> TenantContext:
        with self.db.connect() as connection:
            row = connection.execute(
                """
                SELECT t.id, t.api_key_hash, s.plan_code, s.status,
                       p.api_call_limit, p.ai_token_limit
                FROM tenants t
                JOIN subscriptions s ON s.tenant_id = t.id
                JOIN plans p ON p.code = s.plan_code
                WHERE t.id = ?
                """,
                (tenant_id,),
            ).fetchone()
        if row is None or not verify_tenant_key(api_key, row["api_key_hash"]):
            raise HTTPException(status_code=401, detail="Invalid tenant credentials")
        return TenantContext(
            tenant_id=row["id"], plan_code=row["plan_code"], status=row["status"],
            api_call_limit=row["api_call_limit"], ai_token_limit=row["ai_token_limit"],
        )

    @staticmethod
    def _month_start() -> str:
        now = datetime.now(timezone.utc)
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    def record(self, tenant: TenantContext, payload: GenerateRequest,
               idempotency_key: str) -> dict:
        if not idempotency_key or len(idempotency_key) > 200:
            raise HTTPException(status_code=400, detail="Valid Idempotency-Key required")
        if tenant.status not in ("active", "trialing"):
            raise HTTPException(status_code=402, detail="Subscription payment or upgrade required")

        with self.db.transaction() as connection:
            duplicate = connection.execute(
                "SELECT response_json FROM usage_events WHERE tenant_id=? AND idempotency_key=?",
                (tenant.tenant_id, idempotency_key),
            ).fetchone()
            if duplicate:
                return json.loads(duplicate["response_json"])

            used = connection.execute(
                """SELECT COALESCE(SUM(quantity), 0) AS used FROM usage_events
                   WHERE tenant_id=? AND usage_type=? AND created_at >= ?""",
                (tenant.tenant_id, payload.usage_type, self._month_start()),
            ).fetchone()["used"]
            limit = (tenant.api_call_limit if payload.usage_type == "api_calls"
                     else tenant.ai_token_limit)
            if used + payload.quantity > limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"{payload.usage_type} quota exceeded: used={used}, requested={payload.quantity}, limit={limit}",
                    headers={"Retry-After": "3600"},
                )

            cost = (api_call_cost_microdollars(payload.quantity)
                    if payload.usage_type == "api_calls" else token_cost_microdollars(
                        input_tokens=payload.input_tokens,
                        cached_input_tokens=payload.cached_input_tokens,
                        output_tokens=payload.output_tokens,
                        reasoning_tokens=payload.reasoning_tokens,
                    ))
            event_id = str(uuid.uuid4())
            response = {
                "event_id": event_id, "tenant_id": tenant.tenant_id,
                "usage_type": payload.usage_type, "quantity": payload.quantity,
                "used": used + payload.quantity, "limit": limit,
                "cost_microdollars": cost, "idempotent_replay": False,
            }
            connection.execute(
                """INSERT INTO usage_events
                   (id,tenant_id,usage_type,quantity,input_tokens,cached_input_tokens,
                    output_tokens,reasoning_tokens,cost_microdollars,idempotency_key,response_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (event_id, tenant.tenant_id, payload.usage_type, payload.quantity,
                 payload.input_tokens, payload.cached_input_tokens, payload.output_tokens,
                 payload.reasoning_tokens, cost, idempotency_key, json.dumps(response)),
            )
            return response

    def usage(self, tenant: TenantContext) -> dict:
        with self.db.connect() as connection:
            rows = connection.execute(
                """SELECT usage_type, COALESCE(SUM(quantity),0) used,
                          COALESCE(SUM(cost_microdollars),0) cost
                   FROM usage_events WHERE tenant_id=? AND created_at >= ?
                   GROUP BY usage_type""",
                (tenant.tenant_id, self._month_start()),
            ).fetchall()
        values = {row["usage_type"]: row for row in rows}
        api = values.get("api_calls", {"used": 0, "cost": 0})
        ai = values.get("ai_tokens", {"used": 0, "cost": 0})
        return {
            "tenant_id": tenant.tenant_id,
            "plan": tenant.plan_code,
            "subscription_status": tenant.status,
            "api_calls": {"used": api["used"], "limit": tenant.api_call_limit},
            "ai_tokens": {"used": ai["used"], "limit": tenant.ai_token_limit},
            "cost_microdollars": api["cost"] + ai["cost"],
        }
