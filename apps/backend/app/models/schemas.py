"""Pydantic v2 request/response models for all API endpoints."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    stopped = "stopped"


class RunStage(str, Enum):
    preprocess = "01_preprocess"
    hazard = "02_hazard"
    env = "03_env"
    training = "04_training"
    evaluation = "05_evaluation"
    simulation = "06_simulation"
    reports = "99_reports"


# ---------------------------------------------------------------------------
# Generic / shared
# ---------------------------------------------------------------------------

class StatusResponse(BaseModel):
    status: str
    message: str = ""


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

class CudaDevice(BaseModel):
    name: str
    index: int
    total_memory_mb: float
    free_memory_mb: float
    torch_name: str


class CudaInfo(BaseModel):
    available: bool
    selected_default: str = "cpu"
    devices: list[CudaDevice] = []
    torch_version: str = ""
    cuda_version: str = ""
    cudnn_available: bool = False


class SystemInfo(BaseModel):
    python_version: str
    os_name: str
    hostname: str
    platform: str
    packages: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    description: str = ""
    created_at: str
    workspace_path: str


class ProjectStructure(BaseModel):
    project_id: str
    tree: dict[str, Any]


class ResourceScanResult(BaseModel):
    project_id: str
    terrains: list[str] = []
    hazards: list[str] = []
    missions: list[str] = []
    presets: list[str] = []


# ---------------------------------------------------------------------------
# Terrain
# ---------------------------------------------------------------------------

class TerrainRegisterRequest(BaseModel):
    project_id: str
    file_path: str
    terrain_id: str | None = None


class TerrainMetadata(BaseModel):
    terrain_id: str
    file_path: str
    crs: str = ""
    width: int = 0
    height: int = 0
    resolution_m: float = 0.0
    bounds: dict[str, float] = {}
    nodata: float | None = None
    registered_at: str = ""


class TerrainPreprocessRequest(BaseModel):
    project_id: str
    terrain_id: str
    target_crs: str = "auto"
    target_resolution_m: float = 30.0
    nodata_fill: str = "nearest"
    generate_overviews: bool = True
    overview_factors: list[int] = Field(default_factory=lambda: [2, 4, 8, 16])
    derivatives: dict[str, bool] = Field(default_factory=lambda: {
        "slope": True, "aspect": True, "roughness": True,
        "curvature": True, "tpi": True,
    })


class TerrainArtifact(BaseModel):
    name: str
    path: str
    artifact_type: str = ""
    size_bytes: int = 0


# ---------------------------------------------------------------------------
# Hazard
# ---------------------------------------------------------------------------

class HazardSource(BaseModel):
    id: str
    name: str
    type: str
    x: float
    y: float
    z: float = 0.0
    influence_radius_m: float = 2500.0
    altitude_weight_profile: dict[str, float] = {}
    visibility_sensitive: bool = False
    range_falloff_type: str = "exp"
    range_falloff_scale: float = 1200.0
    sector_azimuth_deg: float | None = None
    sector_width_deg: float | None = None
    enabled: bool = True


class HazardBuildRequest(BaseModel):
    project_id: str
    terrain_id: str
    sources: list[HazardSource]
    fusion_mode: str = "probabilistic_union"
    clearance_margin_m: float = 20.0
    altitude_bands: list[dict[str, Any]] = Field(default_factory=lambda: [
        {"name": "low_masked", "agl_m": 20},
        {"name": "mid_transit", "agl_m": 80},
        {"name": "high_observe", "agl_m": 180},
    ])
    weights: dict[str, float] = Field(default_factory=lambda: {
        "visible_ratio": 0.45, "distance_cost": 0.25,
        "zone_penalty": 0.20, "altitude_penalty": 0.10,
    })


class HazardSummary(BaseModel):
    run_id: str
    terrain_id: str
    num_sources: int = 0
    fusion_mode: str = ""
    altitude_bands: list[str] = []
    risk_stats: dict[str, Any] = {}
    artifacts: list[str] = []


# ---------------------------------------------------------------------------
# Mission
# ---------------------------------------------------------------------------

class Waypoint(BaseModel):
    x: float
    y: float
    agl_m: float = 0.0


class ObserveBox(BaseModel):
    center_x: float
    center_y: float
    center_z: float
    size_x: float
    size_y: float
    size_z: float
    required_duration_sec: float = 10.0


class MissionValidateRequest(BaseModel):
    terrain_id: str
    start: Waypoint
    goal: Waypoint
    observe_box: ObserveBox | None = None
    safe_hold_points: list[Waypoint] = []
    alternate_lz: list[Waypoint] = []
    max_episode_time_sec: float = 1800.0


class MissionResponse(BaseModel):
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    mission_id: str = ""


class MissionPreset(BaseModel):
    preset_id: str
    name: str
    description: str = ""
    file_path: str = ""


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

class EnvCreateRequest(BaseModel):
    project_id: str
    terrain_id: str
    mission_id: str | None = None
    hazard_run_id: str | None = None
    max_candidates: int = 32
    reward_config: dict[str, float] = {}


class DryRunRequest(BaseModel):
    project_id: str
    env_id: str
    num_steps: int = 10
    action_mode: str = "random"


class DryRunResponse(BaseModel):
    env_id: str
    steps: list[dict[str, Any]] = []
    total_reward: float = 0.0
    done: bool = False


class SampleObservation(BaseModel):
    env_id: str
    observation: dict[str, Any] = {}
    action_mask: list[int] = []
    info: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

class TrainingStartRequest(BaseModel):
    project_id: str
    terrain_id: str
    algorithm: str = "MaskablePPO"
    device: str = "cuda:0"
    seed: int = 42
    total_timesteps: int = 1_000_000
    n_envs: int = 4
    n_steps: int = 1024
    batch_size: int = 256
    learning_rate: float = 0.0003
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_range: float = 0.2
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    checkpoint_interval: int = 50_000
    eval_interval: int = 25_000
    curriculum: str = ""
    mission_id: str | None = None
    hazard_run_id: str | None = None
    reward_config: dict[str, float] = {}


class TrainingStopRequest(BaseModel):
    run_id: str


class TrainingStatus(BaseModel):
    run_id: str
    status: JobStatus = JobStatus.queued
    progress: float = 0.0
    timesteps: int = 0
    episodes: int = 0
    current_reward: float = 0.0
    best_reward: float = 0.0
    message: str = ""


class TrainingMetrics(BaseModel):
    run_id: str
    timesteps: list[int] = []
    rewards: list[float] = []
    episode_lengths: list[float] = []
    losses: dict[str, list[float]] = {}
    additional: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

class EvaluationRequest(BaseModel):
    project_id: str
    terrain_id: str
    run_id: str
    checkpoint: str = "best"
    num_episodes: int = 50
    baselines: list[str] = []
    device: str = "cuda:0"


class EvaluationResult(BaseModel):
    run_id: str
    eval_run_id: str = ""
    status: JobStatus = JobStatus.queued
    metrics: dict[str, Any] = {}
    baseline_metrics: dict[str, dict[str, Any]] = {}
    plots: list[str] = []


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

class SimulationRequest(BaseModel):
    project_id: str
    terrain_id: str
    run_id: str
    checkpoint: str = "best"
    num_episodes: int = 1
    device: str = "cuda:0"
    record: bool = True


class EpisodeStep(BaseModel):
    step: int
    x: float
    y: float
    z: float
    action: int
    reward: float
    risk: float = 0.0
    mode: str = ""


class EpisodeData(BaseModel):
    run_id: str
    episode_id: str
    steps: list[EpisodeStep] = []
    total_reward: float = 0.0
    success: bool = False
    length: int = 0
    metadata: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

class RunTag(BaseModel):
    key: str
    value: str


class RunResponse(BaseModel):
    run_id: str
    project_id: str
    stage: str
    terrain_id: str = ""
    status: str = ""
    started_at: str = ""
    finished_at: str | None = None
    config: dict[str, Any] = {}
    tags: list[RunTag] = []


class RunMetrics(BaseModel):
    run_id: str
    metrics: dict[str, Any] = {}


class RunArtifact(BaseModel):
    name: str
    path: str
    artifact_type: str = ""
    size_bytes: int = 0
    created_at: str = ""


class RunListFilter(BaseModel):
    project_id: str | None = None
    stage: str | None = None
    status: str | None = None
    terrain_id: str | None = None
    tag_key: str | None = None
    tag_value: str | None = None
    limit: int = 100
    offset: int = 0


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class ReportGenerateRequest(BaseModel):
    project_id: str
    title: str = "Report"
    run_ids: list[str] = []
    include_sections: list[str] = Field(default_factory=lambda: [
        "summary", "configs", "metrics", "plots", "compare", "artifacts"
    ])
    include_png: bool = True
    include_config_diff: bool = True
    best_run_rule: str = "highest_success_lowest_risk"


class ReportResponse(BaseModel):
    report_id: str
    project_id: str
    title: str = ""
    status: str = "pending"
    created_at: str = ""
    html_path: str | None = None
    sections: list[str] = []


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class JobResponse(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.queued
    progress: float = 0.0
    message: str = ""
    run_id: str = ""
    stage: str = ""
    started_at: str = ""
    finished_at: str | None = None
    error: str | None = None
