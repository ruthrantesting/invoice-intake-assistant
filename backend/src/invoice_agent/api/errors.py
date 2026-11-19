from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


def error_payload(
    code: str, message: str, details: dict[str, object] | None = None
) -> dict[str, object]:
    return {"code": code, "message": message, "details": details or {}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=error_payload(exc.code, exc.message)
        )

    @app.exception_handler(ValidationError)
    async def handle_validation_error(_: Request, __: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "invalid_request",
                "message": "Request validation failed.",
                "details": {},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _: Request, __: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422, content=error_payload("invalid_request", "Request validation failed.")
        )

    @app.exception_handler(HTTPException)
    async def handle_http_error(_: Request, exc: HTTPException) -> JSONResponse:
        code = {
            401: "unauthenticated",
            403: "forbidden",
            404: "not_found",
            413: "too_large",
            415: "unsupported_format",
            422: "invalid_request",
        }.get(exc.status_code, "request_failed")
        message = exc.detail if isinstance(exc.detail, str) else "Request could not be completed."
        return JSONResponse(status_code=exc.status_code, content=error_payload(code, message))

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "code": "service_unavailable",
                "message": "A required service is unavailable.",
                "details": {},
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=error_payload("internal_error", "The request could not be completed."),
        )
