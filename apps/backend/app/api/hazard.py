"""Hazard build and preview endpoints."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..core.job_manager import job_manager, Job
from ..core.run_manager import run_manager, generate_run_id
from ..models.schemas import HazardBuildRequest, HazardSummary, JobResponse

router = APIRouter(prefix="/api/hazard", tags=["hazard"])


@router.post("/build", response_model=JobResponse)
async def build_hazard(body: HazardBuildRequest, request: Request):
    db = request.app.state.db

    run_id = generate_run_id("02_hazard", body.terrain_id)
    run_dir = run_manager.create_run_directory(body.project_id, "02_hazard", run_id)
    run_manager.save_config_snapshot(run_dir, run_id, body.model_dump())

    await db.create_run(
        run_id=run_id,
        project_id=body.project_id,
        stage="02_hazard",
        terrain_id=body.terrain_id,
        config=body.model_dump(),
    )

    job = job_manager.create_job(
        stage="02_hazard",
        run_id=run_id,
        log_dir=run_dir / "logs",
    )

    async def _run_hazard_build(j: Job) -> None:
        steps = ["load_terrain", "compute_los", "compute_risk", "fusion", "preview"]
        for i, step in enumerate(steps):
            if j.is_cancelled:
                return
            j.update_progress((i + 1) / len(steps), f"Running {step}...")
            j.log_stdout(f"[{step}] started")
            await asyncio.sleep(0.5)
            j.log_stdout(f"[{step}] completed")
        await db.update_run_status(run_id, "completed")

    await job_manager.start_job(job, _run_hazard_build)
    return JobResponse(**job.to_dict())


@router.get("/{run_id}/summary", response_model=HazardSummary)
async def get_hazard_summary(run_id: str, request: Request):
    db = request.app.state.db
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run["stage"] != "02_hazard":
        raise HTTPException(status_code=400, detail="Not a hazard run")

    config = run.get("config", {})
    sources = config.get("sources", [])
    bands = config.get("altitude_bands", [])

    arts = await db.get_run_artifacts(run_id)
    artifact_names = [a["name"] for a in arts]

    return HazardSummary(
        run_id=run_id,
        terrain_id=run.get("terrain_id", ""),
        num_sources=len(sources),
        fusion_mode=config.get("fusion_mode", ""),
        altitude_bands=[b.get("name", "") for b in bands],
        risk_stats={},
        artifacts=artifact_names,
    )


@router.get("/{run_id}/preview/{name}")
async def get_hazard_preview(run_id: str, name: str, request: Request):
    db = request.app.state.db
    arts = await db.get_run_artifacts(run_id)
    for art in arts:
        if art["name"] == name:
            path = Path(art["path"])
            if path.exists():
                return FileResponse(str(path), media_type="image/png")

    raise HTTPException(status_code=404, detail="Preview not found")
