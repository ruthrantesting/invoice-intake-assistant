from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import CurrentPrincipal, require_csrf
from invoice_agent.persistence.database import get_session
from invoice_agent.services.review_service import save_review

router = APIRouter(prefix="/api/v1/invoices", tags=["review"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CsrfDep = Annotated[None, Depends(require_csrf)]


class ReviewRequest(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=4000)


@router.post("/{invoice_id}/review")
async def review_invoice(
    invoice_id: UUID,
    request: ReviewRequest,
    principal: CurrentPrincipal,
    _: CsrfDep,
    session: SessionDep,
) -> dict[str, object]:
    event = await save_review(
        session,
        invoice_id=invoice_id,
        status=request.status,
        note=request.note,
        principal=principal,
    )
    return {
        "id": str(event.id),
        "status": event.status,
        "reviewer_id": event.reviewer_id,
        "created_at": event.created_at.isoformat(),
        "meaning": "data_review_only_not_payment_approval",
    }
