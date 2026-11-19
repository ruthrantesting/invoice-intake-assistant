from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import Principal
from invoice_agent.api.errors import AppError
from invoice_agent.persistence.audit_repository import record_event
from invoice_agent.persistence.workbook_models import ColumnMapping
from invoice_agent.services.workbook_service import serialize_mapping, validate_mapping


async def save_mapping(
    session: AsyncSession,
    *,
    workbook_id: UUID,
    sheet_name: str,
    headers: list[str | None],
    mapping: dict[str, str],
    principal: Principal,
) -> ColumnMapping:
    try:
        validate_mapping(headers, mapping)
    except ValueError as exc:
        raise AppError(422, "invalid_mapping", str(exc)) from exc
    row = ColumnMapping(
        id=__import__("uuid").uuid4().hex,
        workbook_id=workbook_id,
        sheet_name=sheet_name,
        header_snapshot=__import__("json").dumps(headers, ensure_ascii=False),
        field_to_column=serialize_mapping(mapping),
        version=1,
        created_by=principal.user_id,
        confirmed_at=datetime.now(UTC),
    )
    session.add(row)
    await record_event(
        session,
        tenant_id=principal.tenant_id,
        actor_type="user",
        actor_id=principal.user_id,
        action="workbook.mapping_confirmed",
        resource_type="workbook",
        resource_id=str(workbook_id),
        outcome="success",
        details={"worksheet": sheet_name, "mapping_id": row.id},
    )
    await session.commit()
    return row
