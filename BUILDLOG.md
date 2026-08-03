# Build Log

## AI assistance

AI helped translate the capstone brief into a bounded architecture, scaffold the FastAPI/SQLite implementation, enumerate adversarial tests, and draft documentation.

## What required human ownership

- Chose integer microdollars instead of floats.
- Defined the exact boundary rule: a request reaching the quota is allowed; the next unit is rejected.
- Chose a tenant-scoped idempotency key rather than a global key.
- Required atomic quota-check-and-insert in one database transaction.
- Separated cached input from fresh input and counted reasoning as output.
- Kept Stripe as payment truth and the local subscription as a verified mirror.

## Where the initial generated approach was wrong

1. The first replay response added an `idempotent_replay` mutation, which violated the acceptance promise that a retry mirrors the original response. It was changed to return the stored response byte-for-byte at the JSON value level.
2. A naive quota design checked usage before opening a transaction, allowing concurrent requests to pass together. The final service uses `BEGIN IMMEDIATE` so check and insert are atomic.
3. A naive token calculator summed all token categories. The final calculator subtracts cached input from fresh input and bills reasoning tokens at the output rate.

## Verification philosophy

The tests target the scary cases: duplicate requests, exact/over quota boundaries, unpaid subscriptions, tenant isolation, invalid signatures, duplicate webhooks, and pinned token math. No test calls live Stripe or spends money.

