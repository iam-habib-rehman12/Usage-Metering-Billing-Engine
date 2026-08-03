# Design: Usage Metering & Billing Engine

## Problem

SaaS products must record billable usage exactly once, reject work beyond a tenant's allowance, calculate costs without floating-point errors, and mirror Stripe subscription truth safely.

## Data model

- `plans`: Free/Pro quotas.
- `tenants`: customer organizations and hashed API keys.
- `subscriptions`: one current plan/status per tenant plus Stripe identifiers.
- `usage_events`: immutable billable records with a tenant-scoped idempotency constraint.
- `webhook_events`: Stripe event IDs already processed.
- `job_runs`: background reconciliation status, attempts, and failures.

## API surface

- `POST /generate` - authenticated billable action.
- `GET /usage` - tenant monthly rollup.
- `POST /checkout` - Stripe test Checkout session.
- `POST /webhooks/stripe` - raw, signed Stripe events.
- `POST /jobs/reconcile` - admin-triggered background reconciliation.
- `GET /jobs/{id}` - background job status.

## Layer sketch

HTTP validates and authenticates, services apply metering/payment rules, and the database module owns transactions and persistence. Pricing is a pure integer-math module.

## Idempotency strategy

`usage_events` has `UNIQUE(tenant_id, idempotency_key)`. Metering uses `BEGIN IMMEDIATE`, checks the key, computes quota, and inserts inside one transaction. A retry returns the original serialized result. Stripe events use the same pattern with `webhook_events.stripe_event_id`.

## Explicit non-goal

The core does not generate invoices, calculate proration, or charge overages. Stripe test mode manages subscription state; this service meters and enforces access.

