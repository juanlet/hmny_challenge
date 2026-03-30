from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import submissions
from app.exceptions import (
    DocumentProcessingError,
    ExtractionError,
    UnsupportedFormatError,
)

app = FastAPI(
    title="Harmony Document Extraction API",
    description="Extracts structured income data from uploaded documents using LLM",
    version="0.1.0",
)

app.include_router(submissions.router, tags=["submissions"])


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
    return _error_response(500, "extraction_failed", "An unexpected error occurred")
