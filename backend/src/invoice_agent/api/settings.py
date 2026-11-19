from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import CurrentPrincipal
from invoice_agent.persistence.database import get_session

router = APIRouter(prefix="/api/v1", tags=["settings"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


class UploadLimitsResponse(BaseModel):
    formats: list[str]
    max_file_bytes: int
    max_pdf_pages: int
    max_image_pixels: int
    max_batch_files: int


@router.get("/session")
async def get_session_info(principal: CurrentPrincipal) -> dict[str, object]:
    from invoice_agent.config import settings

    return {
        "user_id": principal.user_id,
        "tenant_id": str(principal.tenant_id),
        "roles": sorted(principal.roles),
        "prototype_mode": settings.prototype_mode,
        "display_name": settings.prototype_user_name
        if settings.prototype_mode
        else principal.user_id,
    }


@router.get("/settings/upload-limits")
async def get_upload_limits(principal: CurrentPrincipal) -> UploadLimitsResponse:
    from invoice_agent.config import settings

    return UploadLimitsResponse(
        formats=["application/pdf", "image/jpeg", "image/png", "image/heic"],
        max_file_bytes=settings.max_upload_bytes,
        max_pdf_pages=settings.max_pdf_pages,
        max_image_pixels=settings.max_image_pixels,
        max_batch_files=1,
    )


@router.get("/settings/capabilities")
async def get_processing_capabilities(principal: CurrentPrincipal) -> dict[str, object]:
    from invoice_agent.config import settings
    from invoice_agent.services.ocr_engine import ocr_available, ocr_engine_name

    return {
        "prototype_mode": settings.prototype_mode,
        "prototype_warning": (
            "Prototype mode is local-only and is not for production use."
            if settings.prototype_mode
            else None
        ),
        "extraction_mode": (
            "local_text_patterns_manual_review"
            if settings.prototype_mode
            else "approved_model_when_configured"
        ),
        "ocr_available": ocr_available(),
        "ocr_engine": ocr_engine_name(),
        "model_configured": bool(
            settings.openrouter_api_key
            and settings.external_provider_approved
            and settings.openrouter_allowed_providers.strip()
        ),
        "authentication_required": True,
    }


@router.get("/settings/readiness")
async def get_readiness(principal: CurrentPrincipal) -> dict[str, object]:
    from invoice_agent.config import settings

    issues = settings.production_readiness_issues()
    return {
        "ready": not issues,
        "mode": "development_only" if issues else "configured",
        "release_gates": issues,
        "payment_actions": "never_supported",
    }
