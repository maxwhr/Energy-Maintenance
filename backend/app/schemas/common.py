from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Any = None


def success_response(data: Any | None = None, message: str = "success") -> dict:
    return {
        "code": 200,
        "message": message,
        "data": {} if data is None else data,
    }


def error_response(message: str, code: int = 400) -> dict:
    return {
        "code": code,
        "message": message,
        "data": None,
    }
