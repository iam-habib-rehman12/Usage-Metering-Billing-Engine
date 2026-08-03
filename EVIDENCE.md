# Evidence

Each proof maps directly to the capstone Definition of Done. Run `docker compose run --rm api pytest -q` to reproduce the complete suite.

## Metering

- Exactly one event under retries: `tests/test_metering.py::test_retry_with_same_key_cannot_double_count` sends the same key twice, asserts identical responses, then asserts one database row.
- Database guarantee: migration constraint `UNIQUE (tenant_id, idempotency_key)` plus an atomic `BEGIN IMMEDIATE` transaction.

## Quotas

- Exact boundary and over-limit refusal: `tests/test_metering.py::test_quota_allows_exact_boundary_and_rejects_one_after` records 999, allows the 1,000th call, and asserts the next call returns 429.
- Payment-required behavior: `tests/test_metering.py::test_unpaid_subscription_returns_402` proves a `past_due` subscription cannot record usage.

## Cost calculation

- Integer-only API-call cost: `tests/test_pricing.py::test_api_call_cost_uses_integer_microdollars`.
- Cached input discount: `tests/test_pricing.py::test_cached_input_is_priced_separately_and_cheaper` pins 1M input with 400k cached to exactly 800,000 microdollars.
- Reasoning-as-output: `tests/test_pricing.py::test_reasoning_tokens_are_billed_as_output` pins 150k billed-output tokens to 1,500,000 microdollars.

## Stripe integration

- Forgery rejection: `tests/test_webhooks.py::test_invalid_signature_is_rejected` asserts status 400.
- Replay protection and plan sync: `tests/test_webhooks.py::test_duplicate_webhook_updates_subscription_once` handles the same event twice, asserts one event row, and proves Free becomes Pro.
- Checkout code uses Stripe test configuration only and stores no key in source.

## Data model and isolation

- Schema: `migrations/001_initial.sql` contains plans, tenants, subscriptions, usage events, webhook events, indexes, and job runs.
- Tenant isolation: `tests/test_metering.py::test_usage_is_isolated_by_tenant` records for Tenant A and proves Tenant B sees zero.

## Background work and resilience

- `POST /jobs/reconcile` queues reconciliation outside the request path.
- `app/jobs.py` retries three times, records attempts/final error, and exposes status at `GET /jobs/{id}`.

## Reproducible acceptance commands

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec api python -m scripts.seed
docker compose run --rm api pytest -q
curl -i http://localhost:8000/health
```

Live Stripe Checkout requires the reviewer's own free test-mode key, price ID, and webhook secret. No live-mode credentials are supported or required.
