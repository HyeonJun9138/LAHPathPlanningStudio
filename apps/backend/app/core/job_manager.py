"""Background job manager using asyncio for non-blocking execution."""

from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    stopped = "stopped"


class Job:
    """Represents a single background job."""

    def __init__(
        self,
        job_id: str,
        stage: str,
        run_id: str = "",
        log_dir: Path | None = None,
    ):
        self.job_id = job_id
        self.stage = stage
        self.run_id = run_id
        self.status = JobStatus.queued
        self.progress: float = 0.0
        self.message: str = ""
        self.error: str | None = None
        self.started_at: str = ""
        self.finished_at: str | None = None
        self._task: asyncio.Task | None = None
        self._cancel_event = asyncio.Event()

        # Log files
        self.log_dir = log_dir
        self.stdout_log: Path | None = None
        self.stderr_log: Path | None = None
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            self.stdout_log = log_dir / f"{job_id}_stdout.log"
            self.stderr_log = log_dir / f"{job_id}_stderr.log"

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "run_id": self.run_id,
            "stage": self.stage,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def request_stop(self) -> None:
        self._cancel_event.set()

    def update_progress(self, progress: float, message: str = "") -> None:
        self.progress = min(max(progress, 0.0), 1.0)
        if message:
            self.message = message

    def _append_log(self, path: Path | None, text: str) -> None:
        if path:
            with open(path, "a", encoding="utf-8") as f:
                f.write(text + "\n")

    def log_stdout(self, text: str) -> None:
        self._append_log(self.stdout_log, text)

    def log_stderr(self, text: str) -> None:
        self._append_log(self.stderr_log, text)


# Type alias for the async callable that runs the actual work
JobCallable = Callable[[Job], Coroutine[Any, Any, None]]


class JobManager:
    """Manages background jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create_job(
        self,
        stage: str,
        run_id: str = "",
        log_dir: Path | None = None,
    ) -> Job:
        job_id = f"job_{stage}_{uuid.uuid4().hex[:8]}"
        job = Job(job_id=job_id, stage=stage, run_id=run_id, log_dir=log_dir)
        self._jobs[job_id] = job
        return job

    async def start_job(self, job: Job, func: JobCallable) -> None:
        """Start a job as an asyncio background task."""

        async def _wrapper() -> None:
            job.status = JobStatus.running
            job.started_at = datetime.now(timezone.utc).isoformat()
            try:
                await func(job)
                if job.is_cancelled:
                    job.status = JobStatus.stopped
                else:
                    job.status = JobStatus.completed
                    job.progress = 1.0
            except Exception as exc:
                job.status = JobStatus.failed
                job.error = str(exc)
                job.log_stderr(traceback.format_exc())
                logger.exception("Job %s failed", job.job_id)
            finally:
                job.finished_at = datetime.now(timezone.utc).isoformat()

        job._task = asyncio.create_task(_wrapper())

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        return [j.to_dict() for j in self._jobs.values()]

    def stop_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None:
            return False
        if job.status in (JobStatus.completed, JobStatus.failed, JobStatus.stopped):
            return False
        job.request_stop()
        if job._task and not job._task.done():
            job._task.cancel()
        job.status = JobStatus.stopped
        job.finished_at = datetime.now(timezone.utc).isoformat()
        return True


# Singleton
job_manager = JobManager()
