"""
Standardised API response helpers.
"""
from typing import Any, Optional
from app.schemas.common_schema import SuccessResponse, ErrorResponse


def success(message: str, data: Optional[Any] = None) -> SuccessResponse:
    return SuccessResponse(success=True, message=message, data=data)


def error(message: str, detail: Optional[Any] = None) -> ErrorResponse:
    return ErrorResponse(success=False, message=message, detail=detail)
