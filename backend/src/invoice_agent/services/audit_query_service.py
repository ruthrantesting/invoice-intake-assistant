from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.errors import AppError
from invoice_agent.persistence.invoice_models import Invoice
from invoice_agent.persistence.models import AuditEvent


async def list_invoice_audit(
    session: AsyncSession,
    *,
    invoice_id: UUID,
    tenant_id: UUID,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[AuditEvent], str | None]:
    invoice = await session.scalar(
        select(Invoice.id).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    )
    if invoice is None:
        raise AppError(404, "not_found", "Invoice was not found.")
    query = select(AuditEvent).where(
        AuditEvent.tenant_id == tenant_id,
        AuditEvent.resource_type == "invoice",
        AuditEvent.resource_id == str(invoice_id),
    )
    if cursor:
        try:
            cursor_id = UUID(cursor)
        except ValueError as exc:
            raise AppError(400, "invalid_cursor", "Audit cursor is invalid.") from exc
        last = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.id == cursor_id,
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.resource_type == "invoice",
                AuditEvent.resource_id == str(invoice_id),
            )
        )
        if last is None:
            raise AppError(400, "invalid_cursor", "Audit cursor is invalid.")
        query = query.where(
            tuple_(AuditEvent.occurred_at, AuditEvent.id) < tuple_(last.occurred_at, last.id)
        )
    rows = list(
        await session.scalars(
            query.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(
                min(max(limit, 1), 100) + 1
            )
        )
    )
    has_more = len(rows) > min(max(limit, 1), 100)
    rows = rows[: min(max(limit, 1), 100)]
    next_cursor = str(rows[-1].id) if has_more and rows else None
    return rows, next_cursor
