"""Report generation and retrieval endpoints."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from ..core.job_manager import job_manager, Job
from ..core.run_manager import run_manager
from ..models.schemas import JobResponse, ReportGenerateRequest, ReportResponse

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/generate", response_model=JobResponse)
async def generate_report(body: ReportGenerateRequest, request: Request):
    db = request.app.state.db

    report_id = f"report_{uuid.uuid4().hex[:8]}"
    await db.create_report(
        report_id=report_id,
        project_id=body.project_id,
        title=body.title,
        sections=body.include_sections,
    )

    job = job_manager.create_job(
        stage="99_reports",
        run_id=report_id,
    )

    async def _generate(j: Job) -> None:
        sections = body.include_sections
        for i, section in enumerate(sections):
            if j.is_cancelled:
                return
            j.update_progress((i + 1) / len(sections), f"Generating {section}...")
            j.log_stdout(f"[report] generating section: {section}")
            await asyncio.sleep(0.3)

        # Mark report as complete
        await db.update_report(report_id, status="completed")
        j.log_stdout(f"[report] completed: {report_id}")

    await job_manager.start_job(job, _generate)
    return JobResponse(**job.to_dict())


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: str, request: Request):
    db = request.app.state.db
    row = await db.get_report(report_id)
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportResponse(
        report_id=row["report_id"],
        project_id=row["project_id"],
        title=row.get("title", ""),
        status=row.get("status", "pending"),
        created_at=row.get("created_at", ""),
        html_path=row.get("html_path"),
        sections=row.get("sections", []),
    )
