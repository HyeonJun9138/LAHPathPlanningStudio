#!/usr/bin/env python3
"""Initialize the LAH Path Planning Studio workspace directory structure.

Creates the default project workspace with all required subdirectories,
copies default configuration files, and initializes the SQLite database.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve project root (one level up from scripts/)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = PROJECT_ROOT / "workspace" / "projects"
DEFAULT_PROJECT = "default_project"
CONFIGS_DIR = PROJECT_ROOT / "configs"

# ---------------------------------------------------------------------------
# Schema DDL (mirrors apps/backend/app/core/database.py)
# ---------------------------------------------------------------------------
_TABLES_DDL = """
CREATE TABLE IF NOT EXISTS projects (
    project_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT DEFAULT '',
    created_at   TEXT NOT NULL,
    workspace_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS terrains (
    terrain_id   TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL,
    file_path    TEXT NOT NULL,
    crs          TEXT DEFAULT '',
    width        INTEGER DEFAULT 0,
    height       INTEGER DEFAULT 0,
    resolution_m REAL DEFAULT 0.0,
    bounds       TEXT DEFAULT '{}',
    nodata       REAL,
    registered_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

CREATE TABLE IF NOT EXISTS hazard_presets (
    preset_id    TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT DEFAULT '',
    config       TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS mission_presets (
    preset_id    TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT DEFAULT '',
    file_path    TEXT DEFAULT '',
    config       TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS runs (
    run_id       TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL,
    stage        TEXT NOT NULL,
    terrain_id   TEXT DEFAULT '',
    status       TEXT DEFAULT 'queued',
    config       TEXT DEFAULT '{}',
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

CREATE TABLE IF NOT EXISTS run_metrics (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL,
    metric_key   TEXT NOT NULL,
    metric_value TEXT NOT NULL,
    recorded_at  TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS run_artifacts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL,
    name         TEXT NOT NULL,
    path         TEXT NOT NULL,
    artifact_type TEXT DEFAULT '',
    size_bytes   INTEGER DEFAULT 0,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS run_tags (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL,
    key          TEXT NOT NULL,
    value        TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    UNIQUE(run_id, key)
);

CREATE TABLE IF NOT EXISTS models (
    model_id     TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL,
    algorithm    TEXT DEFAULT '',
    checkpoint   TEXT DEFAULT '',
    path         TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS reports (
    report_id    TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL,
    title        TEXT DEFAULT '',
    status       TEXT DEFAULT 'pending',
    html_path    TEXT,
    sections     TEXT DEFAULT '[]',
    created_at   TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
"""

# ---------------------------------------------------------------------------
# Project subdirectory layout
# ---------------------------------------------------------------------------
PROJECT_SUBDIRS = [
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


def create_project_dirs(project_path: Path) -> list[Path]:
    """Create the project directory tree and return created paths."""
    created: list[Path] = []
    for subdir in PROJECT_SUBDIRS:
        p = project_path / subdir
        p.mkdir(parents=True, exist_ok=True)
        created.append(p)
    return created


def copy_default_configs(project_path: Path) -> list[Path]:
    """Copy default YAML configs into the project's configs/ folder."""
    dest_dir = project_path / "configs"
    copied: list[Path] = []

    if not CONFIGS_DIR.exists():
        print(f"  [warn] Configs directory not found: {CONFIGS_DIR}")
        return copied

    for cfg_file in sorted(CONFIGS_DIR.glob("*.yaml")):
        dest = dest_dir / cfg_file.name
        if not dest.exists():
            shutil.copy2(cfg_file, dest)
            copied.append(dest)

    return copied


def init_database(project_path: Path) -> Path:
    """Create and initialize the project SQLite database."""
    db_path = project_path / "db" / "project.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(_TABLES_DDL)

        # Seed the default project record if empty
        cursor = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE project_id = ?",
            (DEFAULT_PROJECT,),
        )
        if cursor.fetchone()[0] == 0:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO projects (project_id, name, description, created_at, workspace_path) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    DEFAULT_PROJECT,
                    "Default Project",
                    "Auto-created default workspace project",
                    now,
                    str(project_path),
                ),
            )
        conn.commit()
    finally:
        conn.close()

    return db_path


def init_shared_cache() -> Path:
    """Ensure the shared cache directory exists."""
    cache_dir = PROJECT_ROOT / "workspace" / "shared_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def main() -> None:
    """Entry point: initialize the default project workspace."""
    print("=" * 60)
    print("  LAH Path Planning Studio - Workspace Initializer")
    print("=" * 60)
    print()

    project_path = WORKSPACE_ROOT / DEFAULT_PROJECT
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Workspace    : {WORKSPACE_ROOT}")
    print(f"Project path : {project_path}")
    print()

    # 1. Create directory structure
    print("[1/4] Creating directory structure...")
    dirs = create_project_dirs(project_path)
    for d in dirs:
        rel = d.relative_to(project_path)
        print(f"  + {rel}/")
    print(f"  -> {len(dirs)} directories created/verified")
    print()

    # 2. Copy default configs
    print("[2/4] Copying default configuration files...")
    configs = copy_default_configs(project_path)
    if configs:
        for c in configs:
            print(f"  + {c.name}")
        print(f"  -> {len(configs)} config(s) copied")
    else:
        print("  -> No new configs to copy (already exist or source missing)")
    print()

    # 3. Initialize database
    print("[3/4] Initializing SQLite database...")
    db_path = init_database(project_path)
    print(f"  + {db_path.relative_to(project_path)}")
    # Verify table count
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    print(f"  -> {len(tables)} tables: {', '.join(tables)}")
    print()

    # 4. Shared cache
    print("[4/4] Ensuring shared cache directory...")
    cache_dir = init_shared_cache()
    print(f"  + {cache_dir.relative_to(PROJECT_ROOT)}/")
    print()

    # Summary
    print("=" * 60)
    print("  Workspace initialization complete!")
    print("=" * 60)
    print()
    print(f"  Project  : {DEFAULT_PROJECT}")
    print(f"  Location : {project_path}")
    print(f"  Database : {db_path}")
    print(f"  Tables   : {len(tables)}")
    print(f"  Configs  : {len(configs)} copied")
    print(f"  Dirs     : {len(dirs)} created/verified")
    print()
    print("  You can now start the backend with:")
    print("    python -m uvicorn apps.backend.app.main:app --reload")
    print()


if __name__ == "__main__":
    main()
