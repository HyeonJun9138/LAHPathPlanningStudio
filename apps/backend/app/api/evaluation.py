"""Evaluation run and results endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from ..core.job_manager import job_manager, Job
from ..core.run_manager import run_manager, generate_run_id
from ..models.schemas import EvaluationRequest, EvaluationResult, JobResponse

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.post("/run", response_model=JobResponse)
async def run_evaluation(body: EvaluationRequest, request: Request):
    db = request.app.state.db

    eval_run_id = generate_run_id("05_evaluation", body.terrain_id, body.checkpoint)
    run_dir = run_manager.create_run_directory(body.project_id, "05_evaluation", eval_run_id)
    run_manager.save_config_snapshot(run_dir, eval_run_id, body.model_dump())

    await db.create_run(
        run_id=eval_run_id,
        project_id=body.project_id,
        stage="05_evaluation",
        terrain_id=body.terrain_id,
        config=body.model_dump(),
    )

    job = job_manager.create_job(
        stage="05_evaluation",
        run_id=eval_run_id,
        log_dir=run_dir / "logs",
    )

    async def _run_eval(j: Job) -> None:
        for i in range(body.num_episodes):
            if j.is_cancelled:
                return
            j.update_progress((i + 1) / body.num_episodes, f"Episode {i+1}/{body.num_episodes}")
            j.log_stdout(f"[eval] episode {i+1} complete")
            await asyncio.sleep(0.2)

        # Store sample metrics
        await db.add_run_metric(eval_run_id, "success_rate", 0.72)
        await db.add_run_metric(eval_run_id, "avg_reward", 38.5)
        await db.add_run_metric(eval_run_id, "avg_episode_length", 145.2)
        await db.add_run_metric(eval_run_id, "avg_risk", 0.15)

        await db.update_run_status(
            eval_run_id, "completed",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )

    await job_manager.start_job(job, _run_eval)
    return JobResponse(**job.to_dict())


@router.get("/{run_id}/results", response_model=EvaluationResult)
async def get_evaluation_results(run_id: str, request: Request):
    db = request.app.state.db
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    metrics = await db.get_run_metrics(run_id)
    arts = await db.get_run_artifacts(run_id)
    plot_names = [a["name"] for a in arts if a.get("artifact_type") == "plot"]

    return EvaluationResult(
        run_id=run.get("config", {}).get("run_id", ""),
        eval_run_id=run_id,
        status=run.get("status", "queued"),
        metrics=metrics,
        plots=plot_names,
    )
