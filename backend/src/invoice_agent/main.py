from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from invoice_agent.api.audit import router as audit_router
from invoice_agent.api.auth import SessionMiddleware
from invoice_agent.api.auth_routes import router as auth_router
from invoice_agent.api.chat import router as chat_router
from invoice_agent.api.downloads import router as downloads_router
from invoice_agent.api.errors import install_error_handlers
from invoice_agent.api.invoices import router as invoice_router
from invoice_agent.api.jobs import router as jobs_router
from invoice_agent.api.logging import router as logging_router
from invoice_agent.api.reviews import router as reviews_router
from invoice_agent.api.settings import router as settings_router
from invoice_agent.api.validation import router as validation_router
from invoice_agent.api.workbooks import router as workbooks_router
from invoice_agent.config import settings
from invoice_agent.observability import SafeRequestMetricsMiddleware
from invoice_agent.persistence.database import SessionFactory, engine
from invoice_agent.persistence.models import Base, Tenant


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.prototype_mode:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with SessionFactory() as session:
            prototype_tenant_id = UUID(settings.prototype_tenant_id)
            tenant = await session.get(Tenant, prototype_tenant_id)
            if tenant is None:
                session.add(Tenant(id=prototype_tenant_id, name="Local Prototype"))
                await session.commit()
    yield
    await engine.dispose()


app = FastAPI(
    title="Invoice Intake Assistant",
    version="0.1.0",
    max_body_size=settings.max_upload_bytes + 1024 * 1024,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
)
app.add_middleware(SessionMiddleware)
app.add_middleware(SafeRequestMetricsMiddleware)
install_error_handlers(app)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(invoice_router)
app.include_router(jobs_router)
app.include_router(settings_router)
app.include_router(validation_router)
app.include_router(workbooks_router)
app.include_router(logging_router)
app.include_router(downloads_router)
app.include_router(reviews_router)
app.include_router(audit_router)


@app.get("/api/v1/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/health/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    from sqlalchemy import text

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"status": "ready"}
