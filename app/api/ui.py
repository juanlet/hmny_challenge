from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.exceptions import UnsupportedFormatError
from app.services.extraction import extract_from_document

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "result": None,
        "max_size_mb": settings.max_file_size_mb,
    })


@router.post("/extract", response_class=HTMLResponse)
async def extract(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    try:
        result = await extract_from_document(content, file.filename or "")
        result_dict = result.model_dump()
    except UnsupportedFormatError as exc:
        result_dict = {
            "status": "error",
            "data": None,
            "errors": [{"field": None, "error_type": "unsupported_format", "message": exc.detail}],
            "metadata": {},
        }

    return templates.TemplateResponse(request, "index.html", {
        "result": _to_namespace(result_dict),
        "max_size_mb": settings.max_file_size_mb,
    })


class _Namespace:
    """Dict-to-attribute wrapper for Jinja2 dot access."""
    def __init__(self, d: dict):
        for k, v in d.items():
            if isinstance(v, dict):
                setattr(self, k, _Namespace(v))
            elif isinstance(v, list):
                setattr(self, k, [_Namespace(i) if isinstance(i, dict) else i for i in v])
            else:
                setattr(self, k, v)

    def get(self, key, default=None):
        return getattr(self, key, default)


def _to_namespace(d: dict) -> _Namespace:
    return _Namespace(d)
