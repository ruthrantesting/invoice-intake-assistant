from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.persistence.audit_repository import record_event


@asynccontextmanager
async def audited_transaction(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_type: str,
    actor_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str,
    outcome: str = "success",
    details: dict[str, Any] | None = None,
) -> AsyncIterator[AsyncSession]:
    try:
        async with session.begin():
            await record_event(
                session,
                tenant_id=tenant_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=outcome,
                details=details,
            )
            yield session
    except Exception:
        await session.rollback()
        raise
