from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .auth import require_admin
from .config import settings
from .database import Database
from .jobs import create_job, reconcile_subscriptions
from .metering import MeteringService, TenantContext
from .schemas import CheckoutRequest, GenerateRequest
from .stripe_service import StripeService

database = Database(settings.database_path)
metering = MeteringService(database)
stripe_service = StripeService(database)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    database.migrate()
    yield


app = FastAPI(
    title="Usage Metering & Billing Engine",
    version="1.0.0",
    description="Idempotent multi-tenant metering, quotas, integer cost math, and Stripe test-mode sync.",
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, _exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "Invalid request"})


def tenant_context(
    x_tenant_id: str = Header(default=""),
    x_api_key: str = Header(default=""),
) -> TenantContext:
    return metering.authenticate(x_tenant_id, x_api_key)


@app.get("/health", tags=["System"])
def health():
    with database.connect() as connection:
        connection.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@app.post("/generate", status_code=201, tags=["Metering"])
def generate(
    payload: GenerateRequest,
    tenant: TenantContext = Depends(tenant_context),
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
):
    return metering.record(tenant, payload, idempotency_key)


@app.get("/usage", tags=["Metering"])
def usage(tenant: TenantContext = Depends(tenant_context)):
    return metering.usage(tenant)


@app.post("/checkout", tags=["Stripe"])
def checkout(payload: CheckoutRequest, tenant: TenantContext = Depends(tenant_context)):
    success = payload.success_url or f"{settings.base_url}/docs?checkout=success"
    cancel = payload.cancel_url or f"{settings.base_url}/docs?checkout=canceled"
    return {"checkout_url": stripe_service.checkout(tenant.tenant_id, success, cancel)}


@app.post("/webhooks/stripe", tags=["Stripe"])
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
):
    return stripe_service.handle_webhook(await request.body(), stripe_signature)


@app.post("/jobs/reconcile", status_code=202, tags=["Jobs"])
def start_reconciliation(
    background_tasks: BackgroundTasks,
    _admin: None = Depends(require_admin),
):
    job_id = create_job(database, "stripe_reconciliation")
    background_tasks.add_task(reconcile_subscriptions, database, job_id)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}", tags=["Jobs"])
def job_status(job_id: str, _admin: None = Depends(require_admin)):
    with database.connect() as connection:
        row = connection.execute("SELECT * FROM job_runs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)

