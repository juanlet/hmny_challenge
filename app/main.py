import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import submissions, ui
from app.exceptions import (
    DocumentProcessingError,
    ExtractionError,
    UnsupportedFormatError,
)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

app = FastAPI(
    title="Harmony Document Extraction API",
    description="Extracts structured income data from uploaded documents using LLM",
    version="0.1.0",
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
            return response
        finally:
            structlog.contextvars.clear_contextvars()


app.add_middleware(RequestIdMiddleware)
app.include_router(submissions.router, tags=["submissions"])
app.include_router(ui.router, tags=["ui"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Global exception handlers — translate domain exceptions to structured JSON
# ---------------------------------------------------------------------------

def _error_response(status_code: int, error_type: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "data": None,
            "errors": [
                {
                    "field": None,
                    "error_type": error_type,
                    "message": message,
                    "raw_value": None,
                }
            ],
            "metadata": {},
        },
    )


@app.exception_handler(UnsupportedFormatError)
async def unsupported_format_handler(request: Request, exc: UnsupportedFormatError) -> JSONResponse:
    logger.warning("unsupported_format", detail=exc.detail)
    return _error_response(422, "unsupported_format", exc.detail)


@app.exception_handler(ExtractionError)
async def extraction_error_handler(request: Request, exc: ExtractionError) -> JSONResponse:
    return _error_response(422, "extraction_failed", exc.detail)


@app.exception_handler(DocumentProcessingError)
async def document_processing_handler(request: Request, exc: DocumentProcessingError) -> JSONResponse:
    return _error_response(502, "extraction_failed", exc.detail)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _error_response(422, "validation_error", str(exc))


@app.exception_handler(Exception)
async def catch_all_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unexpected_error", error="An unexpected error occurred")
    return _error_response(500, "extraction_failed", "An unexpected error occurred")
