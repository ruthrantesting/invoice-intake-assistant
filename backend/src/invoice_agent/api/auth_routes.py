from uuid import UUID

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from invoice_agent.api.auth import (
    SESSION_COOKIE,
    build_oidc_redirect_uri,
    csrf_cookie_settings,
    session_cookie_settings,
    session_manager,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.get("/status")
async def auth_status() -> dict[str, bool]:
    from invoice_agent.config import settings

    return {
        "configured": settings.prototype_mode
        or session_manager.oauth.create_client("organization") is not None,
        "prototype_mode": settings.prototype_mode,
    }


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    client = session_manager.oauth.create_client("organization")
    if client is None:
        raise HTTPException(status_code=503, detail="Organization sign-in is not configured.")
    redirect_uri = build_oidc_redirect_uri(request)
    state = session_manager.create_state()
    return await client.authorize_redirect(request, redirect_uri, state=state)


@router.get("/callback")
async def callback(request: Request) -> Response:
    client = session_manager.oauth.create_client("organization")
    if client is None:
        raise HTTPException(status_code=503, detail="Organization sign-in is not configured.")
    if not session_manager.consume_state(request.query_params.get("state")):
        raise HTTPException(
            status_code=401, detail="Organization sign-in state is invalid or expired."
        )
    try:
        token = await client.authorize_access_token(request)
        userinfo = token.get("userinfo") or await client.userinfo(token=token)
    except (OAuthError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Organization sign-in failed.") from exc
    subject = userinfo.get("sub")
    tenant_claim = userinfo.get("tenant_id")
    role_claim = userinfo.get("roles", [])
    if not isinstance(subject, str) or not isinstance(tenant_claim, str):
        raise HTTPException(
            status_code=403, detail="The identity is missing required organization claims."
        )
    try:
        tenant_id = UUID(tenant_claim)
    except ValueError as exc:
        raise HTTPException(
            status_code=403, detail="The identity has an invalid tenant claim."
        ) from exc
    if not isinstance(role_claim, list) or not all(isinstance(role, str) for role in role_claim):
        raise HTTPException(status_code=403, detail="The identity has invalid role claims.")
    try:
        session_token, principal = session_manager.issue(subject, tenant_id, set(role_claim))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail="Server-side session security is not configured."
        ) from exc
    response = RedirectResponse(url="/", status_code=303)
    cookie_options = session_cookie_settings()
    response.set_cookie(value=session_token, **cookie_options)
    response.set_cookie(value=principal.csrf_token, **csrf_cookie_settings())
    return response


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, str]:
    from invoice_agent.api.auth import current_principal

    await current_principal(request)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session_manager.revoke(token)
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    response.delete_cookie("invoice_csrf", path="/", secure=True, httponly=False, samesite="lax")
    return {"status": "signed_out"}
