import json
import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware


request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger("ecommerce_ops")


def current_request_id() -> str | None:
    return request_id_context.get()


def log_event(event: str, **fields):
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log_event(
                "http_request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            raise
        finally:
            request_id_context.reset(token)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        log_event(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return response
