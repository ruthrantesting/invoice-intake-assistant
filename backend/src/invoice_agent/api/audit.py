from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import CurrentPrincipal
from invoice_agent.persistence.database import get_session
from invoice_agent.services.audit_query_service import list_invoice_audit

router = APIRouter(prefix="/api/v1/invoices", tags=["audit"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/{invoice_id}/audit")
async def get_invoice_audit(
    invoice_id: UUID,
    principal: CurrentPrincipal,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    rows, next_cursor = await list_invoice_audit(
        session, invoice_id=invoice_id, tenant_id=principal.tenant_id, limit=limit, cursor=cursor
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "actor_type": row.actor_type,
                "actor_id": row.actor_id,
                "timestamp": row.occurred_at.isoformat(),
                "action": row.action,
                "resource_type": row.resource_type,
                "outcome": row.outcome,
                "details": row.details,
            }
            for row in rows
        ],
        "next_cursor": next_cursor,
    }
