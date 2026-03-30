"""In-memory async job store for background extraction."""

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import structlog

from app.schemas.responses import SubmissionResponse

logger = structlog.get_logger()


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Job:
    __slots__ = ("id", "status", "filename", "created_at", "completed_at", "result", "error")

    def __init__(self, job_id: str, filename: str) -> None:
        self.id = job_id
        self.status = JobStatus.PENDING
        self.filename = filename
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.completed_at: str | None = None
        self.result: SubmissionResponse | None = None
        self.error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "job_id": self.id,
            "status": self.status.value,
            "filename": self.filename,
            "created_at": self.created_at,
        }
        if self.completed_at:
            d["completed_at"] = self.completed_at
        if self.result is not None:
            d["result"] = self.result.model_dump()
        if self.error is not None:
            d["error"] = self.error
        return d


# Simple in-memory store — swap for Redis/DB in production
_jobs: dict[str, Job] = {}


def create_job(filename: str) -> Job:
    job_id = uuid.uuid4().hex[:12]
    job = Job(job_id, filename)
    _jobs[job_id] = job
    logger.info("job_created", job_id=job_id, filename=filename)
    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


async def run_job(job: Job, content: bytes) -> None:
    """Execute extraction in background and store result on the job."""
    from app.services.graph import run_extraction

    job.status = JobStatus.PROCESSING
    try:
        result = await run_extraction(content, job.filename)
        job.result = result
        job.status = JobStatus.COMPLETED
    except Exception as exc:
        job.error = str(exc)
        job.status = JobStatus.FAILED
        logger.error("job_failed", job_id=job.id, error=str(exc))
    finally:
        job.completed_at = datetime.now(timezone.utc).isoformat()


def submit_job(content: bytes, filename: str) -> Job:
    """Create a job and schedule it for background execution."""
    job = create_job(filename)
    asyncio.get_event_loop().create_task(run_job(job, content))
    return job
