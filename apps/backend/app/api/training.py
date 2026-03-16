"""Training start/stop/metrics endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from ..core.job_manager import job_manager, Job
from ..core.run_manager import run_manager, generate_run_id
from ..models.schemas import (
    JobResponse,
    TrainingMetrics,
    TrainingStartRequest,
    TrainingStatus,
    TrainingStopRequest,
)

router = APIRouter(prefix="/api/training", tags=["training"])


@router.post("/start", response_model=JobResponse)
async def start_training(body: TrainingStartRequest, request: Request):
    db = request.app.state.db

    scenario = body.curriculum or body.algorithm
    run_id = generate_run_id("04_training", body.terrain_id, scenario)
    run_dir = run_manager.create_run_directory(body.project_id, "04_training", run_id)
    run_manager.save_config_snapshot(run_dir, run_id, body.model_dump())

    await db.create_run(
        run_id=run_id,
        project_id=body.project_id,
        stage="04_training",
        terrain_id=body.terrain_id,
        config=body.model_dump(),
    )

    job = job_manager.create_job(
        stage="04_training",
        run_id=run_id,
        log_dir=run_dir / "logs",
    )

    total_steps = body.total_timesteps

    async def _run_training(j: Job) -> None:
        """Stub training loop – will plug into engine/training/train_runner."""
        step = 0
        interval = max(total_steps // 20, 1)
        while step < total_steps:
            if j.is_cancelled:
                return
            step = min(step + interval, total_steps)
            progress = step / total_steps
            j.update_progress(progress, f"Timestep {step}/{total_steps}")
            j.log_stdout(f"step={step} progress={progress:.2%}")

            # Store sample metrics
            await db.add_run_metric(run_id, "timestep", step)
            await db.add_run_metric(run_id, "reward", round(progress * 50 - 10, 2))

            await asyncio.sleep(0.3)

        await db.update_run_status(
            run_id, "completed",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )

    await job_manager.start_job(job, _run_training)
    return JobResponse(**job.to_dict())


@router.post("/stop", response_model=JobResponse)
async def stop_training(body: TrainingStopRequest, request: Request):
    db = request.app.state.db

    # Find job by run_id
    for j_data in job_manager.list_jobs():
        if j_data["run_id"] == body.run_id:
            stopped = job_manager.stop_job(j_data["job_id"])
            if stopped:
                await db.update_run_status(
                    body.run_id, "stopped",
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
            job = job_manager.get_job(j_data["job_id"])
            if job:
                return JobResponse(**job.to_dict())

    raise HTTPException(status_code=404, detail="Training job not found for given run_id")


@router.get("/{run_id}/metrics", response_model=TrainingMetrics)
async def get_training_metrics(run_id: str, request: Request):
    db = request.app.state.db
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    raw_metrics = await db.get_run_metrics(run_id)

    # Aggregate timestep/reward pairs into lists
    timesteps: list[int] = []
    rewards: list[float] = []
    if isinstance(raw_metrics.get("timestep"), list):
        timesteps = raw_metrics["timestep"]
    elif "timestep" in raw_metrics:
        timesteps = [raw_metrics["timestep"]]
    if isinstance(raw_metrics.get("reward"), list):
        rewards = raw_metrics["reward"]
    elif "reward" in raw_metrics:
        rewards = [raw_metrics["reward"]]

    return TrainingMetrics(
        run_id=run_id,
        timesteps=timesteps,
        rewards=rewards,
        additional=raw_metrics,
    )
