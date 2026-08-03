# Usage Metering & Billing Engine

A correctness-first backend for multi-tenant SaaS usage, quotas, integer cost math, Stripe test subscriptions, verified webhook synchronization, and reconciliation jobs.

## Why this project exists

Billing bugs become customer harm. This service is intentionally small - two plans, two usage types, and one billable endpoint - so the hard guarantees are visible and testable:

- a retry cannot double-count;
- a quota boundary is exact;
- money never uses floats;
- cached and reasoning tokens are priced correctly;
- forged/replayed webhooks cannot corrupt subscription state;
- one tenant cannot read another tenant's usage.

## Architecture

```text
Client --tenant API key--> FastAPI
  |                         |
  | POST /generate          +--> MeteringService
  |                              +-- atomic idempotency lookup
  |                              +-- quota check
  |                              +-- integer cost calculation
  |                              `-- immutable usage event
  |
  | GET /usage -----------> monthly tenant rollup
  |
  `-- Stripe Checkout ---> Stripe test mode
                            |
Stripe --signed event--> /webhooks/stripe
                            +-- signature verification
                            +-- event-ID deduplication
                            `-- subscription mirror update

Admin --> /jobs/reconcile --> retrying background reconciliation
```

Layers are separated: HTTP (`main.py`), rules (`metering.py`, `pricing.py`, `stripe_service.py`), and persistence (`database.py`, SQL migration).

## One-command setup

```bash
git clone https://github.com/iam-habib-rehman12/Usage-Metering-Billing-Engine.git
cd Usage-Metering-Billing-Engine
cp .env.example .env
docker compose up --build
```

In another terminal, seed the Free and Pro plans plus one demo tenant:

```bash
docker compose exec api python -m scripts.seed
```

Use the local `DEMO_TENANT_API_KEY` from `.env`; it is hashed in storage and never printed. Swagger is at http://localhost:8000/docs.

## Test

```bash
docker compose run --rm api pytest -q
```

The suite is deterministic and uses temporary SQLite databases plus mocked Stripe events. It never reaches live Stripe.

## Authentication

Tenant endpoints require:

```http
X-Tenant-ID: demo-tenant
X-API-Key: <DEMO_TENANT_API_KEY from local .env>
```

Admin job endpoints require `X-Admin-Key`.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Liveness/persistence check |
| POST | `/generate` | Idempotent billable event + quota enforcement |
| GET | `/usage` | Monthly used/limit/cost rollup |
| POST | `/checkout` | Stripe test Checkout URL for Pro |
| POST | `/webhooks/stripe` | Verified, deduplicated subscription events |
| POST | `/jobs/reconcile` | Queue Stripe reconciliation (admin) |
| GET | `/jobs/{id}` | Inspect retry/failure status (admin) |

## Meter a billable action

```bash
curl -i -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: demo-tenant" \
  -H "X-API-Key: your-local-demo-key" \
  -H "Idempotency-Key: demo-request-001" \
  -d '{"usage_type":"api_calls","quantity":1}'
```

Repeat exactly: the response matches and the database still contains one event.

AI-token example:

```json
{
  "usage_type": "ai_tokens",
  "input_tokens": 2500,
  "cached_input_tokens": 1000,
  "output_tokens": 500,
  "reasoning_tokens": 200
}
```

Cached input is billed at its discounted rate. Reasoning joins output for billing. Costs are integer microdollars (`1 USD = 1,000,000 microdollars`).

## Boundary rule

`current + requested <= limit` is allowed. The first unit beyond the monthly limit returns `429` with `Retry-After` and a message containing used/requested/limit. A `past_due` or canceled subscription returns `402`.

## Stripe test mode

Set only test values in `.env`, create a recurring Pro Price, then forward events:

```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
```

Copy the shown `whsec_...` into `STRIPE_WEBHOOK_SECRET`, restart the API, and use the checkout URL from `POST /checkout`. Required event types are handled and every Stripe event ID is processed once.

## Submission pack

- `DESIGN.md` - problem, schema, contract, idempotency design, non-goal.
- `capstone.yaml` - machine-readable run/seed/test/probe contract.
- `EVIDENCE.md` - proof mapped to every Definition-of-Done category.
- `BUILDLOG.md` - honest AI assistance, corrections, and ownership.
- `.env.example` - safe placeholders only.

## Limitations

- Core scope intentionally excludes invoices, proration, and overage charges.
- SQLite serializes metering writes; this makes correctness easy to inspect. A higher-throughput deployment would move the same transaction and unique constraints to PostgreSQL.
- FastAPI background tasks are suitable for this demo. Production reconciliation should use a durable queue with a worker and alert transport.
- Stripe Checkout is test mode only; no live money is accepted.

MIT licensed. See [EVIDENCE.md](EVIDENCE.md) for the reviewer checklist.

