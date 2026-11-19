from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import CurrentPrincipal, require_csrf, require_role
from invoice_agent.api.errors import AppError
from invoice_agent.persistence.database import get_session
from invoice_agent.persistence.workbook_models import LogOperation
from invoice_agent.services.log_operation_service import (
    confirm_log_operation,
    reconcile_log_operations,
)
from invoice_agent.services.log_preview_service import create_log_preview

router = APIRouter(prefix="/api/v1", tags=["logging"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CsrfDep = Annotated[None, Depends(require_csrf)]


class PreviewRequest(BaseModel):
    invoice_revision: int = Field(ge=1)
    workbook_id: UUID
    workbook_version_id: str
    mapping_id: str


class ConfirmationRequest(BaseModel):
    preview_id: str
    preview_digest: str


@router.post("/admin/log-recovery")
async def recover_log_operations(
    principal: CurrentPrincipal,
    _: CsrfDep,
    session: SessionDep,
) -> dict[str, object]:
    require_role(principal, "administrator")
    result = await reconcile_log_operations(session)
    return {"status": "completed", **result}


@router.post("/invoices/{invoice_id}/log-preview")
async def log_preview(
    invoice_id: UUID,
    request: PreviewRequest,
    principal: CurrentPrincipal,
    _: CsrfDep,
    session: SessionDep,
) -> dict[str, object]:
    preview = await create_log_preview(
        session,
        invoice_id=invoice_id,
        revision_number=request.invoice_revision,
        workbook_id=request.workbook_id,
        workbook_version_id=request.workbook_version_id,
        mapping_id=request.mapping_id,
        principal=principal,
    )
    return {
        "preview_id": preview.id,
        "expires_at": preview.expires_at.isoformat(),
        "invoice_revision": preview.invoice_revision,
        "workbook_id": str(preview.workbook_id),
        "workbook_version_id": preview.workbook_version_id,
        "mapping_id": preview.mapping_id,
        "proposed_row": preview.proposed_row,
        "flags_digest": preview.flags_digest,
        "preview_digest": preview.preview_digest,
    }


@router.post("/invoices/{invoice_id}/log-confirmations")
async def log_confirmation(
    invoice_id: UUID,
    request: ConfirmationRequest,
    principal: CurrentPrincipal,
    _: CsrfDep,
    session: SessionDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> dict[str, object]:
    operation = await confirm_log_operation(
        session,
        invoice_id=invoice_id,
        preview_id=request.preview_id,
        preview_digest=request.preview_digest,
        idempotency_key=idempotency_key,
        principal=principal,
    )
    return {
        "operation_id": operation.id,
        "state": operation.state,
        "workbook_version_id": operation.outcome_version_id,
    }


@router.get("/log-operations/{operation_id}")
async def get_log_operation(
    operation_id: str, principal: CurrentPrincipal, session: SessionDep
) -> dict[str, object]:
    operation = await session.scalar(
        select(LogOperation).where(
            LogOperation.id == operation_id, LogOperation.tenant_id == principal.tenant_id
        )
    )
    if operation is None:
        raise AppError(404, "not_found", "Log operation was not found.")
    return {
        "operation_id": operation.id,
        "state": operation.state,
        "workbook_id": str(operation.workbook_id),
        "invoice_id": str(operation.invoice_id),
        "workbook_version_id": operation.outcome_version_id,
        "error_code": operation.error_code,
    }
