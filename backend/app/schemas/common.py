"""统一 API 响应模型"""

from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应包裹 —— {code, message, data}"""

    code: int = 200
    message: str = "ok"
    data: T | None = None

    @staticmethod
    def ok(data: Any = None, message: str = "ok") -> "ApiResponse":
        return ApiResponse(code=200, message=message, data=data)

    @staticmethod
    def fail(code: int, message: str, data: Any = None) -> "ApiResponse":
        return ApiResponse(code=code, message=message, data=data)


class PaginatedData(BaseModel, Generic[T]):
    """分页列表响应 data"""

    items: list[T]
    total: int
    page: int
    page_size: int
