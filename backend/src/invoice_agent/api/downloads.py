from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import CurrentPrincipal
from invoice_agent.api.errors import AppError
from invoice_agent.config import settings
from invoice_agent.persistence.blob_store import LocalBlobStore
from invoice_agent.persistence.database import get_session
from invoice_agent.persistence.workbook_models import Workbook, WorkbookVersion

router = APIRouter(prefix="/api/v1/workbooks", tags=["workbooks"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/{workbook_id}/versions/{version_id}/download")
async def download_workbook(
    workbook_id: UUID, version_id: str, principal: CurrentPrincipal, session: SessionDep
) -> Response:
    workbook = await session.scalar(
        select(Workbook).where(
            Workbook.id == workbook_id, Workbook.tenant_id == principal.tenant_id
        )
    )
    version = await session.scalar(
        select(WorkbookVersion).where(
            WorkbookVersion.id == version_id, WorkbookVersion.workbook_id == workbook_id
        )
    )
    if workbook is None or version is None:
        raise AppError(404, "not_found", "Workbook version was not found.")
    if settings.data_encryption_key is None:
        raise AppError(
            503, "storage_not_configured", "Private encrypted storage is not configured."
        )
    content = LocalBlobStore(
        settings.blob_root, settings.data_encryption_key.get_secret_value().encode()
    ).get(version.blob_id, version.sha256)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="managed-workbook-{version.version_number}.xlsx"'
            ),
            "X-Workbook-Copy": "application-managed",
        },
    )
