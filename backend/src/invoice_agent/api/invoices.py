from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import CurrentPrincipal, require_csrf
from invoice_agent.api.errors import AppError
from invoice_agent.config import settings
from invoice_agent.domain.amounts import format_amount
from invoice_agent.persistence.audit_repository import record_event
from invoice_agent.persistence.blob_store import LocalBlobStore
from invoice_agent.persistence.database import get_session
from invoice_agent.persistence.invoice_models import FieldEvidence, Invoice, InvoiceRevision
from invoice_agent.services.upload_service import validate_invoice_upload
from invoice_agent.worker.queue import enqueue_job

router = APIRouter(prefix="/api/v1", tags=["invoices"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CsrfDep = Annotated[None, Depends(require_csrf)]


class CorrectionRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    changes: dict[str, str | None]


@router.post("/invoices", status_code=status.HTTP_202_ACCEPTED)
async def upload_invoice(
    principal: CurrentPrincipal,
    _: CsrfDep,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> dict[str, str]:
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise AppError(
            413, "file_too_large", "The uploaded file exceeds the configured size limit."
        )
    try:
        validated = validate_invoice_upload(file.filename or "", data)
    except ValueError as exc:
        message = str(exc)
        status_code = 415 if "Only PDF" in message or "supported" in message else 422
        code = "unsupported_format" if status_code == 415 else "invalid_document"
        raise AppError(status_code, code, message) from exc
    key = settings.data_encryption_key
    if key is None:
        raise AppError(
            503, "storage_not_configured", "Private encrypted storage is not configured."
        )
    try:
        blob_store = LocalBlobStore(settings.blob_root, key.get_secret_value().encode())
        blob = blob_store.put(data)
    except Exception as exc:
        raise AppError(
            503, "storage_unavailable", "The uploaded file could not be stored safely."
        ) from exc
    invoice = Invoice(
        tenant_id=principal.tenant_id,
        source_blob_id=blob.blob_id,
        source_sha256=blob.sha256,
        source_media_type=validated.media_type,
        processing_status="received",
        review_status="not_reviewed",
        current_revision=1,
        created_by=principal.user_id,
    )
    session.add(invoice)
    await session.flush()
    revision = InvoiceRevision(invoice_id=invoice.id, revision=1)
    session.add(revision)
    job = await enqueue_job(session, principal.tenant_id, invoice.id, "extract")
    await record_event(
        session,
        tenant_id=principal.tenant_id,
        actor_type="user",
        actor_id=principal.user_id,
        action="invoice.uploaded",
        resource_type="invoice",
        resource_id=str(invoice.id),
        outcome="success",
        details={"media_type": validated.media_type, "size": len(data), "sha256": blob.sha256},
    )
    await session.commit()
    return {"invoice_id": str(invoice.id), "job_id": str(job.id), "status": "received"}


@router.get("/invoices")
async def list_invoices(
    principal: CurrentPrincipal,
    session: SessionDep,
    limit: int = 50,
    status_filter: str | None = None,
    cursor: UUID | None = None,
) -> dict[str, object]:
    limit = min(max(limit, 1), 100)
    statement = select(Invoice).where(Invoice.tenant_id == principal.tenant_id)
    if cursor:
        last = await session.scalar(
            select(Invoice).where(Invoice.id == cursor, Invoice.tenant_id == principal.tenant_id)
        )
        if last is None:
            raise AppError(400, "invalid_cursor", "Invoice cursor is invalid.")
        statement = statement.where(Invoice.created_at < last.created_at)
    if status_filter:
        statement = statement.where(Invoice.processing_status == status_filter)
    statement = statement.order_by(Invoice.created_at.desc(), Invoice.id.desc()).limit(limit + 1)
    records = list(await session.scalars(statement))
    has_more = len(records) > limit
    records = records[:limit]
    return {
        "items": [
            {
                "id": str(item.id),
                "processing_status": item.processing_status,
                "review_status": item.review_status,
                "created_at": item.created_at.isoformat(),
            }
            for item in records
        ],
        "next_cursor": str(records[-1].id) if has_more and records else None,
    }


@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: UUID, principal: CurrentPrincipal, session: SessionDep
) -> dict[str, object]:
    invoice = await session.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == principal.tenant_id)
    )
    if invoice is None:
        raise AppError(404, "not_found", "Invoice was not found.")
    revision = await session.scalar(
        select(InvoiceRevision).where(
            InvoiceRevision.invoice_id == invoice.id,
            InvoiceRevision.revision == invoice.current_revision,
        )
    )
    evidence = (
        await session.scalars(select(FieldEvidence).where(FieldEvidence.revision_id == revision.id))
        if revision
        else []
    )
    return {
        "id": str(invoice.id),
        "processing_status": invoice.processing_status,
        "review_status": invoice.review_status,
        "revision": invoice.current_revision,
        "fields": {
            "vendor_name": revision.vendor if revision else None,
            "invoice_number": revision.invoice_number if revision else None,
            "invoice_date": revision.invoice_date_raw if revision else None,
            "due_date": revision.due_date_raw if revision else None,
            "po_number": revision.po_number if revision else None,
            "currency": revision.currency if revision else None,
            "subtotal": format_amount(revision.subtotal) if revision else None,
            "tax": format_amount(revision.tax) if revision else None,
            "other_charges": format_amount(revision.other_charges) if revision else None,
            "discounts": format_amount(revision.discounts) if revision else None,
            "total": format_amount(revision.total) if revision else None,
        },
        "evidence": [
            {
                "field": row.field_name,
                "raw_value": row.raw_value,
                "normalized_value": row.normalized_value,
                "corrected_value": row.corrected_value,
                "page_number": row.page_number,
                "snippet": row.snippet,
                "confidence": row.confidence,
                "uncertainty": (
                    None
                    if row.normalized_value is not None or row.corrected_value is not None
                    else "not_extracted_or_unreadable"
                ),
            }
            for row in evidence
        ],
    }


@router.get("/invoices/{invoice_id}/source")
async def get_invoice_source(
    invoice_id: UUID, principal: CurrentPrincipal, session: SessionDep
) -> Response:
    invoice = await session.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == principal.tenant_id)
    )
    if invoice is None:
        raise AppError(404, "not_found", "Invoice was not found.")
    key = settings.data_encryption_key
    if key is None:
        raise AppError(
            503, "storage_not_configured", "Private encrypted storage is not configured."
        )
    data = LocalBlobStore(settings.blob_root, key.get_secret_value().encode()).get(
        invoice.source_blob_id, invoice.source_sha256
    )
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=invoice-source"},
    )


@router.patch("/invoices/{invoice_id}/fields")
async def patch_invoice_fields(
    invoice_id: UUID,
    request: CorrectionRequest,
    principal: CurrentPrincipal,
    _: CsrfDep,
    session: SessionDep,
) -> dict[str, object]:
    from invoice_agent.services.invoice_service import apply_corrections

    revision = await apply_corrections(
        session,
        invoice_id=invoice_id,
        expected_revision=request.expected_revision,
        changes=request.changes,
        principal=principal,
    )
    return {"invoice_id": str(invoice_id), "revision": revision.revision}
