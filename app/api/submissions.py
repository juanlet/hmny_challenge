from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from app.exceptions import UnsupportedFormatError
from app.schemas.responses import SubmissionResponse
from app.services.document import validate_and_convert
from app.services.jobs import get_job, submit_job

router = APIRouter()


@router.post("/submissions", status_code=202)
async def create_submission(file: UploadFile = File(...)) -> JSONResponse:
    content = await file.read()
    filename = file.filename or ""

    # Validate format eagerly so bad uploads fail fast (before queueing a job)
    validate_and_convert(content, filename)

    job = submit_job(content, filename)
    return JSONResponse(
        status_code=202,
        content={"job_id": job.id, "status": "processing"},
    )


@router.get("/submissions/{job_id}")
async def get_submission(job_id: str) -> JSONResponse:
    job = get_job(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    return JSONResponse(content=job.to_dict())
