"""SQLite database manager with async support via aiosqlite."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

# ---------------------------------------------------------------------------
# Schema DDL
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


class DatabaseManager:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(str(self.db_path))
        self._connection.row_factory = aiosqlite.Row
        await self._connection.executescript(_TABLES_DDL)
        await self._connection.commit()

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    # -- helpers ---------------------------------------------------------------

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        cursor = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cursor

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        cursor = await self.conn.execute(sql, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # -- Projects CRUD ---------------------------------------------------------

    async def create_project(
        self, project_id: str, name: str, description: str, workspace_path: str
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        await self.execute(
            "INSERT INTO projects (project_id, name, description, created_at, workspace_path) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, name, description, now, workspace_path),
        )
        return {
            "project_id": project_id,
            "name": name,
            "description": description,
            "created_at": now,
            "workspace_path": workspace_path,
        }

    async def list_projects(self) -> list[dict[str, Any]]:
        return await self.fetch_all("SELECT * FROM projects ORDER BY created_at DESC")

    async def get_project(self, project_id: str) -> dict[str, Any] | None:
        return await self.fetch_one("SELECT * FROM projects WHERE project_id = ?", (project_id,))

    # -- Terrains CRUD ---------------------------------------------------------

    async def register_terrain(
        self,
        terrain_id: str,
        project_id: str,
        file_path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        bounds = json.dumps(kwargs.get("bounds", {}))
        await self.execute(
            "INSERT OR REPLACE INTO terrains "
            "(terrain_id, project_id, file_path, crs, width, height, resolution_m, bounds, nodata, registered_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                terrain_id,
                project_id,
                file_path,
                kwargs.get("crs", ""),
                kwargs.get("width", 0),
                kwargs.get("height", 0),
                kwargs.get("resolution_m", 0.0),
                bounds,
                kwargs.get("nodata"),
                now,
            ),
        )
        return {"terrain_id": terrain_id, "registered_at": now}

    async def get_terrain(self, terrain_id: str) -> dict[str, Any] | None:
        row = await self.fetch_one("SELECT * FROM terrains WHERE terrain_id = ?", (terrain_id,))
        if row and isinstance(row.get("bounds"), str):
            row["bounds"] = json.loads(row["bounds"])
        return row

    async def list_terrains(self, project_id: str | None = None) -> list[dict[str, Any]]:
        if project_id:
            rows = await self.fetch_all(
                "SELECT * FROM terrains WHERE project_id = ?", (project_id,)
            )
        else:
            rows = await self.fetch_all("SELECT * FROM terrains")
        for row in rows:
            if isinstance(row.get("bounds"), str):
                row["bounds"] = json.loads(row["bounds"])
        return rows

    # -- Runs CRUD -------------------------------------------------------------

    async def create_run(
        self,
        run_id: str,
        project_id: str,
        stage: str,
        terrain_id: str = "",
        config: dict | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        config_json = json.dumps(config or {})
        await self.execute(
            "INSERT INTO runs (run_id, project_id, stage, terrain_id, status, config, started_at) "
            "VALUES (?, ?, ?, ?, 'queued', ?, ?)",
            (run_id, project_id, stage, terrain_id, config_json, now),
        )
        return {"run_id": run_id, "project_id": project_id, "stage": stage, "started_at": now}

    async def update_run_status(self, run_id: str, status: str, finished_at: str | None = None) -> None:
        if finished_at:
            await self.execute(
                "UPDATE runs SET status = ?, finished_at = ? WHERE run_id = ?",
                (status, finished_at, run_id),
            )
        else:
            await self.execute(
                "UPDATE runs SET status = ? WHERE run_id = ?",
                (status, run_id),
            )

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = await self.fetch_one("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        if row and isinstance(row.get("config"), str):
            row["config"] = json.loads(row["config"])
        return row

    async def list_runs(
        self,
        project_id: str | None = None,
        stage: str | None = None,
        status: str | None = None,
        terrain_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        if stage:
            conditions.append("stage = ?")
            params.append(stage)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if terrain_id:
            conditions.append("terrain_id = ?")
            params.append(terrain_id)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        params += [limit, offset]
        rows = await self.fetch_all(
            f"SELECT * FROM runs{where} ORDER BY started_at DESC LIMIT ? OFFSET ?",
            tuple(params),
        )
        for row in rows:
            if isinstance(row.get("config"), str):
                row["config"] = json.loads(row["config"])
        return rows

    # -- Run metrics -----------------------------------------------------------

    async def add_run_metric(self, run_id: str, key: str, value: Any) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.execute(
            "INSERT INTO run_metrics (run_id, metric_key, metric_value, recorded_at) VALUES (?, ?, ?, ?)",
            (run_id, key, json.dumps(value), now),
        )

    async def get_run_metrics(self, run_id: str) -> dict[str, Any]:
        rows = await self.fetch_all(
            "SELECT metric_key, metric_value FROM run_metrics WHERE run_id = ? ORDER BY recorded_at",
            (run_id,),
        )
        metrics: dict[str, Any] = {}
        for row in rows:
            metrics[row["metric_key"]] = json.loads(row["metric_value"])
        return metrics

    # -- Run artifacts ---------------------------------------------------------

    async def add_run_artifact(
        self, run_id: str, name: str, path: str, artifact_type: str = "", size_bytes: int = 0
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.execute(
            "INSERT INTO run_artifacts (run_id, name, path, artifact_type, size_bytes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, name, path, artifact_type, size_bytes, now),
        )

    async def get_run_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        return await self.fetch_all(
            "SELECT * FROM run_artifacts WHERE run_id = ? ORDER BY created_at", (run_id,)
        )

    # -- Run tags --------------------------------------------------------------

    async def add_run_tag(self, run_id: str, key: str, value: str) -> None:
        await self.execute(
            "INSERT OR REPLACE INTO run_tags (run_id, key, value) VALUES (?, ?, ?)",
            (run_id, key, value),
        )

    async def get_run_tags(self, run_id: str) -> list[dict[str, str]]:
        return await self.fetch_all(
            "SELECT key, value FROM run_tags WHERE run_id = ?", (run_id,)
        )

    # -- Reports ---------------------------------------------------------------

    async def create_report(
        self, report_id: str, project_id: str, title: str, sections: list[str]
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        await self.execute(
            "INSERT INTO reports (report_id, project_id, title, status, sections, created_at) "
            "VALUES (?, ?, ?, 'pending', ?, ?)",
            (report_id, project_id, title, json.dumps(sections), now),
        )
        return {"report_id": report_id, "project_id": project_id, "created_at": now}

    async def get_report(self, report_id: str) -> dict[str, Any] | None:
        row = await self.fetch_one("SELECT * FROM reports WHERE report_id = ?", (report_id,))
        if row and isinstance(row.get("sections"), str):
            row["sections"] = json.loads(row["sections"])
        return row

    async def update_report(self, report_id: str, **kwargs: Any) -> None:
        sets = []
        params = []
        for k, v in kwargs.items():
            sets.append(f"{k} = ?")
            params.append(v)
        params.append(report_id)
        await self.execute(
            f"UPDATE reports SET {', '.join(sets)} WHERE report_id = ?",
            tuple(params),
        )

    # -- Mission presets -------------------------------------------------------

    async def list_mission_presets(self) -> list[dict[str, Any]]:
        return await self.fetch_all("SELECT * FROM mission_presets")

    async def upsert_mission_preset(
        self, preset_id: str, name: str, description: str = "", file_path: str = "", config: dict | None = None
    ) -> None:
        await self.execute(
            "INSERT OR REPLACE INTO mission_presets (preset_id, name, description, file_path, config) "
            "VALUES (?, ?, ?, ?, ?)",
            (preset_id, name, description, file_path, json.dumps(config or {})),
        )
