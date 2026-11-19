from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import Principal
from invoice_agent.api.errors import AppError
from invoice_agent.persistence.audit_repository import record_event
from invoice_agent.persistence.invoice_models import (
    FieldEvidence,
    Invoice,
    InvoiceRevision,
)


async def apply_corrections(
    session: AsyncSession,
    *,
    invoice_id: UUID,
    expected_revision: int,
    changes: dict[str, str | None],
    principal: Principal,
) -> InvoiceRevision:
    invoice = await session.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.tenant_id == principal.tenant_id)
        .with_for_update()
    )
    if invoice is None:
        raise AppError(404, "not_found", "Invoice was not found.")
    if invoice.current_revision != expected_revision:
        raise AppError(
            409, "stale_revision", "The invoice changed. Reload it before correcting fields."
        )
    previous = await session.scalar(
        select(InvoiceRevision).where(
            InvoiceRevision.invoice_id == invoice.id,
            InvoiceRevision.revision == invoice.current_revision,
        )
    )
    if previous is None:
        raise AppError(409, "revision_missing", "The current invoice revision is unavailable.")
    allowed = {
        "vendor_name": "vendor",
        "invoice_number": "invoice_number",
        "invoice_date": "invoice_date_raw",
        "due_date": "due_date_raw",
        "po_number": "po_number",
        "currency": "currency",
        "subtotal": "subtotal",
        "tax": "tax",
        "other_charges": "other_charges",
        "discounts": "discounts",
        "total": "total",
    }
    if not changes or set(changes) - allowed.keys():
        raise AppError(422, "invalid_fields", "One or more invoice fields are unsupported.")
    values = {field: getattr(previous, field) for field in allowed.values()}
    audit_before: dict[str, str | None] = {}
    audit_after: dict[str, str | None] = {}
    for key, value in changes.items():
        field_name = allowed[key]
        prior = getattr(previous, field_name)
        audit_before[key] = str(prior) if prior is not None else None
        if key in {"subtotal", "tax", "other_charges", "discounts", "total"} and value is not None:
            from decimal import Decimal, InvalidOperation

            try:
                values[field_name] = Decimal(value)
            except InvalidOperation as exc:
                raise AppError(
                    422, "invalid_amount", "Amounts must be valid decimal strings."
                ) from exc
        else:
            values[field_name] = value
        audit_after[key] = value
    revision = InvoiceRevision(
        invoice_id=invoice.id, revision=invoice.current_revision + 1, **values
    )
    session.add(revision)
    await session.flush()
    original_evidence = await session.scalars(
        select(FieldEvidence).where(FieldEvidence.revision_id == previous.id)
    )
    for evidence in original_evidence:
        session.add(
            FieldEvidence(
                revision_id=revision.id,
                field_name=evidence.field_name,
                raw_value=evidence.raw_value,
                normalized_value=evidence.normalized_value,
                corrected_value=evidence.corrected_value,
                page_number=evidence.page_number,
                snippet=evidence.snippet,
                confidence=evidence.confidence,
                extraction_method=evidence.extraction_method,
            )
        )
    for key, value in changes.items():
        session.add(
            FieldEvidence(
                revision_id=revision.id,
                field_name=key,
                raw_value=str(getattr(previous, allowed[key]))
                if getattr(previous, allowed[key]) is not None
                else None,
                normalized_value=str(getattr(previous, allowed[key]))
                if getattr(previous, allowed[key]) is not None
                else None,
                corrected_value=value,
                extraction_method="user_correction",
            )
        )
    invoice.current_revision = revision.revision
    invoice.processing_status = "ready_for_review"
    invoice.review_status = "needs_review"
    await record_event(
        session,
        tenant_id=principal.tenant_id,
        actor_type="user",
        actor_id=principal.user_id,
        action="invoice.fields_corrected",
        resource_type="invoice",
        resource_id=str(invoice.id),
        outcome="success",
        details={"before": audit_before, "after": audit_after, "revision": revision.revision},
    )
    await session.commit()
    return revision
