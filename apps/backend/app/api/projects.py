"""Project management endpoints."""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..core.config import settings
from ..models.schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectStructure,
    ResourceScanResult,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _slugify(name: str) -> str:
    """Create a filesystem-safe project id from a name."""
    slug = re.sub(r"[^\w\s-]", "", name.lower().strip())
    slug = re.sub(r"[\s-]+", "_", slug)
    return slug or "project"


def _build_tree(root: Path, max_depth: int = 4, _depth: int = 0) -> dict:
    """Recursively build a directory tree dict."""
    tree: dict = {}
    if _depth >= max_depth or not root.is_dir():
        return tree
    try:
        for entry in sorted(root.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                tree[entry.name + "/"] = _build_tree(entry, max_depth, _depth + 1)
            else:
                tree[entry.name] = entry.stat().st_size
    except PermissionError:
        pass
    return tree


@router.get("", response_model=list[ProjectResponse])
async def list_projects(request: Request):
    db = request.app.state.db
    rows = await db.list_projects()
    return [ProjectResponse(**r) for r in rows]


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate, request: Request):
    db = request.app.state.db
    rm = request.app.state.run_manager

    project_id = _slugify(body.name)

    existing = await db.get_project(project_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Project '{project_id}' already exists")

    workspace_path = rm.create_project_workspace(project_id)
    row = await db.create_project(
        project_id=project_id,
        name=body.name,
        description=body.description,
        workspace_path=str(workspace_path),
    )
    return ProjectResponse(**row)


@router.get("/{project_id}/structure", response_model=ProjectStructure)
async def get_project_structure(project_id: str, request: Request):
    db = request.app.state.db
    project = await db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ws = Path(project["workspace_path"])
    if not ws.exists():
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    tree = _build_tree(ws)
    return ProjectStructure(project_id=project_id, tree=tree)


@router.post("/{project_id}/scan-resources", response_model=ResourceScanResult)
async def scan_resources(project_id: str, request: Request):
    db = request.app.state.db
    project = await db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    resource_root = settings.resource_path
    result = ResourceScanResult(project_id=project_id)

    if resource_root.exists():
        for f in resource_root.glob("*.tif"):
            result.terrains.append(f.name)
        hazards_dir = resource_root / "hazards"
        if hazards_dir.exists():
            for f in hazards_dir.glob("*.json"):
                result.hazards.append(f.name)
        missions_dir = resource_root / "missions"
        if missions_dir.exists():
            for f in missions_dir.iterdir():
                if f.suffix in (".yaml", ".yml", ".json"):
                    result.missions.append(f.name)
        presets_dir = resource_root / "presets"
        if presets_dir.exists():
            for f in presets_dir.iterdir():
                if f.suffix in (".yaml", ".yml"):
                    result.presets.append(f.name)

    return result
