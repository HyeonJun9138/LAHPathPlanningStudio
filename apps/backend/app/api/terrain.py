"""Terrain registration and preprocessing endpoints."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..core.job_manager import job_manager, Job
from ..core.run_manager import run_manager, generate_run_id
from ..models.schemas import (
    JobResponse,
    TerrainArtifact,
    TerrainMetadata,
    TerrainPreprocessRequest,
    TerrainRegisterRequest,
)

router = APIRouter(prefix="/api/terrain", tags=["terrain"])


@router.post("/register", response_model=TerrainMetadata, status_code=201)
async def register_terrain(body: TerrainRegisterRequest, request: Request):
    db = request.app.state.db

    terrain_id = body.terrain_id or Path(body.file_path).stem
    file_path = Path(body.file_path)

    metadata: dict = {
        "crs": "",
        "width": 0,
        "height": 0,
        "resolution_m": 0.0,
        "bounds": {},
        "nodata": None,
    }

    # Try to read actual metadata from the GeoTIFF
    try:
        import rasterio
        with rasterio.open(str(file_path)) as ds:
            metadata["crs"] = str(ds.crs) if ds.crs else ""
            metadata["width"] = ds.width
            metadata["height"] = ds.height
            if ds.res:
                metadata["resolution_m"] = float(ds.res[0])
            metadata["bounds"] = {
                "left": ds.bounds.left,
                "bottom": ds.bounds.bottom,
                "right": ds.bounds.right,
                "top": ds.bounds.top,
            }
            metadata["nodata"] = float(ds.nodata) if ds.nodata is not None else None
    except Exception:
        pass

    await db.register_terrain(
        terrain_id=terrain_id,
        project_id=body.project_id,
        file_path=str(file_path),
        **metadata,
    )

    return TerrainMetadata(
        terrain_id=terrain_id,
        file_path=str(file_path),
        **metadata,
    )


@router.post("/preprocess", response_model=JobResponse)
async def preprocess_terrain(body: TerrainPreprocessRequest, request: Request):
    db = request.app.state.db

    terrain = await db.get_terrain(body.terrain_id)
    if not terrain:
        raise HTTPException(status_code=404, detail="Terrain not found. Register it first.")

    run_id = generate_run_id("01_preprocess", body.terrain_id)
    run_dir = run_manager.create_run_directory(body.project_id, "01_preprocess", run_id)
    run_manager.save_config_snapshot(run_dir, run_id, body.model_dump())

    await db.create_run(
        run_id=run_id,
        project_id=body.project_id,
        stage="01_preprocess",
        terrain_id=body.terrain_id,
        config=body.model_dump(),
    )

    job = job_manager.create_job(
        stage="01_preprocess",
        run_id=run_id,
        log_dir=run_dir / "logs",
    )

    async def _run_preprocess(j: Job) -> None:
        """Execute terrain preprocessing (stub – connects to engine when ready)."""
        steps = ["reproject", "resample", "derivatives", "overviews", "preview"]
        for i, step in enumerate(steps):
            if j.is_cancelled:
                return
            j.update_progress((i + 1) / len(steps), f"Running {step}...")
            j.log_stdout(f"[{step}] started")
            await asyncio.sleep(0.5)  # placeholder for real engine call
            j.log_stdout(f"[{step}] completed")
        await db.update_run_status(run_id, "completed")

    await job_manager.start_job(job, _run_preprocess)

    return JobResponse(**job.to_dict())


@router.get("/{terrain_id}/metadata", response_model=TerrainMetadata)
async def get_terrain_metadata(terrain_id: str, request: Request):
    db = request.app.state.db
    row = await db.get_terrain(terrain_id)
    if not row:
        raise HTTPException(status_code=404, detail="Terrain not found")
    return TerrainMetadata(**row)


@router.get("/{terrain_id}/artifacts", response_model=list[TerrainArtifact])
async def get_terrain_artifacts(terrain_id: str, request: Request):
    db = request.app.state.db
    terrain = await db.get_terrain(terrain_id)
    if not terrain:
        raise HTTPException(status_code=404, detail="Terrain not found")

    # Scan run artifacts associated with terrain preprocess runs
    runs = await db.list_runs(terrain_id=terrain_id, stage="01_preprocess")
    artifacts: list[TerrainArtifact] = []
    for run in runs:
        run_arts = await db.get_run_artifacts(run["run_id"])
        for art in run_arts:
            artifacts.append(TerrainArtifact(**art))
    return artifacts


@router.get("/{terrain_id}/preview/{artifact_name}")
async def get_terrain_preview(terrain_id: str, artifact_name: str, request: Request):
    db = request.app.state.db
    terrain = await db.get_terrain(terrain_id)
    if not terrain:
        raise HTTPException(status_code=404, detail="Terrain not found")

    # Look through preprocess run artifacts for matching PNG
    runs = await db.list_runs(terrain_id=terrain_id, stage="01_preprocess")
    for run in runs:
        arts = await db.get_run_artifacts(run["run_id"])
        for art in arts:
            if art["name"] == artifact_name:
                path = Path(art["path"])
                if path.exists():
                    return FileResponse(str(path), media_type="image/png")

    raise HTTPException(status_code=404, detail="Artifact not found")
