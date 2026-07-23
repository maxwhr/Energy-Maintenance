from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)

HTTP_STATUS_TO_BUSINESS_CODE = {
    400: 40000,
    401: 40100,
    403: 40300,
    404: 40400,
    409: 40900,
    413: 41300,
    422: 42200,
    429: 42900,
    500: 50000,
}


def http_status_from_business_code(
    business_code: int,
    *,
    default: int = 400,
) -> int:
    prefix = str(abs(int(business_code)))[:3]
    status = int(prefix) if prefix.isdigit() else default
    return status if status in HTTP_STATUS_TO_BUSINESS_CODE else default


class BusinessException(Exception):
    def __init__(
        self,
        message: str,
        business_code: int,
        http_status: int | None = None,
        data: Any | None = None,
    ) -> None:
        safe_message = _safe_business_message(message)
        super().__init__(safe_message)
        self.message = safe_message
        self.business_code = business_code
        self.http_status = (
            http_status
            if http_status is not None
            else http_status_from_business_code(business_code)
        )
        self.data = data

    @classmethod
    def from_service_error(
        cls,
        exc: Exception,
        business_code: int,
        *,
        default_status: int | None = None,
    ) -> "BusinessException":
        message = str(exc) or "Request failed"
        normalized = message.casefold()
        if "not found" in normalized or "does not exist" in normalized:
            http_status = 404
        elif any(
            marker in normalized
            for marker in (
                "permission denied",
                "permission required",
                "not permitted",
                "forbidden",
            )
        ):
            http_status = 403
        elif any(
            marker in normalized
            for marker in (
                "already",
                "already exists",
                "already confirmed",
                "already processed",
                "duplicate",
                "conflict",
                "invalid transition",
                "status transition",
                "state transition",
                "current state",
                "only active or waiting",
                "before conversion",
                "before task completion",
                "requires evidence-ready case state",
                "frozen benchmark",
            )
        ):
            http_status = 409
        else:
            http_status = (
                default_status
                if default_status is not None
                else http_status_from_business_code(business_code)
            )
        return cls(
            message=message,
            business_code=business_code,
            http_status=http_status,
        )


def error_payload(
    *,
    business_code: int,
    message: str,
    data: Any | None = None,
) -> dict[str, Any]:
    return {
        "code": business_code,
        "message": message,
        "data": data,
    }


async def business_exception_handler(
    _: Request,
    exc: BusinessException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content=error_payload(
            business_code=exc.business_code,
            message=exc.message,
            data=exc.data,
        ),
    )


async def http_exception_handler(
    _: Request,
    exc: HTTPException,
) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        business_code = int(
            detail.get(
                "code",
                HTTP_STATUS_TO_BUSINESS_CODE.get(exc.status_code, 50000),
            )
        )
        message = str(detail.get("message") or _default_message(exc.status_code))
    else:
        business_code = HTTP_STATUS_TO_BUSINESS_CODE.get(
            exc.status_code,
            50000 if exc.status_code >= 500 else 40000,
        )
        message = (
            _default_message(exc.status_code)
            if exc.status_code >= 500
            else str(detail or _default_message(exc.status_code))
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            business_code=business_code,
            message=message,
        ),
        headers=exc.headers,
    )


async def validation_exception_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(item) for item in first_error.get("loc", ()))
    detail = str(first_error.get("msg") or "invalid request")
    message = "Request validation failed"
    if location:
        message = f"{message}: {location} {detail}"
    return JSONResponse(
        status_code=422,
        content=error_payload(
            business_code=42200,
            message=message,
        ),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        "Unhandled API exception",
        extra={
            "request_method": request.method,
            "request_path": request.url.path,
            "exception_type": type(exc).__name__,
        },
    )
    return JSONResponse(
        status_code=500,
        content=error_payload(
            business_code=50000,
            message="Internal server error",
        ),
    )


def _default_message(status_code: int) -> str:
    return {
        400: "Bad request",
        401: "Authentication required",
        403: "Permission denied",
        404: "Resource not found",
        409: "Resource state conflict",
        413: "Request body is too large",
        422: "Request validation failed",
        429: "Too many requests",
        500: "Internal server error",
    }.get(status_code, "Request failed")


def _safe_business_message(message: str) -> str:
    normalized = message.casefold()
    if "database write failed" in normalized or any(
        marker in normalized
        for marker in ("sqlalchemy", "psycopg", "traceback (most recent call")
    ):
        return "Database operation failed"
    if re.search(r"[A-Za-z]:[\\/][^\s]+", message):
        return "Request could not be completed"
    if re.search(
        r"(?i)(password|api[_ -]?key|authorization|bearer|access[_ -]?token)"
        r"\s*[:=]\s*\S+",
        message,
    ):
        return "Request could not be completed"
    return message or "Request failed"
