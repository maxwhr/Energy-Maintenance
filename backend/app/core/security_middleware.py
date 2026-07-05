from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self.upload_paths = {
            "/api/media/upload",
            "/api/knowledge/upload",
            "/api/knowledge/documents/upload",
        }

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is None:
            return await call_next(request)
        try:
            body_size = int(content_length)
        except ValueError:
            return await call_next(request)
        limit_bytes = self._limit_bytes(request)
        if body_size > limit_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "code": 413,
                    "message": "Request body is too large",
                    "data": None,
                },
            )
        return await call_next(request)

    def _limit_bytes(self, request: Request) -> int:
        path = request.url.path
        content_type = request.headers.get("content-type", "").lower()
        if path in self.upload_paths or content_type.startswith("multipart/form-data"):
            return self.settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if "application/json" in content_type:
            return self.settings.SECURITY_MAX_JSON_BODY_MB * 1024 * 1024
        return self.settings.SECURITY_MAX_REQUEST_BODY_MB * 1024 * 1024


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self.events: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not self.settings.RATE_LIMIT_ENABLED or self._is_exempt(request.url.path):
            return await call_next(request)
        now = time.monotonic()
        key = (self._client_ip(request), self._path_group(request.url.path))
        window_start = now - self.settings.RATE_LIMIT_WINDOW_SECONDS
        event_queue = self.events[key]
        while event_queue and event_queue[0] < window_start:
            event_queue.popleft()
        if len(event_queue) >= self.settings.RATE_LIMIT_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "message": "Too many requests",
                    "data": None,
                },
            )
        event_queue.append(now)
        return await call_next(request)

    def _is_exempt(self, path: str) -> bool:
        return any(path == item or path.startswith(f"{item}/") for item in self.settings.rate_limit_exempt_paths)

    @staticmethod
    def _client_ip(request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
        return request.client.host if request.client else "unknown"

    @staticmethod
    def _path_group(path: str) -> str:
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2 and parts[0] == "api":
            return f"/api/{parts[1]}"
        return path or "/"
