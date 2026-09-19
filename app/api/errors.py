from __future__ import annotations

import logging
import time
import uuid
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

ErrorCode = Literal["invalid_input", "timeout", "upstream_unavailable", "internal", "unauthorized"]


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid.uuid4()))


def error_response(
    request: Request,
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
) -> JSONResponse:
    request_id = get_request_id(request)
    body = ErrorEnvelope(error=ErrorBody(code=code, message=message, request_id=request_id))
    return JSONResponse(status_code=status_code, content=body.model_dump())


def register_error_handlers(app: FastAPI) -> None:
    from app.conversation.service import InvalidMessageError

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        incoming = request.headers.get("X-Request-Id")
        request.state.request_id = incoming or str(uuid.uuid4())
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "request completed",
            extra={
                "request_id": request.state.request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=400,
            code="invalid_input",
            message="Invalid request body",
        )

    @app.exception_handler(InvalidMessageError)
    async def invalid_message_handler(
        request: Request,
        exc: InvalidMessageError,
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=400,
            code="invalid_input",
            message=str(exc),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        request_id = get_request_id(request)
        logger.exception("Unhandled error request_id=%s", request_id)
        return error_response(
            request,
            status_code=500,
            code="internal",
            message="An internal error occurred",
        )
