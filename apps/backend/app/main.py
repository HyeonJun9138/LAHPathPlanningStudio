"""FastAPI application entry point for LAH Terrain Path Planning Studio."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure engine modules are importable
_project_root = Path(__file__).resolve().parents[3]
_src_path = str(_project_root / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from .core.config import settings
from .core.database import DatabaseManager
from .core.run_manager import run_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Initialize shared SQLite database
    db_path = settings.workspace_path / "global.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = DatabaseManager(db_path)
    await db.connect()
    app.state.db = db
    app.state.run_manager = run_manager

    # Ensure workspace directories exist
    settings.workspace_path.mkdir(parents=True, exist_ok=True)
    settings.shared_cache_path.mkdir(parents=True, exist_ok=True)

    yield

    await db.close()


app = FastAPI(
    title=settings.name,
    version=settings.version,
    lifespan=lifespan,
)

# CORS – allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend.origin,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Register all routers
# ---------------------------------------------------------------------------
from .api.health import router as health_router
from .api.system import router as system_router
from .api.projects import router as projects_router
from .api.terrain import router as terrain_router
from .api.hazard import router as hazard_router
from .api.mission import router as mission_router
from .api.env import router as env_router
from .api.training import router as training_router
from .api.evaluation import router as evaluation_router
from .api.simulation import router as simulation_router
from .api.runs import router as runs_router
from .api.reports import router as reports_router
from .api.jobs import router as jobs_router
from .api.ai import router as ai_router

app.include_router(health_router)
app.include_router(system_router)
app.include_router(projects_router)
app.include_router(terrain_router)
app.include_router(hazard_router)
app.include_router(mission_router)
app.include_router(env_router)
app.include_router(training_router)
app.include_router(evaluation_router)
app.include_router(simulation_router)
app.include_router(runs_router)
app.include_router(reports_router)
app.include_router(jobs_router)
app.include_router(ai_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
