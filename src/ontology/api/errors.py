"""Error handling for FastAPI.

This module provides custom exceptions and error handlers for consistent
API error responses following the problem+json format.
"""

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class NotFoundError(HTTPException):
    """Resource not found error."""

    def __init__(self, resource: str, identifier: Any) -> None:
        """Initialize not found error.

        Args:
            resource: Resource type (e.g., "Taxonomy", "Topic")
            identifier: Resource identifier
        """
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} with id '{identifier}' not found",
        )


class ConflictError(HTTPException):
    """Resource conflict error."""

    def __init__(self, message: str) -> None:
        """Initialize conflict error.

        Args:
            message: Error message
        """
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=message,
        )


class ValidationError(HTTPException):
    """Validation error."""

    def __init__(self, message: str) -> None:
        """Initialize validation error.

        Args:
            message: Error message
        """
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=message,
        )


def create_problem_response(
    status_code: int,
    title: str,
    detail: str | None = None,
    instance: str | None = None,
) -> JSONResponse:
    """Create a problem+json response.

    Args:
        status_code: HTTP status code
        title: Short, human-readable summary
        detail: Detailed explanation
        instance: URI reference that identifies the specific occurrence

    Returns:
        JSONResponse with problem+json format
    """
    content = {
        "type": f"https://httpstatuses.com/{status_code}",
        "title": title,
        "status": status_code,
    }

    if detail:
        content["detail"] = detail
    if instance:
        content["instance"] = instance

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={"Content-Type": "application/problem+json"},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with problem+json format.

    Args:
        request: The request
        exc: The exception

    Returns:
        JSONResponse with problem+json format
    """
    return create_problem_response(
        status_code=exc.status_code,
        title=HTTPException.__name__,
        detail=str(exc.detail) if exc.detail else None,
        instance=str(request.url),
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle ValueError exceptions.

    Args:
        request: The request
        exc: The exception

    Returns:
        JSONResponse with problem+json format
    """
    return create_problem_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        title="Validation Error",
        detail=str(exc),
        instance=str(request.url),
    )
