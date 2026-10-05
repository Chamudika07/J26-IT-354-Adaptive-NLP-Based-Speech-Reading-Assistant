"""Stable public error envelopes without validation input or database details."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException


class SecurityError(Exception):
    """Only fixed public messages belong here, never credential or database details."""

    def __init__(
        self, status: int, code: str, message: str, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers


def authentication_required() -> SecurityError:
    return SecurityError(
        401, "authentication_required", "Authentication required", {"WWW-Authenticate": "Bearer"}
    )


def rate_limited(retry_after: int) -> SecurityError:
    """Adapter contract for deployment rate limiting; no process-local security claim."""
    return SecurityError(
        429, "rate_limited", "Try again later", {"Retry-After": str(max(1, retry_after))}
    )


async def security_exception_handler(request: Request, exc: SecurityError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message}},
        headers={"Cache-Control": "no-store", **(exc.headers or {})},
    )


async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": {"code": "service_unavailable", "message": "Service unavailable"}},
        headers={"Cache-Control": "no-store"},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "http_error", "message": exc.detail}},
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Do not echo request values, custom validation messages, or exception context.
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "Invalid request"}},
    )


def register_exception_handlers(application: FastAPI) -> None:
    application.add_exception_handler(SecurityError, security_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(SQLAlchemyError, database_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,  # type: ignore[arg-type]
    )
