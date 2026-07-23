from typing import Any, Generic, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: T | None = None


def success_response(data: Any | None = None, message: str = "success") -> dict:
    return {
        "code": 0,
        "message": message,
        "data": {} if data is None else data,
    }
