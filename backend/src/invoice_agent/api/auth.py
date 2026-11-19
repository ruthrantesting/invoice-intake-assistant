import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urljoin
from uuid import UUID

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from invoice_agent.config import settings

SESSION_COOKIE = "invoice_session"
SESSION_TTL_SECONDS = 8 * 60 * 60


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: UUID
    roles: frozenset[str]
    csrf_token: str


class OIDCSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, tuple[Principal, float]] = {}
        self._states: dict[str, float] = {}
        self.oauth = OAuth()
        if settings.oidc_issuer and settings.oidc_client_id and settings.oidc_client_secret:
            self.oauth.register(
                name="organization",
                client_id=settings.oidc_client_id,
                client_secret=settings.oidc_client_secret.get_secret_value(),
                server_metadata_url=(
                    f"{settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration"
                ),
                client_kwargs={"scope": "openid profile email"},
            )

    def issue(self, subject: str, tenant_id: UUID, roles: set[str]) -> tuple[str, Principal]:
        key = (
            settings.session_secret.get_secret_value().encode() if settings.session_secret else b""
        )
        if len(key) < 32:
            raise RuntimeError(
                "SESSION_SECRET must contain at least 32 bytes before sign-in is enabled."
            )
        token = secrets.token_urlsafe(32)
        principal = Principal(subject, tenant_id, frozenset(roles), secrets.token_urlsafe(32))
        token_digest = hmac.new(key, token.encode(), hashlib.sha256).hexdigest()
        self._sessions[token_digest] = (principal, time.time() + SESSION_TTL_SECONDS)
        return token, principal

    def resolve(self, token: str | None) -> Principal | None:
        if not token:
            return None
        key = (
            settings.session_secret.get_secret_value().encode() if settings.session_secret else b""
        )
        if len(key) < 32:
            return None
        token_digest = hmac.new(key, token.encode(), hashlib.sha256).hexdigest()
        saved = self._sessions.get(token_digest)
        if saved is None:
            return None
        principal, expiry = saved
        if expiry < time.time():
            self._sessions.pop(token_digest, None)
            return None
        return principal

    def revoke(self, token: str) -> None:
        key = (
            settings.session_secret.get_secret_value().encode() if settings.session_secret else b""
        )
        if len(key) >= 32:
            token_digest = hmac.new(key, token.encode(), hashlib.sha256).hexdigest()
            self._sessions.pop(token_digest, None)

    def create_state(self) -> str:
        state = secrets.token_urlsafe(32)
        self._states[state] = time.time() + 300
        return state

    def consume_state(self, state: str | None) -> bool:
        if not state:
            return False
        expiry = self._states.pop(state, 0)
        return expiry >= time.time()


session_manager = OIDCSessionManager()


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.principal = session_manager.resolve(request.cookies.get(SESSION_COOKIE))
        if (
            request.state.principal is None
            and settings.prototype_mode
            and settings.prototype_auto_login
        ):
            try:
                request.state.principal = Principal(
                    user_id=settings.prototype_user_id,
                    tenant_id=UUID(settings.prototype_tenant_id),
                    roles=frozenset({"operator", "reviewer", "administrator"}),
                    csrf_token="prototype-csrf-token",
                )
            except ValueError:
                request.state.principal = None
        response = await call_next(request)
        if isinstance(request.state.principal, Principal):
            response.set_cookie(
                key="invoice_csrf",
                value=request.state.principal.csrf_token,
                httponly=False,
                secure=not settings.prototype_mode,
                samesite="lax",
                max_age=SESSION_TTL_SECONDS,
                path="/",
            )
        return response


def _principal_from_request(request: Request) -> Principal:
    """Read a principal set by the verified OIDC session middleware."""
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal):
        raise HTTPException(status_code=401, detail="Authentication required.")
    return principal


async def current_principal(request: Request) -> Principal:
    return _principal_from_request(request)


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


async def require_csrf(
    request: Request,
    principal: CurrentPrincipal,
) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    token = request.headers.get("X-CSRF-Token")
    if token is None or not hmac.compare_digest(token, principal.csrf_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")


def require_role(principal: Principal, *allowed_roles: str) -> None:
    if not principal.roles.intersection(allowed_roles):
        raise HTTPException(status_code=403, detail="This operation is not permitted.")


def session_cookie_settings() -> dict[str, object]:
    return {
        "key": SESSION_COOKIE,
        "httponly": True,
        "secure": not settings.prototype_mode,
        "samesite": "lax",
        "max_age": SESSION_TTL_SECONDS,
        "path": "/",
    }


def csrf_cookie_settings() -> dict[str, object]:
    return {
        "key": "invoice_csrf",
        "httponly": False,
        "secure": not settings.prototype_mode,
        "samesite": "lax",
        "max_age": SESSION_TTL_SECONDS,
        "path": "/",
    }


def build_oidc_redirect_uri(request: Request) -> str:
    # Forwarded host headers are deliberately not trusted here.
    configured = settings.oidc_callback_url
    if configured:
        return configured
    if request.url.scheme != "https" and not settings.allow_insecure_local_auth:
        raise HTTPException(status_code=503, detail="HTTPS callback URL must be configured.")
    return urljoin(str(request.base_url), "/api/v1/auth/callback")
