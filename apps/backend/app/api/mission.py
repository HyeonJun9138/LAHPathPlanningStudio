"""Mission validation and presets endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..core.config import settings
from ..models.schemas import MissionPreset, MissionResponse, MissionValidateRequest

router = APIRouter(prefix="/api/missions", tags=["missions"])


@router.post("/validate", response_model=MissionResponse)
async def validate_mission(body: MissionValidateRequest, request: Request):
    errors: list[str] = []
    warnings: list[str] = []

    # Basic validation checks
    if body.start.x < 0 or body.start.y < 0:
        errors.append("Start point must have non-negative coordinates")
    if body.goal.x < 0 or body.goal.y < 0:
        errors.append("Goal point must have non-negative coordinates")

    if body.start.x == body.goal.x and body.start.y == body.goal.y:
        errors.append("Start and goal must be different")

    if body.max_episode_time_sec <= 0:
        errors.append("max_episode_time_sec must be positive")

    if body.start.agl_m < 0:
        errors.append("Start AGL altitude must be non-negative")
    if body.goal.agl_m < 0:
        errors.append("Goal AGL altitude must be non-negative")

    if body.observe_box is not None:
        ob = body.observe_box
        if ob.size_x <= 0 or ob.size_y <= 0 or ob.size_z <= 0:
            errors.append("Observe box dimensions must be positive")
        if ob.required_duration_sec <= 0:
            warnings.append("Observe box duration_sec is zero or negative")

    if not body.safe_hold_points:
        warnings.append("No safe hold points defined")

    mission_id = f"mission_{body.terrain_id}_{len(errors) == 0}"

    return MissionResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        mission_id=mission_id if not errors else "",
    )


@router.get("/presets", response_model=list[MissionPreset])
async def list_mission_presets(request: Request):
    db = request.app.state.db
    rows = await db.list_mission_presets()
    if rows:
        return [MissionPreset(**r) for r in rows]

    # Scan filesystem for presets if DB is empty
    presets: list[MissionPreset] = []
    missions_dir = settings.resource_path / "missions"
    if missions_dir.exists():
        for f in missions_dir.iterdir():
            if f.suffix in (".yaml", ".yml", ".json"):
                presets.append(
                    MissionPreset(
                        preset_id=f.stem,
                        name=f.stem.replace("_", " ").title(),
                        file_path=str(f),
                    )
                )
    return presets
