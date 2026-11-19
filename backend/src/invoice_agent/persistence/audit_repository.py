import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.persistence.models import AuditEvent


async def record_event(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_type: str,
    actor_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str,
    outcome: str,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        details=json.dumps(details, ensure_ascii=False) if details else None,
    )
    session.add(event)
    return event
