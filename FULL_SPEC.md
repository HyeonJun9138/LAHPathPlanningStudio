# LAH Terrain Path Planning Studio - Full Implementation Specification

## Project Overview
Build a complete local HTML-based research platform for terrain-based 3D sparse waypoint path planning.
The platform uses three GeoTIFF terrain files (Hongik_48km.tif, Inje_48km.tif, Jipo_48km.tif) already in resource/.

## Tech Stack
- Backend: FastAPI + Pydantic v2 + Uvicorn
- Frontend: React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- Engine: Python (numpy, scipy, rasterio for geo)
- RL: Gymnasium + Stable Baselines3 + sb3-contrib (MaskablePPO)
- DL: PyTorch with CUDA support
- Geospatial: rasterio, pyproj, shapely
- Charts: Plotly (frontend via plotly.js/react-plotly)
- State: Zustand + React Query
- DB: SQLite
- Testing: pytest

## Directory Structure (MUST follow exactly)
```
LAHPathPlanningStudio/
├── resource/
│   ├── Hongik_48km.tif
│   ├── Inje_48km.tif
│   ├── Jipo_48km.tif
│   ├── hazards/
│   │   └── sample_hazards.json
│   ├── missions/
│   │   └── sample_mission.yaml
│   └── presets/
│       ├── curriculum_a.yaml
│       ├── curriculum_b.yaml
│       └── curriculum_c.yaml
├── apps/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── health.py
│   │   │   │   ├── system.py
│   │   │   │   ├── projects.py
│   │   │   │   ├── terrain.py
│   │   │   │   ├── hazard.py
│   │   │   │   ├── mission.py
│   │   │   │   ├── env.py
│   │   │   │   ├── training.py
│   │   │   │   ├── evaluation.py
│   │   │   │   ├── simulation.py
│   │   │   │   ├── runs.py
│   │   │   │   ├── reports.py
│   │   │   │   └── jobs.py
│   │   │   ├── core/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── config.py
│   │   │   │   ├── database.py
│   │   │   │   ├── job_manager.py
│   │   │   │   └── run_manager.py
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       └── schemas.py
│   │   └── requirements.txt
│   └── frontend/
│       ├── package.json
│       ├── vite.config.ts
│       ├── tsconfig.json
│       ├── tailwind.config.js
│       ├── postcss.config.js
│       ├── index.html
│       └── src/
│           ├── main.tsx
│           ├── App.tsx
│           ├── index.css
│           ├── api/
│           │   └── client.ts
│           ├── stores/
│           │   └── appStore.ts
│           ├── components/
│           │   ├── layout/
│           │   │   ├── AppLayout.tsx
│           │   │   ├── Sidebar.tsx
│           │   │   ├── TopBar.tsx
│           │   │   └── BottomConsole.tsx
│           │   ├── common/
│           │   │   ├── GlassCard.tsx
│           │   │   ├── MetricPill.tsx
│           │   │   ├── StatusBadge.tsx
│           │   │   ├── SectionTitle.tsx
│           │   │   ├── ParameterRow.tsx
│           │   │   ├── RunActionBar.tsx
│           │   │   ├── PlotCard.tsx
│           │   │   └── ArtifactList.tsx
│           │   └── tabs/
│           │       ├── Dashboard.tsx
│           │       ├── ResourceManager.tsx
│           │       ├── TerrainAnalysis.tsx
│           │       ├── HazardBuilder.tsx
│           │       ├── MissionDesigner.tsx
│           │       ├── CandidateLab.tsx
│           │       ├── TrainingCenter.tsx
│           │       ├── Evaluation.tsx
│           │       ├── SimulationPlayer.tsx
│           │       ├── ExperimentCompare.tsx
│           │       ├── Reports.tsx
│           │       └── Settings.tsx
│           └── types/
│               └── index.ts
├── src/
│   └── engine/
│       ├── __init__.py
│       ├── io/
│       │   ├── __init__.py
│       │   └── geotiff_loader.py
│       ├── terrain/
│       │   ├── __init__.py
│       │   ├── reproject.py
│       │   ├── resample.py
│       │   ├── derivatives.py
│       │   ├── patch_sampler.py
│       │   ├── preview.py
│       │   ├── cache_manager.py
│       │   └── pipeline.py
│       ├── hazard/
│       │   ├── __init__.py
│       │   ├── schema.py
│       │   ├── los.py
│       │   ├── risk_models.py
│       │   ├── fusion.py
│       │   ├── observe_box.py
│       │   └── pipeline.py
│       ├── mission/
│       │   ├── __init__.py
│       │   ├── schema.py
│       │   ├── state_machine.py
│       │   ├── primitives.py
│       │   ├── candidate_generator.py
│       │   └── validator.py
│       ├── env/
│       │   ├── __init__.py
│       │   ├── terrain_env.py
│       │   ├── reward.py
│       │   ├── observation.py
│       │   └── wrappers.py
│       ├── training/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── device.py
│       │   ├── feature_extractor.py
│       │   ├── callbacks.py
│       │   ├── train_runner.py
│       │   └── plots.py
│       ├── evaluation/
│       │   ├── __init__.py
│       │   ├── evaluator.py
│       │   ├── metrics.py
│       │   ├── compare.py
│       │   └── plots.py
│       ├── simulation/
│       │   ├── __init__.py
│       │   ├── rollout.py
│       │   ├── player_data.py
│       │   └── export.py
│       ├── baselines/
│       │   ├── __init__.py
│       │   ├── random_masked.py
│       │   ├── risk_astar.py
│       │   └── rule_fsm.py
│       └── reporting/
│           ├── __init__.py
│           ├── run_db.py
│           ├── report_generator.py
│           └── plots.py
├── configs/
│   ├── app.yaml
│   ├── logging.yaml
│   ├── dev.yaml
│   └── preprocess_config.yaml
├── scripts/
│   ├── bootstrap_windows.ps1
│   ├── run_backend.ps1
│   ├── run_frontend.ps1
│   ├── run_all.ps1
│   ├── check_cuda.ps1
│   ├── check_cuda.py
│   └── init_workspace.py
├── workspace/
│   ├── projects/
│   └── shared_cache/
├── tests/
│   ├── unit/
│   │   ├── test_terrain.py
│   │   ├── test_hazard.py
│   │   ├── test_env.py
│   │   ├── test_training.py
│   │   └── test_evaluation.py
│   ├── integration/
│   │   └── test_pipeline.py
│   └── fixtures/
│       ├── hazard_sample.json
│       └── mission_sample.json
├── docs/
│   └── architecture.md
├── README.md
├── .gitignore
└── pyproject.toml
```

## CRITICAL DESIGN PRINCIPLES
1. 2.5D terrain + altitude band (NOT full 3D voxel)
2. Sparse waypoint planning - policy selects from K=32 candidate waypoints
3. Motion primitives handle actual flight path generation
4. Action masking is mandatory
5. All runs must have run_id with full config snapshots
6. All plots saved as PNG files
7. Settings externalized to YAML
8. Windows-compatible paths and subprocess handling
9. CUDA device selection in GUI
10. NO weapons, attack logic, or combat automation

## Backend API Endpoints (MUST implement all)
- GET /api/health
- GET /api/system/info
- GET /api/system/cuda
- GET /api/projects (list)
- POST /api/projects (create)
- GET /api/projects/{project_id}/structure
- POST /api/projects/{project_id}/scan-resources
- GET /api/jobs, GET /api/jobs/{job_id}, POST /api/jobs/{job_id}/stop
- POST /api/terrain/register
- POST /api/terrain/preprocess
- GET /api/terrain/{terrain_id}/metadata
- GET /api/terrain/{terrain_id}/artifacts
- GET /api/terrain/{terrain_id}/preview/{artifact_name}
- POST /api/hazard/build
- GET /api/hazard/{run_id}/summary
- GET /api/hazard/{run_id}/preview/{name}
- POST /api/missions/validate
- POST /api/envs/create
- POST /api/envs/dry-run
- GET /api/envs/{env_id}/sample-observation
- POST /api/training/start
- POST /api/training/stop
- GET /api/training/{run_id}/metrics
- POST /api/evaluation/run
- GET /api/evaluation/{run_id}/results
- POST /api/simulation/rollout
- GET /api/simulation/{run_id}/episode/{episode_id}
- GET /api/runs (list)
- GET /api/runs/{run_id}
- GET /api/runs/{run_id}/artifacts
- POST /api/runs/{run_id}/tags
- POST /api/reports/generate
- GET /api/reports/{report_id}

## Frontend 12 Tabs (ALL required)
1. Dashboard - project cards, CUDA status, recent runs, pipeline timeline
2. Resource Manager - tif list, metadata, thumbnails, scan
3. Terrain Analysis - tif select, preprocess config, derivative map previews
4. Hazard & LoS Builder - hazard sources, altitude bands, risk maps, feasibility
5. Mission Designer - start/goal/observe points on map, mission JSON
6. Candidate & Primitive Lab - primitive list, candidate preview, dry-run
7. Training Center - algorithm/device select, hyperparams, live reward curve
8. Evaluation - run/checkpoint select, baseline compare, metrics plots
9. Simulation Player - top-down map, altitude profile, playback controls
10. Experiment Compare - multi-run select, config diff, metric comparison
11. Reports - markdown/HTML report generation, section selection
12. Settings - workspace, device, theme, autosave

## Design System
- Apple-inspired: translucent glass cards, backdrop blur, large radius, subtle shadows
- Light neutral gray + subtle blue accents
- Professional research tool aesthetic
- Data-dense but not cramped
- All parameters have tooltips with descriptions, units, ranges
