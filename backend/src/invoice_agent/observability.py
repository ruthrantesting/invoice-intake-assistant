import logging
import time
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("invoice_agent.request")


class SafeRequestMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.error(
                "request_failed",
                extra={
                    "method": request.method,
                    "path_template": request.scope.get("route"),
                    "outcome": "error",
                },
            )
            raise
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path_template": request.scope.get("route"),
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response


def summarize_job_transition(
    stage: str, state: str, duration_ms: float, error_code: str | None = None
) -> dict[str, Any]:
    return {
        "stage": stage,
        "state": state,
        "duration_ms": round(duration_ms, 2),
        "error_code": error_code,
    }
