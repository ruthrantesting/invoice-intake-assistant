from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.errors import AppError
from invoice_agent.config import settings
from invoice_agent.domain.duplicate_validation import DuplicateCandidate
from invoice_agent.domain.issue_validation import ValidationResult, run_issue_checks
from invoice_agent.persistence.invoice_models import Invoice, InvoiceRevision
from invoice_agent.persistence.validation_models import ValidationResultRow, ValidationRun


async def revalidate_for_write(
    session: AsyncSession,
    *,
    invoice_id: UUID,
    revision: int,
    workbook_version_id: str,
    mapping_id: str,
    tenant_id: UUID,
) -> list[ValidationResult]:
    invoice = await session.scalar(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant_id,
        )
    )
    current_revision = await session.scalar(
        select(InvoiceRevision).where(
            InvoiceRevision.invoice_id == invoice_id,
            InvoiceRevision.revision == revision,
        )
    )
    if invoice is None or current_revision is None:
        raise AppError(409, "invoice_changed", "Invoice changed before confirmation.")
    candidates = await session.execute(
        select(Invoice, InvoiceRevision)
        .join(InvoiceRevision, InvoiceRevision.invoice_id == Invoice.id)
        .where(
            Invoice.tenant_id == tenant_id,
            Invoice.id != invoice_id,
            Invoice.processing_status.in_(["ready_for_review", "logged"]),
            InvoiceRevision.revision == Invoice.current_revision,
        )
    )
    matches = [
        DuplicateCandidate(
            str(existing.id), record.invoice_number, record.vendor, existing.source_sha256
        )
        for existing, record in candidates
    ]
    workbook_candidates = await load_mapped_workbook_candidates(
        session,
        workbook_version_id=workbook_version_id,
        mapping_id=mapping_id,
        tenant_id=tenant_id,
    )
    matches.extend(workbook_candidates)
    try:
        tolerance_map = __import__("json").loads(settings.currency_tolerances_json)
        configured_tolerance = tolerance_map.get((current_revision.currency or "").upper())
        if configured_tolerance is None and settings.prototype_mode:
            configured_tolerance = "0.01"
        if configured_tolerance is None:
            raise KeyError(current_revision.currency)
        tolerance = Decimal(str(configured_tolerance))
    except (KeyError, ValueError, TypeError) as exc:
        raise AppError(
            503,
            "currency_tolerance_unconfigured",
            "Currency tolerance is not configured for this invoice.",
        ) from exc
    results = run_issue_checks(
        subtotal=current_revision.subtotal,
        tax=current_revision.tax,
        other_charges=current_revision.other_charges,
        discounts=current_revision.discounts,
        total=current_revision.total,
        tolerance=tolerance,
        po_number=current_revision.po_number,
        invoice_number=current_revision.invoice_number,
        vendor=current_revision.vendor,
        source_sha256=invoice.source_sha256,
        candidates=matches,
        comparison_scope=(
            f"tenant {tenant_id} accessible invoice records and workbook version "
            f"{workbook_version_id}"
        ),
    )
    run = ValidationRun(
        invoice_id=invoice_id,
        revision=revision,
        workbook_version_id=workbook_version_id,
        mapping_id=mapping_id,
        rule_config_version="configured-v1",
        actor_id="system",
    )
    session.add(run)
    await session.flush()
    for item in results:
        session.add(
            ValidationResultRow(
                run_id=run.id,
                check_type=item.check_type,
                outcome=item.outcome,
                reason=item.reason,
                matched_record_id=item.matched_record_id,
                comparison_scope=item.comparison_scope,
            )
        )
    await session.flush()
    return results


async def load_mapped_workbook_candidates(
    session: AsyncSession,
    *,
    workbook_version_id: str,
    mapping_id: str,
    tenant_id: UUID,
) -> list[DuplicateCandidate]:
    import json
    from io import BytesIO

    from openpyxl import load_workbook

    from invoice_agent.config import settings
    from invoice_agent.persistence.blob_store import LocalBlobStore
    from invoice_agent.persistence.workbook_models import ColumnMapping, WorkbookVersion

    mapping = await session.scalar(
        select(ColumnMapping).where(
            ColumnMapping.id == mapping_id,
            ColumnMapping.confirmed_at.is_not(None),
        )
    )
    version = await session.scalar(
        select(WorkbookVersion).where(WorkbookVersion.id == workbook_version_id)
    )
    if mapping is None or version is None:
        raise AppError(409, "validation_context_changed", "Workbook mapping or version changed.")
    if settings.data_encryption_key is None:
        raise AppError(
            503, "storage_not_configured", "Private encrypted storage is not configured."
        )
    blob_store = LocalBlobStore(
        settings.blob_root, settings.data_encryption_key.get_secret_value().encode()
    )
    content = blob_store.get(version.blob_id, version.sha256)
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=False)
    try:
        sheet = workbook[mapping.sheet_name]
        fields = json.loads(mapping.field_to_column)
        headers = {cell.value: cell.column - 1 for cell in sheet[1] if cell.value is not None}
        invoice_col = headers.get(fields.get("invoice_number"))
        vendor_col = headers.get(fields.get("vendor_name"))
        matches: list[DuplicateCandidate] = []
        for index, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            number = (
                row[invoice_col] if invoice_col is not None and invoice_col < len(row) else None
            )
            vendor = row[vendor_col] if vendor_col is not None and vendor_col < len(row) else None
            if number is not None or vendor is not None:
                matches.append(
                    DuplicateCandidate(
                        f"workbook:{version.id}:row:{index}",
                        str(number) if number is not None else None,
                        str(vendor) if vendor is not None else None,
                        None,
                    )
                )
        return matches
    finally:
        workbook.close()
