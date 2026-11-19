from functools import lru_cache

from fastapi import HTTPException
from langchain_openrouter import ChatOpenRouter

from invoice_agent.config import settings


@lru_cache
def get_chat_model() -> ChatOpenRouter:
    if settings.prototype_mode:
        raise HTTPException(
            status_code=503,
            detail=(
                "AI services are disabled in local prototype mode. "
                "Review and correct fields manually."
            ),
        )
    if not settings.external_provider_approved:
        raise HTTPException(
            status_code=503,
            detail="External model processing is not enabled until provider approval is recorded.",
        )
    if settings.openrouter_api_key is None:
        raise HTTPException(status_code=503, detail="The configured model service is unavailable.")
    allowed = [
        name.strip() for name in settings.openrouter_allowed_providers.split(",") if name.strip()
    ]
    if not allowed:
        raise HTTPException(
            status_code=503,
            detail="Approved provider routing is not configured.",
        )
    try:
        return ChatOpenRouter(
            model="qwen/qwen3.7-flash",
            api_key=settings.openrouter_api_key.get_secret_value(),
            provider={"order": allowed, "allow_fallbacks": False},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="The configured model service is unavailable."
        ) from exc
