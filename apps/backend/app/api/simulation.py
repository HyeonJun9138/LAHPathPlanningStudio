"""Simulation rollout and episode data endpoints."""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from ..core.job_manager import job_manager, Job
from ..core.run_manager import run_manager, generate_run_id
from ..models.schemas import (
    EpisodeData,
    EpisodeStep,
    JobResponse,
    SimulationRequest,
)

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

# In-memory episode storage (would be file-backed in production)
_episodes: dict[str, dict[str, EpisodeData]] = {}


@router.post("/rollout", response_model=JobResponse)
async def execute_rollout(body: SimulationRequest, request: Request):
    db = request.app.state.db

    sim_run_id = generate_run_id("06_simulation", body.terrain_id, body.checkpoint)
    run_dir = run_manager.create_run_directory(body.project_id, "06_simulation", sim_run_id)
    run_manager.save_config_snapshot(run_dir, sim_run_id, body.model_dump())

    await db.create_run(
        run_id=sim_run_id,
        project_id=body.project_id,
        stage="06_simulation",
        terrain_id=body.terrain_id,
        config=body.model_dump(),
    )

    job = job_manager.create_job(
        stage="06_simulation",
        run_id=sim_run_id,
        log_dir=run_dir / "logs",
    )

    async def _run_rollout(j: Job) -> None:
        _episodes[sim_run_id] = {}
        for ep_num in range(body.num_episodes):
            if j.is_cancelled:
                return
            episode_id = f"ep_{ep_num:04d}"
            j.update_progress(
                (ep_num + 1) / body.num_episodes,
                f"Rollout episode {ep_num+1}/{body.num_episodes}",
            )

            # Generate stub episode data
            num_steps = random.randint(50, 200)
            steps = []
            x, y, z = 1000.0, 1000.0, 30.0
            total_reward = 0.0
            for s in range(num_steps):
                dx = random.uniform(-200, 200)
                dy = random.uniform(-200, 200)
                dz = random.uniform(-10, 10)
                x = max(0, x + dx)
                y = max(0, y + dy)
                z = max(10, min(300, z + dz))
                r = round(random.uniform(-1, 3), 3)
                total_reward += r
                steps.append(
                    EpisodeStep(
                        step=s,
                        x=round(x, 1),
                        y=round(y, 1),
                        z=round(z, 1),
                        action=random.randint(0, 31),
                        reward=r,
                        risk=round(random.uniform(0, 0.5), 3),
                        mode="transit",
                    )
                )

            _episodes[sim_run_id][episode_id] = EpisodeData(
                run_id=sim_run_id,
                episode_id=episode_id,
                steps=steps,
                total_reward=round(total_reward, 3),
                success=random.random() > 0.3,
                length=num_steps,
            )
            j.log_stdout(f"[rollout] episode {episode_id} done, steps={num_steps}")
            await asyncio.sleep(0.2)

        await db.update_run_status(
            sim_run_id, "completed",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )

    await job_manager.start_job(job, _run_rollout)
    return JobResponse(**job.to_dict())


@router.get("/{run_id}/episode/{episode_id}", response_model=EpisodeData)
async def get_episode(run_id: str, episode_id: str, request: Request):
    run_episodes = _episodes.get(run_id)
    if not run_episodes:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    episode = run_episodes.get(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode
