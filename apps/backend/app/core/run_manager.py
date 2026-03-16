"""Run manager – creates run directories and generates run IDs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings

# Stage folders inside a project's runs/ directory
STAGE_DIRS = {
    "01_preprocess": "01_preprocess",
    "02_hazard": "02_hazard",
    "03_env": "03_env",
    "04_training": "04_training",
    "05_evaluation": "05_evaluation",
    "06_simulation": "06_simulation",
    "99_reports": "99_reports",
}


def generate_run_id(
    stage: str,
    terrain_id: str = "unknown",
    scenario: str = "",
) -> str:
    """Generate a run ID: {stage}__{terrain}__{scenario}__{timestamp}__{shortid}."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:6]
    parts = [stage, terrain_id]
    if scenario:
        parts.append(scenario)
    parts += [ts, short]
    return "__".join(parts)


class RunManager:
    """Handles creating run directories and config snapshots."""

    def __init__(self) -> None:
        pass

    def get_project_path(self, project_id: str) -> Path:
        return settings.workspace_path / project_id

    def get_runs_path(self, project_id: str) -> Path:
        return self.get_project_path(project_id) / "runs"

    def create_run_directory(
        self,
        project_id: str,
        stage: str,
        run_id: str,
    ) -> Path:
        """Create the directory structure for a run."""
        stage_dir = STAGE_DIRS.get(stage, stage)
        run_dir = self.get_runs_path(project_id) / stage_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Standard sub-dirs
        (run_dir / "logs").mkdir(exist_ok=True)
        (run_dir / "artifacts").mkdir(exist_ok=True)
        (run_dir / "plots").mkdir(exist_ok=True)
        (run_dir / "checkpoints").mkdir(exist_ok=True)

        return run_dir

    def save_config_snapshot(
        self,
        run_dir: Path,
        run_id: str,
        config: dict[str, Any],
    ) -> Path:
        """Save a JSON snapshot of the configuration used for this run."""
        meta = {
            "run_id": run_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "config": config,
        }
        path = run_dir / "run_meta.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        return path

    def create_project_workspace(self, project_id: str) -> Path:
        """Create the full project workspace directory structure."""
        project_dir = self.get_project_path(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)

        subdirs = [
            "db",
            "configs",
            "cache",
            "derived",
            "runs/01_preprocess",
            "runs/02_hazard",
            "runs/03_env",
            "runs/04_training",
            "runs/05_evaluation",
            "runs/06_simulation",
            "runs/99_reports",
            "exports",
            "reports",
            "notes",
        ]
        for sub in subdirs:
            (project_dir / sub).mkdir(parents=True, exist_ok=True)

        return project_dir


# Singleton
run_manager = RunManager()
