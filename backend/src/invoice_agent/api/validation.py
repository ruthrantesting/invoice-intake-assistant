import json
from decimal import Decimal
from io import BytesIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from openpyxl import load_workbook
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import CurrentPrincipal, require_csrf
from invoice_agent.api.errors import AppError
from invoice_agent.config import settings
from invoice_agent.domain.duplicate_validation import DuplicateCandidate
from invoice_agent.domain.issue_validation import run_issue_checks
from invoice_agent.persistence.blob_store import LocalBlobStore
from invoice_agent.persistence.database import get_session
from invoice_agent.persistence.invoice_models import Invoice, InvoiceRevision
from invoice_agent.persistence.invoice_models import Invoice as InvoiceModel
from invoice_agent.persistence.validation_models import ValidationResultRow, ValidationRun
from invoice_agent.persistence.workbook_models import ColumnMapping, Workbook, WorkbookVersion
from invoice_agent.services.workbook_inspection import inspect_workbook_package

router = APIRouter(prefix="/api/v1", tags=["validation"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CsrfDep = Annotated[None, Depends(require_csrf)]


class ValidationRequest(BaseModel):
    workbook_id: UUID | None = None
    workbook_version_id: str | None = None
    mapping_id: str | None = None


def _decimal(value: Decimal | None) -> Decimal | None:
    return value


@router.post("/invoices/{invoice_id}/validate")
async def validate_invoice(
    invoice_id: UUID,
    request: ValidationRequest,
    principal: CurrentPrincipal,
    _: CsrfDep,
    session: SessionDep,
) -> dict[str, object]:
    invoice = await session.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == principal.tenant_id)
    )
    if invoice is None:
        raise AppError(404, "not_found", "Invoice was not found.")
    revision = await session.scalar(
        select(InvoiceRevision).where(
            InvoiceRevision.invoice_id == invoice_id,
            InvoiceRevision.revision == invoice.current_revision,
        )
    )
    if revision is None:
        raise AppError(409, "revision_missing", "The current invoice revision is unavailable.")
    candidates_rows = await session.execute(
        select(InvoiceModel, InvoiceRevision)
        .join(InvoiceRevision, InvoiceRevision.invoice_id == InvoiceModel.id)
        .where(
            InvoiceModel.tenant_id == principal.tenant_id,
            InvoiceModel.id != invoice_id,
            InvoiceModel.processing_status.in_(["ready_for_review", "logged"]),
            InvoiceRevision.revision == InvoiceModel.current_revision,
        )
    )
    candidates = [
        DuplicateCandidate(
            str(row.id),
            candidate_revision.invoice_number,
            candidate_revision.vendor,
            row.source_sha256,
        )
        for row, candidate_revision in candidates_rows.all()
    ]
    if request.workbook_id and request.workbook_version_id:
        workbook = await session.scalar(
            select(Workbook).where(
                Workbook.id == request.workbook_id,
                Workbook.tenant_id == principal.tenant_id,
            )
        )
        version = await session.scalar(
            select(WorkbookVersion).where(
                WorkbookVersion.id == request.workbook_version_id,
                WorkbookVersion.workbook_id == request.workbook_id,
            )
        )
        mapping = (
            await session.scalar(
                select(ColumnMapping).where(
                    ColumnMapping.id == request.mapping_id,
                    ColumnMapping.workbook_id == request.workbook_id,
                    ColumnMapping.confirmed_at.is_not(None),
                )
            )
            if request.mapping_id
            else None
        )
        if (
            workbook is None
            or version is None
            or mapping is None
            or workbook.current_version_id != version.id
        ):
            raise AppError(
                409, "stale_workbook", "Workbook version changed. Refresh before validation."
            )
        if settings.data_encryption_key is None:
            raise AppError(
                503, "storage_not_configured", "Private encrypted storage is not configured."
            )
        blob = LocalBlobStore(
            settings.blob_root, settings.data_encryption_key.get_secret_value().encode()
        )
        workbook_bytes = blob.get(version.blob_id, version.sha256)
        inspect_workbook_package(workbook_bytes)
        workbook_file = load_workbook(BytesIO(workbook_bytes), read_only=True, data_only=False)
        try:
            sheet = workbook_file[mapping.sheet_name]
            field_map = json.loads(mapping.field_to_column)
            header_indices = {
                cell.value: cell.column - 1 for cell in sheet[1] if cell.value is not None
            }
            invoice_column = header_indices.get(field_map.get("invoice_number"))
            vendor_column = header_indices.get(field_map.get("vendor_name"))
            for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                invoice_number = (
                    row[invoice_column]
                    if invoice_column is not None and invoice_column < len(row)
                    else None
                )
                vendor = (
                    row[vendor_column]
                    if vendor_column is not None and vendor_column < len(row)
                    else None
                )
                if invoice_number is not None or vendor is not None:
                    candidates.append(
                        DuplicateCandidate(
                            f"workbook:{version.id}:row:{row_number}",
                            str(invoice_number) if invoice_number is not None else None,
                            str(vendor) if vendor is not None else None,
                            None,
                        )
                    )
        finally:
            workbook_file.close()
    tolerances = __import__("json").loads(settings.currency_tolerances_json)
    configured_tolerance = tolerances.get((revision.currency or "").upper())
    if configured_tolerance is None and settings.prototype_mode:
        # Prototype convenience only; currency policy remains an explicit production gate.
        configured_tolerance = "0.01"
    if configured_tolerance is None:
        raise AppError(
            503,
            "currency_tolerance_unconfigured",
            "Currency tolerance is not configured for this invoice.",
        )
    tolerance = Decimal(str(configured_tolerance))
    results = run_issue_checks(
        subtotal=_decimal(revision.subtotal),
        tax=_decimal(revision.tax),
        other_charges=_decimal(revision.other_charges),
        discounts=_decimal(revision.discounts),
        total=_decimal(revision.total),
        tolerance=tolerance,
        po_number=revision.po_number,
        invoice_number=revision.invoice_number,
        vendor=revision.vendor,
        source_sha256=invoice.source_sha256,
        candidates=candidates,
        comparison_scope=(
            f"tenant {principal.tenant_id} accessible invoice records"
            + (
                f" and workbook version {request.workbook_version_id}"
                if request.workbook_version_id
                else ""
            )
        ),
    )
    run = ValidationRun(
        invoice_id=invoice_id,
        revision=revision.revision,
        workbook_version_id=request.workbook_version_id,
        mapping_id=request.mapping_id,
        rule_config_version="configured-v1",
        actor_id=principal.user_id,
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
    invoice.latest_validation_run_id = run.id
    await session.commit()
    return {
        "run_id": str(run.id),
        "revision": revision.revision,
        "results": [item.__dict__ for item in results],
    }


@router.get("/invoices/{invoice_id}/validation")
async def get_validation(
    invoice_id: UUID, principal: CurrentPrincipal, session: SessionDep
) -> dict[str, object]:
    invoice = await session.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == principal.tenant_id)
    )
    if invoice is None:
        raise AppError(404, "not_found", "Invoice was not found.")
    run = await session.scalar(
        select(ValidationRun)
        .where(ValidationRun.invoice_id == invoice_id)
        .order_by(ValidationRun.created_at.desc())
        .limit(1)
    )
    if run is None:
        return {"items": [], "next_cursor": None}
    rows = await session.scalars(
        select(ValidationResultRow).where(ValidationResultRow.run_id == run.id)
    )
    return {
        "run_id": str(run.id),
        "items": [
            {
                "check_type": r.check_type,
                "outcome": r.outcome,
                "reason": r.reason,
                "matched_record_id": r.matched_record_id,
                "comparison_scope": r.comparison_scope,
            }
            for r in rows
        ],
        "next_cursor": None,
    }
