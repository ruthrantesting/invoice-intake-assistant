import logging
import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.config import settings
from invoice_agent.persistence.audit_repository import record_event
from invoice_agent.persistence.blob_store import LocalBlobStore
from invoice_agent.persistence.invoice_models import FieldEvidence, Invoice, InvoiceRevision
from invoice_agent.persistence.job_repository import Job
from invoice_agent.services.document_service import PageText, extract_document_text
from invoice_agent.services.extraction_service import extract_invoice_fields
from invoice_agent.services.prototype_extraction import extract_prototype_fields

logger = logging.getLogger("invoice_agent.worker")


async def process_extraction_job(
    session: AsyncSession, job_id: UUID, worker_id: str | None = None
) -> None:
    started = time.perf_counter()
    job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if job is None or job.state != "leased":
        return
    if worker_id is not None and job.lease_owner != worker_id:
        return
    invoice = await session.scalar(
        select(Invoice)
        .where(Invoice.id == job.invoice_id, Invoice.tenant_id == job.tenant_id)
        .with_for_update()
    )
    if invoice is None:
        job.state = "failed"
        job.error_code = "invoice_missing"
        await session.commit()
        return
    try:
        key = settings.data_encryption_key
        if key is None:
            raise RuntimeError("storage_not_configured")
        source = LocalBlobStore(settings.blob_root, key.get_secret_value().encode()).get(
            invoice.source_blob_id, invoice.source_sha256
        )
        from invoice_agent.services.upload_service import validate_invoice_upload

        validation = validate_invoice_upload(
            f"source.{_extension(invoice.source_media_type)}", source
        )
        try:
            pages = extract_document_text(source, validation.media_type)
        except ValueError as exc:
            if settings.prototype_mode and "OCR is unavailable" in str(exc):
                pages = [PageText(1, "", "ocr_unavailable")]
            else:
                raise
        if settings.prototype_mode:
            extraction = extract_prototype_fields(pages)
        else:
            extraction = await extract_invoice_fields(pages)
        revision = await session.scalar(
            select(InvoiceRevision).where(
                InvoiceRevision.invoice_id == invoice.id,
                InvoiceRevision.revision == invoice.current_revision,
            )
        )
        if revision is None:
            raise RuntimeError("revision_missing")
        fields = {
            "vendor_name": ("vendor", extraction.vendor_name),
            "invoice_number": ("invoice_number", extraction.invoice_number),
            "invoice_date": ("invoice_date_raw", extraction.invoice_date),
            "due_date": ("due_date_raw", extraction.due_date),
            "po_number": ("po_number", extraction.po_number),
            "currency": ("currency", extraction.currency),
            "subtotal": ("subtotal", extraction.subtotal),
            "tax": ("tax", extraction.tax),
            "other_charges": ("other_charges", extraction.other_charges),
            "discounts": ("discounts", extraction.discounts),
            "total": ("total", extraction.total),
        }
        for name, (attribute, item) in fields.items():
            raw = item.raw_value if item else None
            normalized = item.normalized_value if item else None
            if attribute in {"subtotal", "tax", "other_charges", "discounts", "total"}:
                from decimal import Decimal, InvalidOperation

                try:
                    setattr(
                        revision, attribute, Decimal(normalized) if normalized is not None else None
                    )
                except InvalidOperation:
                    setattr(revision, attribute, None)
            else:
                setattr(revision, attribute, normalized)
            session.add(
                FieldEvidence(
                    revision_id=revision.id,
                    field_name=name,
                    raw_value=raw,
                    normalized_value=normalized,
                    page_number=item.page_number if item else None,
                    snippet=item.evidence_snippet if item else None,
                    confidence=item.confidence if item else None,
                    extraction_method=(
                        "prototype_patterns" if settings.prototype_mode else "llm_structured"
                    ),
                )
            )
        invoice.processing_status = "ready_for_review"
        invoice.review_status = "needs_review"
        job.state = "completed"
        job.lease_owner = None
        job.lease_expires_at = None
        job.error_code = None
        await record_event(
            session,
            tenant_id=invoice.tenant_id,
            actor_type="system",
            actor_id=None,
            action="invoice.extraction_completed",
            resource_type="invoice",
            resource_id=str(invoice.id),
            outcome="success",
            details={"revision": revision.revision, "pages": len(pages)},
        )
    except Exception as exc:
        retryable = job.attempts < 3
        invoice.processing_status = "received" if retryable else "failed"
        job.state = "retry" if retryable else "failed"
        job.error_code = _safe_error_code(exc)
        job.lease_owner = None
        job.lease_expires_at = None
        job.lease_owner = None
        job.lease_expires_at = None
        if retryable:
            from datetime import UTC, datetime, timedelta

            job.next_attempt_at = datetime.now(UTC) + timedelta(seconds=min(2**job.attempts, 60))
        await record_event(
            session,
            tenant_id=invoice.tenant_id,
            actor_type="system",
            actor_id=None,
            action="invoice.extraction_failed",
            resource_type="invoice",
            resource_id=str(invoice.id),
            outcome="failed",
            details={"error_code": job.error_code},
        )
    await session.commit()
    logger.info(
        "invoice_job_completed",
        extra={
            "job_id": str(job_id),
            "stage": "extract",
            "state": job.state,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "error_code": job.error_code,
        },
    )


def _safe_error_code(exc: Exception) -> str:
    value = str(exc)
    allowed = {"storage_not_configured", "revision_missing"}
    if value in allowed:
        return value
    if "provider approval" in value.lower() or "model service" in value.lower():
        return "model_unavailable_or_unapproved"
    if "OCR is unavailable" in value:
        return "ocr_unavailable"
    return "processing_failed"


def _extension(media_type: str) -> str:
    return {
        "application/pdf": "pdf",
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/heic": "heic",
        "image/heif": "heif",
    }.get(media_type, "bin")
