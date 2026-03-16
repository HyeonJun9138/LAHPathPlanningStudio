"""Run listing, details, artifacts, and tagging endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..models.schemas import RunArtifact, RunResponse, RunTag

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("", response_model=list[RunResponse])
async def list_runs(
    request: Request,
    project_id: str | None = Query(None),
    stage: str | None = Query(None),
    status: str | None = Query(None),
    terrain_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    db = request.app.state.db
    rows = await db.list_runs(
        project_id=project_id,
        stage=stage,
        status=status,
        terrain_id=terrain_id,
        limit=limit,
        offset=offset,
    )
    results = []
    for row in rows:
        tags_data = await db.get_run_tags(row["run_id"])
        tags = [RunTag(key=t["key"], value=t["value"]) for t in tags_data]
        results.append(
            RunResponse(
                run_id=row["run_id"],
                project_id=row["project_id"],
                stage=row["stage"],
                terrain_id=row.get("terrain_id", ""),
                status=row.get("status", ""),
                started_at=row.get("started_at", ""),
                finished_at=row.get("finished_at"),
                config=row.get("config", {}),
                tags=tags,
            )
        )
    return results


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, request: Request):
    db = request.app.state.db
    row = await db.get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    tags_data = await db.get_run_tags(run_id)
    tags = [RunTag(key=t["key"], value=t["value"]) for t in tags_data]

    return RunResponse(
        run_id=row["run_id"],
        project_id=row["project_id"],
        stage=row["stage"],
        terrain_id=row.get("terrain_id", ""),
        status=row.get("status", ""),
        started_at=row.get("started_at", ""),
        finished_at=row.get("finished_at"),
        config=row.get("config", {}),
        tags=tags,
    )


@router.get("/{run_id}/artifacts", response_model=list[RunArtifact])
async def get_run_artifacts(run_id: str, request: Request):
    db = request.app.state.db
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    arts = await db.get_run_artifacts(run_id)
    return [RunArtifact(**a) for a in arts]


@router.post("/{run_id}/tags", response_model=list[RunTag])
async def add_tags(run_id: str, tags: list[RunTag], request: Request):
    db = request.app.state.db
    run = await db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    for tag in tags:
        await db.add_run_tag(run_id, tag.key, tag.value)

    all_tags = await db.get_run_tags(run_id)
    return [RunTag(key=t["key"], value=t["value"]) for t in all_tags]
