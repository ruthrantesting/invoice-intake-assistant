from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.api.auth import CurrentPrincipal, require_csrf
from invoice_agent.api.errors import AppError
from invoice_agent.persistence.chat_models import ChatMessage, ChatSession
from invoice_agent.persistence.database import get_session
from invoice_agent.services.chat_service import create_chat_session, send_chat_message

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CsrfDep = Annotated[None, Depends(require_csrf)]


class CreateChatRequest(BaseModel):
    invoice_id: UUID


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@router.post("/sessions", status_code=201)
async def create_session(
    request: CreateChatRequest, principal: CurrentPrincipal, _: CsrfDep, session: SessionDep
) -> dict[str, str]:
    chat = await create_chat_session(session, request.invoice_id, principal)
    return {"id": str(chat.id)}


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: UUID,
    request: MessageRequest,
    principal: CurrentPrincipal,
    _: CsrfDep,
    session: SessionDep,
) -> dict[str, str]:
    assistant, response = await send_chat_message(session, session_id, request.message, principal)
    return {"id": str(assistant.id), "message": response, "citations": [], "uncertainty": None}


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: UUID, principal: CurrentPrincipal, session: SessionDep
) -> dict[str, list[dict[str, str]]]:
    chat = await session.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.tenant_id == principal.tenant_id,
            ChatSession.user_id == principal.user_id,
        )
    )
    if chat is None:
        raise AppError(404, "not_found", "Chat session was not found.")
    messages = await session.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat.id)
        .order_by(ChatMessage.created_at)
    )
    return {
        "items": [
            {"id": str(message.id), "role": message.role, "content": message.content}
            for message in messages
        ],
        "next_cursor": None,
    }
