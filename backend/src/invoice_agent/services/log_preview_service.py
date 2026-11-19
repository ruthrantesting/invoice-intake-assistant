import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import Principal
from invoice_agent.api.errors import AppError
from invoice_agent.domain.amounts import format_amount
from invoice_agent.persistence.invoice_models import Invoice, InvoiceRevision
from invoice_agent.persistence.validation_models import ValidationResultRow, ValidationRun
from invoice_agent.persistence.workbook_models import (
    ColumnMapping,
    LogPreview,
    Workbook,
    WorkbookVersion,
)
from invoice_agent.services.workbook_service import new_id

PREVIEW_TTL_MINUTES = 15


async def create_log_preview(
    session: AsyncSession,
    *,
    invoice_id: UUID,
    revision_number: int,
    workbook_id: UUID,
    workbook_version_id: str,
    mapping_id: str,
    principal: Principal,
) -> LogPreview:
    invoice = await session.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == principal.tenant_id)
    )
    workbook = await session.scalar(
        select(Workbook).where(
            Workbook.id == workbook_id, Workbook.tenant_id == principal.tenant_id
        )
    )
    if invoice is None or workbook is None:
        raise AppError(404, "not_found", "Invoice or workbook was not found.")
    if workbook.current_version_id != workbook_version_id:
        raise AppError(409, "stale_workbook", "The workbook changed. Refresh it before previewing.")
    version = await session.scalar(
        select(WorkbookVersion).where(
            WorkbookVersion.id == workbook_version_id, WorkbookVersion.workbook_id == workbook.id
        )
    )
    mapping = await session.scalar(
        select(ColumnMapping).where(
            ColumnMapping.id == mapping_id,
            ColumnMapping.workbook_id == workbook.id,
            ColumnMapping.confirmed_at.is_not(None),
        )
    )
    revision = await session.scalar(
        select(InvoiceRevision).where(
            InvoiceRevision.invoice_id == invoice.id, InvoiceRevision.revision == revision_number
        )
    )
    if (
        version is None
        or mapping is None
        or revision is None
        or invoice.current_revision != revision_number
    ):
        raise AppError(
            409, "stale_preview_inputs", "Invoice revision, workbook version, or mapping changed."
        )
    run = await session.scalar(
        select(ValidationRun)
        .where(
            ValidationRun.invoice_id == invoice.id,
            ValidationRun.revision == revision_number,
            ValidationRun.workbook_version_id == workbook_version_id,
            ValidationRun.mapping_id == mapping_id,
        )
        .order_by(ValidationRun.created_at.desc(), ValidationRun.id.desc())
        .limit(1)
    )
    if run is None:
        raise AppError(409, "validation_required", "Run validation before preparing a log preview.")
    results = list(
        await session.scalars(
            select(ValidationResultRow).where(ValidationResultRow.run_id == run.id)
        )
    )
    flags = [
        {"type": row.check_type, "outcome": row.outcome, "reason": row.reason} for row in results
    ]
    flags.sort(key=lambda item: (item["type"], item["outcome"], item["reason"]))
    flags_digest = hashlib.sha256(json.dumps(flags, sort_keys=True).encode()).hexdigest()
    row = {
        "vendor_name": revision.vendor,
        "invoice_number": revision.invoice_number,
        "invoice_date": revision.invoice_date_raw,
        "due_date": revision.due_date_raw,
        "po_number": revision.po_number,
        "currency": revision.currency,
        "subtotal": format_amount(revision.subtotal),
        "tax": format_amount(revision.tax),
        "other_charges": format_amount(revision.other_charges),
        "discounts": format_amount(revision.discounts),
        "total": format_amount(revision.total),
    }
    preview_id = new_id()
    payload = {
        "invoice_id": str(invoice.id),
        "invoice_revision": revision_number,
        "workbook_id": str(workbook.id),
        "workbook_version_id": version.id,
        "mapping_id": mapping.id,
        "row": row,
        "flags_digest": flags_digest,
        "worksheet": mapping.sheet_name,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    preview = LogPreview(
        id=preview_id,
        tenant_id=principal.tenant_id,
        invoice_id=invoice.id,
        invoice_revision=revision_number,
        workbook_id=workbook.id,
        workbook_version_id=version.id,
        mapping_id=mapping.id,
        proposed_row=json.dumps(row, sort_keys=True),
        flags_digest=flags_digest,
        preview_digest=digest,
        expires_at=datetime.now(UTC) + timedelta(minutes=PREVIEW_TTL_MINUTES),
        created_by=principal.user_id,
    )
    session.add(preview)
    await session.commit()
    return preview
