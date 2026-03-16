"""Environment creation and dry-run endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ..models.schemas import (
    DryRunRequest,
    DryRunResponse,
    EnvCreateRequest,
    SampleObservation,
)

router = APIRouter(prefix="/api/envs", tags=["environments"])

# In-memory registry of created environments
_envs: dict[str, dict[str, Any]] = {}


@router.post("/create", response_model=dict[str, Any], status_code=201)
async def create_env(body: EnvCreateRequest, request: Request):
    env_id = f"env_{uuid.uuid4().hex[:8]}"
    _envs[env_id] = {
        "env_id": env_id,
        "project_id": body.project_id,
        "terrain_id": body.terrain_id,
        "mission_id": body.mission_id,
        "hazard_run_id": body.hazard_run_id,
        "max_candidates": body.max_candidates,
        "reward_config": body.reward_config,
        "status": "created",
    }
    return _envs[env_id]


@router.post("/dry-run", response_model=DryRunResponse)
async def dry_run(body: DryRunRequest, request: Request):
    if body.env_id not in _envs:
        raise HTTPException(status_code=404, detail="Environment not found")

    # Stub: generate mock steps
    import random
    steps = []
    total_reward = 0.0
    for i in range(body.num_steps):
        r = round(random.uniform(-1.0, 2.0), 3)
        total_reward += r
        steps.append({
            "step": i,
            "action": random.randint(0, 31),
            "reward": r,
            "x": round(random.uniform(0, 20000), 1),
            "y": round(random.uniform(0, 20000), 1),
            "z": round(random.uniform(20, 200), 1),
            "done": False,
        })

    return DryRunResponse(
        env_id=body.env_id,
        steps=steps,
        total_reward=round(total_reward, 3),
        done=False,
    )


@router.get("/{env_id}/sample-observation", response_model=SampleObservation)
async def sample_observation(env_id: str, request: Request):
    if env_id not in _envs:
        raise HTTPException(status_code=404, detail="Environment not found")

    env_info = _envs[env_id]
    k = env_info.get("max_candidates", 32)

    # Stub observation
    import random
    observation = {
        "terrain_patch_hi": [[[0.0] * 5] * 128] * 128,  # placeholder shape
        "terrain_patch_mid": [[[0.0] * 5] * 64] * 64,
        "agent_state": [
            round(random.uniform(0, 20000), 1),  # x
            round(random.uniform(0, 20000), 1),  # y
            round(random.uniform(20, 200), 1),    # z
            0.0,  # heading
            round(random.uniform(0, 1), 3),       # fuel
        ],
        "mission_state": [0.0, 0.0, 1.0],  # progress, observe_done, time_remaining
    }
    action_mask = [random.randint(0, 1) for _ in range(k)]

    return SampleObservation(
        env_id=env_id,
        observation=observation,
        action_mask=action_mask,
        info={"max_candidates": k},
    )
