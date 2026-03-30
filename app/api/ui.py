from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.document import validate_and_convert
from app.services.jobs import get_job, submit_job

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "max_size_mb": settings.max_file_size_mb,
    })


@router.post("/extract")
async def extract(file: UploadFile = File(...)) -> JSONResponse:
    """Accept upload, validate eagerly, return a job ID for polling."""
    content = await file.read()
    filename = file.filename or ""
    validate_and_convert(content, filename)
    job = submit_job(content, filename)
    return JSONResponse(status_code=202, content={"job_id": job.id, "status": "processing"})


@router.get("/jobs/{job_id}")
async def poll_job(job_id: str) -> JSONResponse:
    """Poll for extraction result by job ID."""
    job = get_job(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    return JSONResponse(content=job.to_dict())
