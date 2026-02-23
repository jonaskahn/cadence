"""Response schemas for Cadence API.

This module provides consistent response formats for success and error cases.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

# Generic type for response data
T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str = Field(..., description="Error code for programmatic handling")
    message: str = Field(..., description="Human-readable error message")
    field: Optional[str] = Field(None, description="Field name if validation error")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error context"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid email format",
                "field": "email",
                "details": {
                    "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
                },
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response format."""

    success: bool = Field(False, description="Always false for errors")
    error: ErrorDetail = Field(..., description="Error details")
    errors: Optional[List[ErrorDetail]] = Field(
        None, description="Multiple errors (e.g., validation)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error timestamp (UTC)"
    )
    request_id: Optional[str] = Field(None, description="Request ID for tracing")
    path: Optional[str] = Field(None, description="API path that caused the error")
    method: Optional[str] = Field(None, description="HTTP method")

    stack_trace: Optional[str] = Field(
        None, description="Stack trace (development only)"
    )
    debug_info: Optional[Dict[str, Any]] = Field(
        None, description="Debug information (development only)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Orchestrator instance not found",
                    "details": {"instance_id": "abc-123"},
                },
                "timestamp": "2026-02-18T00:00:00Z",
                "request_id": "req_abc123",
                "path": "/api/orchestrators/abc-123",
                "method": "GET",
            }
        }


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response format."""

    success: bool = Field(True, description="Always true for success")
    data: T = Field(..., description="Response data")
    message: Optional[str] = Field(None, description="Optional success message")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp (UTC)"
    )
    request_id: Optional[str] = Field(None, description="Request ID for tracing")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": "123", "name": "Example"},
                "message": "Operation completed successfully",
                "timestamp": "2026-02-18T00:00:00Z",
                "request_id": "req_abc123",
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response format."""

    success: bool = Field(True, description="Always true for success")
    data: List[T] = Field(..., description="List of items")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp (UTC)"
    )
    request_id: Optional[str] = Field(None, description="Request ID for tracing")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": [{"id": "1", "name": "Item 1"}, {"id": "2", "name": "Item 2"}],
                "pagination": {
                    "page": 1,
                    "page_size": 10,
                    "total_items": 100,
                    "total_pages": 10,
                    "has_next": True,
                    "has_prev": False,
                },
                "timestamp": "2026-02-18T00:00:00Z",
                "request_id": "req_abc123",
            }
        }


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total_items: int = Field(..., ge=0, description="Total number of items")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


# Update forward references
PaginatedResponse.model_rebuild()


# Utility functions for creating responses
def success_response(
    data: Any, message: Optional[str] = None, request_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a success response."""
    return SuccessResponse(
        data=data, message=message, request_id=request_id
    ).model_dump()


def error_response(
    code: str,
    message: str,
    field: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    errors: Optional[List[ErrorDetail]] = None,
    request_id: Optional[str] = None,
    path: Optional[str] = None,
    method: Optional[str] = None,
    stack_trace: Optional[str] = None,
    debug_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create an error response."""
    return ErrorResponse(
        error=ErrorDetail(code=code, message=message, field=field, details=details),
        errors=errors,
        request_id=request_id,
        path=path,
        method=method,
        stack_trace=stack_trace,
        debug_info=debug_info,
    ).model_dump(mode="json", exclude_none=True)


def paginated_response(
    data: List[Any],
    page: int,
    page_size: int,
    total_items: int,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a paginated response."""
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0

    return PaginatedResponse(
        data=data,
        pagination=PaginationInfo(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        ),
        request_id=request_id,
    ).model_dump()
