from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import CurrentPrincipal, Principal, require_csrf
from invoice_agent.api.errors import AppError
from invoice_agent.persistence.audit_repository import record_event
from invoice_agent.persistence.database import get_session
from invoice_agent.persistence.invoice_models import Invoice
from invoice_agent.persistence.job_repository import Job
from invoice_agent.worker.queue import enqueue_job

router = APIRouter(prefix="/api/v1", tags=["jobs"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CsrfDep = Annotated[None, Depends(require_csrf)]


async def _authorized_job(session: AsyncSession, job_id: UUID, principal: Principal) -> Job:
    job = await session.scalar(
        select(Job)
        .join(Invoice, Invoice.id == Job.invoice_id)
        .where(
            Job.id == job_id,
            Job.tenant_id == principal.tenant_id,
            Invoice.tenant_id == principal.tenant_id,
        )
    )
    if job is None:
        raise AppError(404, "not_found", "Job was not found.")
    return job


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: UUID, principal: CurrentPrincipal, session: SessionDep
) -> dict[str, object]:
    job = await _authorized_job(session, job_id, principal)
    return {
        "id": str(job.id),
        "status": job.state,
        "stage": job.stage,
        "attempts": job.attempts,
        "error_code": job.error_code,
    }


@router.post("/invoices/{invoice_id}/retry", status_code=202)
async def retry_invoice(
    invoice_id: UUID,
    principal: CurrentPrincipal,
    _: CsrfDep,
    session: SessionDep,
) -> dict[str, str]:
    invoice = await session.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.tenant_id == principal.tenant_id)
        .with_for_update()
    )
    if invoice is None:
        raise AppError(404, "not_found", "Invoice was not found.")
    if invoice.processing_status != "failed":
        raise AppError(409, "not_retryable", "Only failed invoice processing can be retried.")
    job = await enqueue_job(session, principal.tenant_id, invoice.id, "extract")
    invoice.processing_status = "received"
    await record_event(
        session,
        tenant_id=principal.tenant_id,
        actor_type="user",
        actor_id=principal.user_id,
        action="invoice.processing_retried",
        resource_type="invoice",
        resource_id=str(invoice.id),
        outcome="success",
        details={"job_id": str(job.id)},
    )
    await session.commit()
    return {"job_id": str(job.id), "status": "queued"}
