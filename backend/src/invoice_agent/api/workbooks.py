import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import CurrentPrincipal, require_csrf
from invoice_agent.api.errors import AppError
from invoice_agent.config import settings
from invoice_agent.persistence.audit_repository import record_event
from invoice_agent.persistence.blob_store import LocalBlobStore
from invoice_agent.persistence.database import get_session
from invoice_agent.persistence.workbook_models import ColumnMapping, Workbook, WorkbookVersion
from invoice_agent.services.mapping_service import save_mapping
from invoice_agent.services.workbook_creation_service import create_log
from invoice_agent.services.workbook_inspection import inspect_workbook_package
from invoice_agent.services.workbook_service import PROFILE_VERSION, new_id

router = APIRouter(prefix="/api/v1", tags=["workbooks"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CsrfDep = Annotated[None, Depends(require_csrf)]


class NewWorkbookRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    headers: list[str] = Field(min_length=1, max_length=200)


class MappingRequest(BaseModel):
    expected_version_id: str
    sheet: str
    field_to_column: dict[str, str]


def _blob_store() -> LocalBlobStore:
    if settings.data_encryption_key is None:
        raise AppError(
            503, "storage_not_configured", "Private encrypted storage is not configured."
        )
    return LocalBlobStore(
        settings.blob_root, settings.data_encryption_key.get_secret_value().encode()
    )


@router.post("/workbooks", status_code=201)
async def upload_workbook(
    principal: CurrentPrincipal,
    _: CsrfDep,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> dict[str, object]:
    data = await file.read(50 * 1024 * 1024 + 1)
    try:
        inspection = inspect_workbook_package(data)
    except ValueError as exc:
        raise AppError(422, "unsupported_workbook", str(exc)) from exc
    blob = _blob_store().put(data)
    workbook = Workbook(
        tenant_id=principal.tenant_id,
        label=(file.filename or "Invoice log.xlsx")[:255],
        source_blob_id=blob.blob_id,
        created_by=principal.user_id,
    )
    session.add(workbook)
    await session.flush()
    version_id = new_id()
    version = WorkbookVersion(
        id=version_id,
        workbook_id=workbook.id,
        version_number=1,
        blob_id=blob.blob_id,
        sha256=blob.sha256,
        profile_version=PROFILE_VERSION,
    )
    session.add(version)
    workbook.current_version_id = version_id
    await record_event(
        session,
        tenant_id=principal.tenant_id,
        actor_type="user",
        actor_id=principal.user_id,
        action="workbook.uploaded",
        resource_type="workbook",
        resource_id=str(workbook.id),
        outcome="success",
        details={"sha256": blob.sha256},
    )
    await session.commit()
    return {"workbook_id": str(workbook.id), "version_id": version_id, **inspection}


@router.post("/workbooks/new", status_code=201)
async def new_workbook(
    request: NewWorkbookRequest, principal: CurrentPrincipal, _: CsrfDep, session: SessionDep
) -> dict[str, object]:
    try:
        label, data = create_log(request.name, request.headers)
    except ValueError as exc:
        raise AppError(422, "invalid_workbook_layout", str(exc)) from exc
    blob = _blob_store().put(data)
    workbook = Workbook(
        tenant_id=principal.tenant_id,
        label=label,
        source_blob_id=blob.blob_id,
        created_by=principal.user_id,
    )
    session.add(workbook)
    await session.flush()
    version_id = new_id()
    session.add(
        WorkbookVersion(
            id=version_id,
            workbook_id=workbook.id,
            version_number=1,
            blob_id=blob.blob_id,
            sha256=blob.sha256,
            profile_version=PROFILE_VERSION,
        )
    )
    workbook.current_version_id = version_id
    await session.commit()
    return {
        "workbook_id": str(workbook.id),
        "version_id": version_id,
        "profile_version": PROFILE_VERSION,
        "sheets": [{"name": "Invoice Log", "headers": request.headers}],
    }


@router.get("/workbooks/{workbook_id}")
async def get_workbook(
    workbook_id: UUID, principal: CurrentPrincipal, session: SessionDep
) -> dict[str, object]:
    workbook = await session.scalar(
        select(Workbook).where(
            Workbook.id == workbook_id, Workbook.tenant_id == principal.tenant_id
        )
    )
    if workbook is None:
        raise AppError(404, "not_found", "Workbook was not found.")
    version = await session.scalar(
        select(WorkbookVersion).where(WorkbookVersion.id == workbook.current_version_id)
    )
    mappings = await session.scalars(
        select(ColumnMapping).where(ColumnMapping.workbook_id == workbook.id)
    )
    blob_data = _blob_store().get(version.blob_id, version.sha256) if version else b""
    inspection = inspect_workbook_package(blob_data) if blob_data else {"sheets": []}
    return {
        "id": str(workbook.id),
        "label": workbook.label,
        "current_version_id": workbook.current_version_id,
        **inspection,
        "mappings": [
            {
                "id": item.id,
                "sheet": item.sheet_name,
                "field_to_column": json.loads(item.field_to_column),
            }
            for item in mappings
        ],
    }


@router.post("/workbooks/{workbook_id}/mappings", status_code=201)
async def create_mapping(
    workbook_id: UUID,
    request: MappingRequest,
    principal: CurrentPrincipal,
    _: CsrfDep,
    session: SessionDep,
) -> dict[str, object]:
    workbook = await session.scalar(
        select(Workbook).where(
            Workbook.id == workbook_id, Workbook.tenant_id == principal.tenant_id
        )
    )
    if workbook is None:
        raise AppError(404, "not_found", "Workbook was not found.")
    if workbook.current_version_id != request.expected_version_id:
        raise AppError(
            409, "stale_workbook", "Workbook changed. Reload and confirm the mapping again."
        )
    version = await session.scalar(
        select(WorkbookVersion).where(WorkbookVersion.id == request.expected_version_id)
    )
    if version is None:
        raise AppError(409, "version_missing", "Workbook version is unavailable.")
    inspection = inspect_workbook_package(_blob_store().get(version.blob_id, version.sha256))
    sheet = next((item for item in inspection["sheets"] if item["name"] == request.sheet), None)
    if sheet is None:
        raise AppError(422, "invalid_sheet", "Selected worksheet was not found.")
    mapping = await save_mapping(
        session,
        workbook_id=workbook_id,
        sheet_name=request.sheet,
        headers=sheet["headers"],
        mapping=request.field_to_column,
        principal=principal,
    )
    return {
        "mapping_id": mapping.id,
        "sheet": mapping.sheet_name,
        "field_to_column": request.field_to_column,
        "confirmed": True,
    }
