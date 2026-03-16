"""Job listing, status, and control endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core.job_manager import job_manager
from ..models.schemas import JobResponse, StatusResponse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs():
    return [JobResponse(**j) for j in job_manager.list_jobs()]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**job.to_dict())


@router.post("/{job_id}/stop", response_model=StatusResponse)
async def stop_job(job_id: str):
    success = job_manager.stop_job(job_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Job not found or already finished",
        )
    return StatusResponse(status="ok", message=f"Job {job_id} stop requested")
