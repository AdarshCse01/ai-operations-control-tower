"""
Common reusable schemas including standard pagination response wrappers.
"""
from typing import Generic, Sequence, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: Sequence[T]
    total: int = Field(ge=0, description="Total count of matching records across all pages")
    page: int = Field(ge=1, description="Current 1-based page number")
    page_size: int = Field(ge=1, description="Number of items returned per page")
    total_pages: int = Field(ge=0, description="Total number of available pages")

    @classmethod
    def create(cls, items: Sequence[T], total: int, page: int, page_size: int):
        import math
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
