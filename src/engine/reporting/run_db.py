"""SQLite database for experiment management.

Provides a :class:`RunDatabase` that stores runs, metrics, artifacts, tags,
notes, reports, and supporting project/terrain/preset reference tables.
All tables are created automatically on first open.  Every public method
performs real SQL — no stubs.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    """Return a new UUID4 hex string suitable for primary keys."""
    return uuid.uuid4().hex


class RunDatabase:
    """Thin wrapper around a SQLite database for experiment tracking.

    Parameters
    ----------
    db_path : str
        Filesystem path to the ``.sqlite`` file.  Created (along with
        parent directories) if it does not exist.
    """

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    # ------------------------------------------------------------------
    # schema
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        """Create all tables if they do not already exist."""
        ddl = """
        CREATE TABLE IF NOT EXISTS projects (
            project_id   TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            description  TEXT DEFAULT '',
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS terrains (
            terrain_id   TEXT PRIMARY KEY,
            project_id   TEXT,
            name         TEXT NOT NULL,
            file_path    TEXT NOT NULL,
            crs          TEXT DEFAULT '',
            resolution_x REAL DEFAULT 0,
            resolution_y REAL DEFAULT 0,
            width        INTEGER DEFAULT 0,
            height       INTEGER DEFAULT 0,
            created_at   TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS hazard_presets (
            preset_id    TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            config_json  TEXT NOT NULL,
            created_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mission_presets (
            preset_id    TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            config_json  TEXT NOT NULL,
            created_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
            run_id       TEXT PRIMARY KEY,
            project_id   TEXT,
            run_type     TEXT DEFAULT 'training',
            status       TEXT DEFAULT 'pending',
            config_json  TEXT DEFAULT '{}',
            started_at   TEXT,
            finished_at  TEXT,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS run_metrics (
            metric_id    TEXT PRIMARY KEY,
            run_id       TEXT NOT NULL,
            name         TEXT NOT NULL,
            value        REAL NOT NULL,
            step         INTEGER,
            recorded_at  TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );
        CREATE INDEX IF NOT EXISTS idx_run_metrics_run
            ON run_metrics(run_id);

        CREATE TABLE IF NOT EXISTS run_artifacts (
            artifact_id    TEXT PRIMARY KEY,
            run_id         TEXT NOT NULL,
            name           TEXT NOT NULL,
            path           TEXT NOT NULL,
            artifact_type  TEXT NOT NULL,
            created_at     TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );
        CREATE INDEX IF NOT EXISTS idx_run_artifacts_run
            ON run_artifacts(run_id);

        CREATE TABLE IF NOT EXISTS run_tags (
            tag_id   TEXT PRIMARY KEY,
            run_id   TEXT NOT NULL,
            tag      TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id),
            UNIQUE(run_id, tag)
        );
        CREATE INDEX IF NOT EXISTS idx_run_tags_run
            ON run_tags(run_id);

        CREATE TABLE IF NOT EXISTS run_notes (
            note_id     TEXT PRIMARY KEY,
            run_id      TEXT NOT NULL,
            text        TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );
        CREATE INDEX IF NOT EXISTS idx_run_notes_run
            ON run_notes(run_id);

        CREATE TABLE IF NOT EXISTS models (
            model_id     TEXT PRIMARY KEY,
            run_id       TEXT NOT NULL,
            name         TEXT NOT NULL,
            path         TEXT NOT NULL,
            framework    TEXT DEFAULT 'pytorch',
            created_at   TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS reports (
            report_id    TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            format       TEXT DEFAULT 'markdown',
            content      TEXT DEFAULT '',
            output_path  TEXT DEFAULT '',
            run_ids_json TEXT DEFAULT '[]',
            config_json  TEXT DEFAULT '{}',
            created_at   TEXT NOT NULL
        );
        """
        self._conn.executescript(ddl)
        self._conn.commit()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _row_to_dict(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row)

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

    # ------------------------------------------------------------------
    # runs
    # ------------------------------------------------------------------

    def insert_run(self, run_data: dict) -> str:
        """Insert a new run and return the generated ``run_id``.

        *run_data* may contain any of the columns of the ``runs`` table.
        Missing columns receive their default values.
        """
        run_id = run_data.get("run_id") or _new_id()
        now = _utcnow_iso()
        config_json = json.dumps(run_data.get("config", run_data.get("config_json", {})))
        self._conn.execute(
            """
            INSERT INTO runs
                (run_id, project_id, run_type, status, config_json,
                 started_at, finished_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run_data.get("project_id"),
                run_data.get("run_type", "training"),
                run_data.get("status", "pending"),
                config_json,
                run_data.get("started_at"),
                run_data.get("finished_at"),
                now,
                now,
            ),
        )
        self._conn.commit()
        return run_id

    def update_run(self, run_id: str, updates: dict) -> None:
        """Apply *updates* (column -> value mapping) to an existing run."""
        if not updates:
            return
        allowed = {
            "project_id", "run_type", "status", "config_json",
            "started_at", "finished_at",
        }
        # Special handling: if caller passes "config" dict, serialise it.
        if "config" in updates:
            updates["config_json"] = json.dumps(updates.pop("config"))

        sets: list[str] = []
        vals: list[Any] = []
        for col, val in updates.items():
            if col in allowed:
                sets.append(f"{col} = ?")
                vals.append(val)
        if not sets:
            return
        sets.append("updated_at = ?")
        vals.append(_utcnow_iso())
        vals.append(run_id)
        sql = f"UPDATE runs SET {', '.join(sets)} WHERE run_id = ?"
        self._conn.execute(sql, vals)
        self._conn.commit()

    def get_run(self, run_id: str) -> dict | None:
        """Fetch a single run by its id, or *None* if not found."""
        row = self._conn.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        result = self._row_to_dict(row)
        if result and result.get("config_json"):
            try:
                result["config"] = json.loads(result["config_json"])
            except (json.JSONDecodeError, TypeError):
                result["config"] = {}
        return result

    def list_runs(self, filters: dict | None = None) -> list[dict]:
        """List runs, optionally filtered by column values.

        *filters* maps column names (``project_id``, ``run_type``,
        ``status``) to exact-match values.  ``None`` returns all runs.
        """
        sql = "SELECT * FROM runs"
        params: list[Any] = []
        if filters:
            clauses: list[str] = []
            for col, val in filters.items():
                clauses.append(f"{col} = ?")
                params.append(val)
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC"
        rows = self._conn.execute(sql, params).fetchall()
        results: list[dict] = []
        for row in rows:
            d = dict(row)
            if d.get("config_json"):
                try:
                    d["config"] = json.loads(d["config_json"])
                except (json.JSONDecodeError, TypeError):
                    d["config"] = {}
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # metrics
    # ------------------------------------------------------------------

    def insert_metric(
        self,
        run_id: str,
        name: str,
        value: float,
        step: int | None = None,
    ) -> None:
        """Record a scalar metric for a run."""
        self._conn.execute(
            """
            INSERT INTO run_metrics (metric_id, run_id, name, value, step, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_new_id(), run_id, name, float(value), step, _utcnow_iso()),
        )
        self._conn.commit()

    def get_metrics(self, run_id: str) -> list[dict]:
        """Return all metrics for a given run, ordered by step then name."""
        rows = self._conn.execute(
            """
            SELECT * FROM run_metrics
            WHERE run_id = ?
            ORDER BY step ASC NULLS LAST, name ASC
            """,
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # artifacts
    # ------------------------------------------------------------------

    def insert_artifact(
        self,
        run_id: str,
        name: str,
        path: str,
        artifact_type: str,
    ) -> str:
        """Record an artifact (model checkpoint, plot image, etc.).

        Returns the generated ``artifact_id``.
        """
        artifact_id = _new_id()
        self._conn.execute(
            """
            INSERT INTO run_artifacts
                (artifact_id, run_id, name, path, artifact_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (artifact_id, run_id, name, path, artifact_type, _utcnow_iso()),
        )
        self._conn.commit()
        return artifact_id

    def get_artifacts(self, run_id: str) -> list[dict]:
        """Return all artifacts for a run."""
        rows = self._conn.execute(
            "SELECT * FROM run_artifacts WHERE run_id = ? ORDER BY created_at",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # tags
    # ------------------------------------------------------------------

    def add_tag(self, run_id: str, tag: str) -> None:
        """Attach a tag string to a run (idempotent)."""
        try:
            self._conn.execute(
                "INSERT INTO run_tags (tag_id, run_id, tag) VALUES (?, ?, ?)",
                (_new_id(), run_id, tag),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            # Duplicate (run_id, tag) — silently ignore.
            pass

    def get_tags(self, run_id: str) -> list[str]:
        """Return all tags for a run as a sorted list of strings."""
        rows = self._conn.execute(
            "SELECT tag FROM run_tags WHERE run_id = ? ORDER BY tag",
            (run_id,),
        ).fetchall()
        return [r["tag"] for r in rows]

    # ------------------------------------------------------------------
    # notes
    # ------------------------------------------------------------------

    def add_note(self, run_id: str, text: str) -> str:
        """Append a free-text note to a run.  Returns the ``note_id``."""
        note_id = _new_id()
        self._conn.execute(
            """
            INSERT INTO run_notes (note_id, run_id, text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (note_id, run_id, text, _utcnow_iso()),
        )
        self._conn.commit()
        return note_id

    def get_notes(self, run_id: str) -> list[dict]:
        """Return all notes for a run ordered by creation time."""
        rows = self._conn.execute(
            "SELECT * FROM run_notes WHERE run_id = ? ORDER BY created_at",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # reports
    # ------------------------------------------------------------------

    def insert_report(self, report_data: dict) -> str:
        """Insert a generated report record.  Returns the ``report_id``."""
        report_id = report_data.get("report_id") or _new_id()
        run_ids_json = json.dumps(report_data.get("run_ids", []))
        config_json = json.dumps(report_data.get("config", {}))
        self._conn.execute(
            """
            INSERT INTO reports
                (report_id, title, format, content, output_path,
                 run_ids_json, config_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                report_data.get("title", "Untitled Report"),
                report_data.get("format", "markdown"),
                report_data.get("content", ""),
                report_data.get("output_path", ""),
                run_ids_json,
                config_json,
                _utcnow_iso(),
            ),
        )
        self._conn.commit()
        return report_id

    def get_report(self, report_id: str) -> dict | None:
        """Fetch a report by its id, or *None* if not found."""
        row = self._conn.execute(
            "SELECT * FROM reports WHERE report_id = ?", (report_id,)
        ).fetchone()
        result = self._row_to_dict(row)
        if result:
            try:
                result["run_ids"] = json.loads(result.get("run_ids_json", "[]"))
            except (json.JSONDecodeError, TypeError):
                result["run_ids"] = []
            try:
                result["config"] = json.loads(result.get("config_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                result["config"] = {}
        return result

    # ------------------------------------------------------------------
    # projects (convenience)
    # ------------------------------------------------------------------

    def insert_project(self, name: str, description: str = "") -> str:
        """Create a new project.  Returns the ``project_id``."""
        project_id = _new_id()
        now = _utcnow_iso()
        self._conn.execute(
            """
            INSERT INTO projects (project_id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, name, description, now, now),
        )
        self._conn.commit()
        return project_id

    # ------------------------------------------------------------------
    # terrains (convenience)
    # ------------------------------------------------------------------

    def insert_terrain(self, terrain_data: dict) -> str:
        """Register a terrain file.  Returns the ``terrain_id``."""
        terrain_id = terrain_data.get("terrain_id") or _new_id()
        self._conn.execute(
            """
            INSERT INTO terrains
                (terrain_id, project_id, name, file_path, crs,
                 resolution_x, resolution_y, width, height, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                terrain_id,
                terrain_data.get("project_id"),
                terrain_data.get("name", ""),
                terrain_data.get("file_path", ""),
                terrain_data.get("crs", ""),
                terrain_data.get("resolution_x", 0),
                terrain_data.get("resolution_y", 0),
                terrain_data.get("width", 0),
                terrain_data.get("height", 0),
                _utcnow_iso(),
            ),
        )
        self._conn.commit()
        return terrain_id

    # ------------------------------------------------------------------
    # models (convenience)
    # ------------------------------------------------------------------

    def insert_model(self, model_data: dict) -> str:
        """Register a trained model checkpoint.  Returns the ``model_id``."""
        model_id = model_data.get("model_id") or _new_id()
        self._conn.execute(
            """
            INSERT INTO models
                (model_id, run_id, name, path, framework, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                model_id,
                model_data.get("run_id", ""),
                model_data.get("name", ""),
                model_data.get("path", ""),
                model_data.get("framework", "pytorch"),
                _utcnow_iso(),
            ),
        )
        self._conn.commit()
        return model_id
