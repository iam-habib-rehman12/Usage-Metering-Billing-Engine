import pytest
from fastapi import HTTPException

from app.schemas import GenerateRequest


def api_calls(quantity=1):
    return GenerateRequest(usage_type="api_calls", quantity=quantity)


def test_retry_with_same_key_cannot_double_count(service, tenant, database):
    first = service.record(tenant, api_calls(), "retry-key")
    second = service.record(tenant, api_calls(), "retry-key")
    assert second == first
    with database.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM usage_events WHERE tenant_id='tenant-a'"
        ).fetchone()[0]
    assert count == 1


def test_quota_allows_exact_boundary_and_rejects_one_after(service, tenant):
    service.record(tenant, api_calls(999), "q-999")
    boundary = service.record(tenant, api_calls(1), "q-1000")
    assert boundary["used"] == 1000
    with pytest.raises(HTTPException) as error:
        service.record(tenant, api_calls(1), "q-over")
    assert error.value.status_code == 429
    assert "quota exceeded" in error.value.detail


def test_unpaid_subscription_returns_402(service, tenant, database):
    with database.transaction() as connection:
        connection.execute(
            "UPDATE subscriptions SET status='past_due' WHERE tenant_id='tenant-a'"
        )
    unpaid = service.authenticate("tenant-a", "secret")
    with pytest.raises(HTTPException) as error:
        service.record(unpaid, api_calls(), "unpaid")
    assert error.value.status_code == 402


def test_usage_is_isolated_by_tenant(service, tenant, database):
    service.record(tenant, api_calls(4), "tenant-a-event")
    with database.transaction() as connection:
        import hashlib
        connection.execute(
            "INSERT INTO tenants(id,name,api_key_hash) VALUES (?,?,?)",
            ("tenant-b", "Tenant B", hashlib.sha256(b"other").hexdigest()),
        )
        connection.execute(
            "INSERT INTO subscriptions(tenant_id,plan_code,status) VALUES (?,?,?)",
            ("tenant-b", "free", "active"),
        )
    other = service.authenticate("tenant-b", "other")
    assert service.usage(tenant)["api_calls"]["used"] == 4
    assert service.usage(other)["api_calls"]["used"] == 0

