import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from salesos_shared.logging import request_id_context


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_context.set(correlation_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        response.headers["X-Correlation-ID"] = correlation_id
        return response
