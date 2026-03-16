"""Application configuration loaded from configs/app.yaml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


def _find_project_root() -> Path:
    """Walk up from this file to find the repo root (contains configs/)."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "configs").is_dir():
            return parent
    return Path.cwd()


PROJECT_ROOT = _find_project_root()


class FrontendConfig(BaseModel):
    origin: str = "http://localhost:5173"


class PathsConfig(BaseModel):
    resource_root: str = "./resource"
    hazards_root: str = "./resource/hazards"
    missions_root: str = "./resource/missions"
    presets_root: str = "./resource/presets"


class AppConfig(BaseModel):
    name: str = "LAH Terrain Path Planning Studio"
    version: str = "1.0.0"
    host: str = "127.0.0.1"
    port: int = 8000
    workspace_root: str = "./workspace/projects"
    shared_cache_root: str = "./workspace/shared_cache"
    autosave_seconds: int = 30
    default_device: str = "cuda:0"
    log_level: str = "INFO"
    db_name: str = "project.sqlite"
    frontend: FrontendConfig = Field(default_factory=FrontendConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)

    def resolve_path(self, relative: str) -> Path:
        """Resolve a relative path against the project root."""
        return (PROJECT_ROOT / relative).resolve()

    @property
    def workspace_path(self) -> Path:
        return self.resolve_path(self.workspace_root)

    @property
    def shared_cache_path(self) -> Path:
        return self.resolve_path(self.shared_cache_root)

    @property
    def resource_path(self) -> Path:
        return self.resolve_path(self.paths.resource_root)


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = PROJECT_ROOT / "configs" / "app.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        return AppConfig()

    with open(config_path, "r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    app_section = raw.get("app", {})
    frontend_section = raw.get("frontend", {})
    paths_section = raw.get("paths", {})

    return AppConfig(
        **app_section,
        frontend=FrontendConfig(**frontend_section),
        paths=PathsConfig(**paths_section),
    )


# Singleton config instance
settings = load_config()
