from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import Principal
from invoice_agent.api.errors import AppError
from invoice_agent.persistence.audit_repository import record_event
from invoice_agent.persistence.invoice_models import Invoice
from invoice_agent.persistence.review_models import ReviewEvent

ALLOWED_REVIEW_STATUSES = {"not_reviewed", "needs_review", "reviewed"}
MAX_NOTE_LENGTH = 4000


async def save_review(
    session: AsyncSession,
    *,
    invoice_id: UUID,
    status: str,
    note: str | None,
    principal: Principal,
) -> ReviewEvent:
    if status not in ALLOWED_REVIEW_STATUSES:
        raise AppError(422, "invalid_review_status", "Review status is unsupported.")
    if note is not None and len(note) > MAX_NOTE_LENGTH:
        raise AppError(422, "invalid_review_note", "Review note exceeds the supported length.")
    invoice = await session.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.tenant_id == principal.tenant_id)
        .with_for_update()
    )
    if invoice is None:
        raise AppError(404, "not_found", "Invoice was not found.")
    invoice.review_status = status
    event = ReviewEvent(
        invoice_id=invoice_id, status=status, reviewer_id=principal.user_id, note=note
    )
    session.add(event)
    await record_event(
        session,
        tenant_id=principal.tenant_id,
        actor_type="user",
        actor_id=principal.user_id,
        action="invoice.review_recorded",
        resource_type="invoice",
        resource_id=str(invoice_id),
        outcome="success",
        details={"status": status, "note": note, "meaning": "data_review_only"},
    )
    await session.commit()
    return event
