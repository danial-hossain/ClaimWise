"""Custom exceptions and centralized error handling for ClaimWise."""

import logging
import uuid
from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Preserve validation locations/messages without echoing passwords or documents."""
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]})


class ClaimWiseException(Exception):
    """Base exception for all domain-specific ClaimWise errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class DatabaseConnectionException(ClaimWiseException):
    """Raised when database connection attempt fails."""

    def __init__(self, message: str = "Database connection failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="DATABASE_UNAVAILABLE",
            details=details,
        )


class ConfigurationException(ClaimWiseException):
    """Raised when an essential configuration is missing or invalid."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="CONFIGURATION_ERROR",
            details=details,
        )


class UnauthorizedException(ClaimWiseException):
    """Raised when authentication credentials are missing or invalid."""

    def __init__(self, message: str = "Invalid or expired authentication credentials"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
        )


class ResourceNotFoundException(ClaimWiseException):
    """Raised when requested entity is not found."""

    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} with identifier '{identifier}' was not found",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier},
        )


async def claimwise_exception_handler(_: Request, exc: ClaimWiseException) -> JSONResponse:
    """Format domain exceptions into standard error envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the server traceback and return a safe, traceable error reference."""
    request_id = uuid.uuid4().hex[:12]
    logging.getLogger("claimwise.errors").error(
        "Unhandled request error reference=%s method=%s path=%s",
        request_id, request.method, request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Something went wrong while processing this request. Please retry.",
                "request_id": request_id,
                "details": {},
            },
        },
    )
