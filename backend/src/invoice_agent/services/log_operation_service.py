import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import Principal
from invoice_agent.api.errors import AppError
from invoice_agent.config import settings
from invoice_agent.persistence.audit_repository import record_event
from invoice_agent.persistence.blob_store import LocalBlobStore
from invoice_agent.persistence.invoice_models import Invoice
from invoice_agent.persistence.validation_models import ValidationResultRow, ValidationRun
from invoice_agent.persistence.workbook_models import (
    ColumnMapping,
    LogOperation,
    LogPreview,
    Workbook,
    WorkbookVersion,
)
from invoice_agent.services.validation_service import revalidate_for_write
from invoice_agent.services.workbook_inspection import inspect_workbook_package


async def reconcile_log_operations(session: AsyncSession) -> dict[str, object]:
    """Find candidate blobs that were published before a crash but never committed."""
    pending = list(
        await session.scalars(select(LogOperation).where(LogOperation.state == "pending"))
    )
    referenced = {
        str(item.candidate_blob_id) for item in pending if item.candidate_blob_id is not None
    }
    key = settings.data_encryption_key
    orphan_ids: list[str] = []
    if key is not None:
        store = LocalBlobStore(settings.blob_root, key.get_secret_value().encode())
        # Keep all committed version blobs, source invoice blobs, and candidate blobs.
        from invoice_agent.persistence.invoice_models import Invoice

        source_ids = set(await session.scalars(select(Invoice.source_blob_id)))
        version_ids = set(await session.scalars(select(WorkbookVersion.blob_id)))
        all_referenced = source_ids | version_ids | referenced
        orphan_ids = store.reconcile_orphans(all_referenced)
    for operation in pending:
        candidate = operation.candidate_blob_id
        if candidate is None or candidate in orphan_ids:
            operation.state = "failed"
            operation.error_code = "orphan_candidate_reconciled"
    await session.commit()
    return {
        "pending_reconciled": sum(item.state == "failed" for item in pending),
        "orphan_blob_ids": orphan_ids,
    }


async def confirm_log_operation(
    session: AsyncSession,
    *,
    invoice_id: UUID,
    preview_id: str,
    preview_digest: str,
    idempotency_key: str,
    principal: Principal,
) -> LogOperation:
    if not idempotency_key or len(idempotency_key) > 255:
        raise AppError(400, "invalid_idempotency_key", "A valid Idempotency-Key is required.")
    preview = await session.scalar(
        select(LogPreview).where(
            LogPreview.id == preview_id,
            LogPreview.tenant_id == principal.tenant_id,
            LogPreview.invoice_id == invoice_id,
        )
    )
    expiry = (
        preview.expires_at.replace(tzinfo=UTC)
        if preview and preview.expires_at.tzinfo is None
        else preview.expires_at
        if preview
        else None
    )
    if preview is None or expiry < datetime.now(UTC) or preview.preview_digest != preview_digest:
        raise AppError(
            409,
            "preview_invalid",
            "The preview expired or changed. Prepare and review a new preview.",
        )
    workbook = await session.scalar(
        select(Workbook)
        .where(Workbook.id == preview.workbook_id, Workbook.tenant_id == principal.tenant_id)
        .with_for_update()
    )
    invoice = await session.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.tenant_id == principal.tenant_id)
        .with_for_update()
    )
    if workbook is None or invoice is None:
        raise AppError(404, "not_found", "Invoice or workbook was not found.")
    existing = await session.scalar(
        select(LogOperation).where(
            LogOperation.tenant_id == principal.tenant_id,
            LogOperation.workbook_id == workbook.id,
            LogOperation.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.request_digest != preview_digest or existing.preview_id != preview.id:
            raise AppError(
                409,
                "idempotency_mismatch",
                "The key was already used for different confirmation content.",
            )
        return existing
    if (
        invoice.current_revision != preview.invoice_revision
        or workbook.current_version_id != preview.workbook_version_id
    ):
        raise AppError(
            409,
            "stale_confirmation",
            "Invoice or workbook changed after preview. Review a new preview.",
        )
    current_results = await revalidate_for_write(
        session,
        invoice_id=invoice.id,
        revision=invoice.current_revision,
        workbook_version_id=preview.workbook_version_id,
        mapping_id=preview.mapping_id,
        tenant_id=principal.tenant_id,
    )
    await session.flush()
    stored_run = await session.scalar(
        select(ValidationRun)
        .where(
            ValidationRun.invoice_id == invoice.id,
            ValidationRun.revision == preview.invoice_revision,
            ValidationRun.workbook_version_id == preview.workbook_version_id,
            ValidationRun.mapping_id == preview.mapping_id,
        )
        .order_by(ValidationRun.created_at.desc(), ValidationRun.id.desc())
        .limit(1)
    )
    if stored_run is None:
        raise AppError(
            409, "validation_changed", "Validation results changed. Review a new preview."
        )
    stored_rows = list(
        await session.scalars(
            select(ValidationResultRow).where(ValidationResultRow.run_id == stored_run.id)
        )
    )
    stored_flags = [
        {"type": item.check_type, "outcome": item.outcome, "reason": item.reason}
        for item in stored_rows
    ]
    stored_flags.sort(key=lambda item: (item["type"], item["outcome"], item["reason"]))
    stored_digest = hashlib.sha256(json.dumps(stored_flags, sort_keys=True).encode()).hexdigest()
    if stored_digest != preview.flags_digest:
        raise AppError(
            409, "validation_changed", "Stored validation flags changed. Review a new preview."
        )
    stored_outcomes = sorted((item["type"], item["outcome"]) for item in stored_flags)
    current_outcomes = sorted((item.check_type, item.outcome) for item in current_results)
    if current_outcomes != stored_outcomes:
        raise AppError(
            409, "validation_changed", "Validation outcomes changed. Review a new preview."
        )
    mapping = await session.scalar(
        select(ColumnMapping).where(
            ColumnMapping.id == preview.mapping_id, ColumnMapping.workbook_id == workbook.id
        )
    )
    version = await session.scalar(
        select(WorkbookVersion).where(
            WorkbookVersion.id == preview.workbook_version_id,
            WorkbookVersion.workbook_id == workbook.id,
        )
    )
    if mapping is None or version is None:
        raise AppError(
            409, "preview_inputs_missing", "The preview mapping or workbook version is unavailable."
        )
    key = settings.data_encryption_key
    if key is None:
        raise AppError(
            503, "storage_not_configured", "Private encrypted storage is not configured."
        )
    blob_store = LocalBlobStore(settings.blob_root, key.get_secret_value().encode())
    source = blob_store.get(version.blob_id, version.sha256)
    inspect_workbook_package(source)
    row = json.loads(preview.proposed_row)
    mapping_values = json.loads(mapping.field_to_column)
    header_values = json.loads(mapping.header_snapshot)
    from invoice_agent.domain.workbook_safety import append_text_row
    from invoice_agent.services.workbook_service import build_row

    proposed = build_row(header_values, mapping_values, row)
    output = append_text_row(source, mapping.sheet_name, proposed)
    blob = blob_store.put(output)
    operation_id = __import__("uuid").uuid4().hex
    next_version_id = __import__("uuid").uuid4().hex
    operation = LogOperation(
        id=operation_id,
        tenant_id=principal.tenant_id,
        workbook_id=workbook.id,
        invoice_id=invoice.id,
        idempotency_key=idempotency_key,
        request_digest=preview_digest,
        preview_id=preview.id,
        confirming_user=principal.user_id,
        state="pending",
        candidate_blob_id=blob.blob_id,
    )
    next_version = WorkbookVersion(
        id=next_version_id,
        workbook_id=workbook.id,
        version_number=(
            await session.scalar(
                select(WorkbookVersion.version_number).where(WorkbookVersion.id == version.id)
            )
        )
        + 1,
        blob_id=blob.blob_id,
        sha256=blob.sha256,
        parent_version_id=version.id,
        profile_version=version.profile_version,
    )
    session.add_all([operation, next_version])
    await session.flush()
    cas = await session.execute(
        update(Workbook)
        .where(
            Workbook.id == workbook.id,
            Workbook.tenant_id == principal.tenant_id,
            Workbook.current_version_id == version.id,
        )
        .values(current_version_id=next_version.id)
    )
    if cas.rowcount != 1:
        await session.rollback()
        raise AppError(
            409, "stale_workbook", "Workbook changed during confirmation. Refresh and review again."
        )
    workbook.current_version_id = next_version.id
    invoice.processing_status = "logged"
    operation.state = "committed"
    operation.outcome_version_id = next_version.id
    await record_event(
        session,
        tenant_id=principal.tenant_id,
        actor_type="user",
        actor_id=principal.user_id,
        action="workbook.log_committed",
        resource_type="invoice",
        resource_id=str(invoice.id),
        outcome="success",
        details={"workbook_id": str(workbook.id), "version_id": next_version.id},
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "write_conflict",
            "The invoice or workbook changed during confirmation. Refresh and review again.",
        ) from exc
    return operation
