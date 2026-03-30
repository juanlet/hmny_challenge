from fastapi import APIRouter, File, UploadFile

from app.schemas.responses import SubmissionResponse
from app.services.extraction import extract_from_document

router = APIRouter()


@router.post("/submissions", response_model=SubmissionResponse)
async def create_submission(file: UploadFile = File(...)) -> SubmissionResponse:
    content = await file.read()
    return await extract_from_document(content, file.filename or "")
