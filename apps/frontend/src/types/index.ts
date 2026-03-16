// ── System & CUDA ──
export interface CudaDevice {
  name: string;
  index: number;
  total_memory_mb: number;
  free_memory_mb: number;
  torch_name: string;
}

export interface CudaInfo {
  available: boolean;
  selected_default: string;
  devices: CudaDevice[];
  torch_version: string;
  cuda_version: string;
}

export interface SystemInfo {
  platform: string;
  python_version: string;
  torch_version: string;
  cuda_available: boolean;
  workspace_root: string;
}

export interface HealthResponse {
  status: string;
  version: string;
}

// ── Projects ──
export interface Project {
  project_id: string;
  name: string;
  created_at: string;
  workspace_path: string;
  description?: string;
}

export interface ResourceFile {
  filename: string;
  type: string;
  crs: string;
  resolution_m: number;
  dimensions: [number, number];
  file_size_mb: number;
  bounds?: [number, number, number, number];
  path: string;
}

// ── Jobs ──
export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'stopped';

export interface Job {
  job_id: string;
  status: JobStatus;
  progress: number;
  message: string;
  stage: string;
  run_id?: string;
  started_at?: string;
  finished_at?: string;
}

// ── Terrain ──
export interface TerrainMetadata {
  terrain_id: string;
  source_path: string;
  crs: string;
  resolution_m: number;
  dimensions: [number, number];
  bounds: [number, number, number, number];
  nodata_value: number | null;
  derivatives_available: string[];
  stats: Record<string, DerivativeStats>;
}

export interface DerivativeStats {
  min: number;
  max: number;
  mean: number;
  std: number;
}

export interface TerrainArtifact {
  name: string;
  path: string;
  type: string;
  size_mb: number;
}

export interface PreprocessConfig {
  terrain_id: string;
  source_path: string;
  target_crs: string;
  target_resolution_m: number;
  nodata_fill: string;
  generate_overviews: boolean;
  overview_factors: number[];
  derivatives: Record<string, boolean>;
}

// ── Hazard ──
export interface HazardSource {
  id: string;
  name: string;
  type: string;
  x: number;
  y: number;
  z: number;
  influence_radius_m: number;
  altitude_weight_profile: Record<string, number>;
  visibility_sensitive: boolean;
  range_falloff_type: string;
  range_falloff_scale: number;
  sector_azimuth_deg: number;
  sector_width_deg: number;
  enabled: boolean;
}

export interface HazardConfig {
  fusion_mode: 'probabilistic_union' | 'sum_clip' | 'max';
  clearance_margin_m: number;
  altitude_bands: AltitudeBand[];
  weights: Record<string, number>;
  sources: HazardSource[];
}

export interface AltitudeBand {
  name: string;
  agl_m: number;
}

export interface HazardSummary {
  run_id: string;
  terrain_id: string;
  num_sources: number;
  altitude_bands: string[];
  risk_stats: Record<string, DerivativeStats>;
  artifacts: string[];
}

// ── Mission ──
export interface MissionPoint {
  x: number;
  y: number;
  agl_m: number;
}

export interface ObserveBox {
  center_x: number;
  center_y: number;
  center_z: number;
  size_x: number;
  size_y: number;
  size_z: number;
  required_duration_sec: number;
}

export interface MissionConfig {
  mission_id: string;
  terrain_id: string;
  max_episode_time_sec: number;
  start: MissionPoint;
  goal: MissionPoint;
  observe_box: ObserveBox;
  safe_hold_points: MissionPoint[];
  alternate_lz: MissionPoint[];
}

export interface MissionValidation {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

// ── Candidate / Env ──
export interface CandidateConfig {
  max_candidates: number;
  transit_count: number;
  hold_count: number;
  observe_setup_count: number;
  popup_observe_count: number;
  egress_count: number;
  return_count: number;
  divert_count: number;
  distance_bands_m: number[];
  heading_samples_deg: number[];
  agl_bands: Record<string, number>;
}

export interface DryRunResult {
  candidates: CandidateFeature[];
  action_mask: boolean[];
  reward_breakdown: Record<string, number>;
}

export interface CandidateFeature {
  index: number;
  x: number;
  y: number;
  agl_m: number;
  primitive: string;
  distance_m: number;
  risk: number;
  clearance_m: number;
  progress: number;
  visible_ratio: number;
  masked: boolean;
}

// ── Training ──
export interface TrainingConfig {
  algorithm: 'MaskablePPO' | 'PPO';
  device: string;
  seed: number;
  total_timesteps: number;
  n_envs: number;
  n_steps: number;
  batch_size: number;
  learning_rate: number;
  gamma: number;
  gae_lambda: number;
  clip_range: number;
  ent_coef: number;
  vf_coef: number;
  max_grad_norm: number;
  checkpoint_interval: number;
  eval_interval: number;
  curriculum: string;
}

export interface TrainingMetrics {
  timestep: number;
  episodes: number;
  mean_reward: number;
  mean_length: number;
  success_rate: number;
  mean_risk: number;
  learning_rate: number;
  entropy_loss: number;
  policy_loss: number;
  value_loss: number;
  history: MetricHistory;
}

export interface MetricHistory {
  timesteps: number[];
  rewards: number[];
  success_rates: number[];
  episode_lengths: number[];
  risks: number[];
}

export interface Checkpoint {
  path: string;
  timestep: number;
  mean_reward: number;
  success_rate: number;
  created_at: string;
}

// ── Evaluation ──
export interface EvaluationConfig {
  run_id: string;
  checkpoint_path: string;
  baselines: string[];
  terrain_split: string;
  scenario: string;
  n_episodes: number;
}

export interface EvaluationResults {
  run_id: string;
  metrics: Record<string, BaselineMetrics>;
  terrain_splits: Record<string, Record<string, number>>;
}

export interface BaselineMetrics {
  success_rate: number;
  mean_reward: number;
  mean_risk: number;
  mean_path_length: number;
  mean_episode_length: number;
  std_reward: number;
  std_risk: number;
}

// ── Simulation ──
export interface EpisodeData {
  episode_id: string;
  run_id: string;
  steps: EpisodeStep[];
  total_reward: number;
  success: boolean;
  duration_sec: number;
}

export interface EpisodeStep {
  step: number;
  x: number;
  y: number;
  z: number;
  agl_m: number;
  mode: string;
  primitive: string;
  risk: number;
  reward: number;
  cumulative_reward: number;
  action_index: number;
  event?: string;
}

// ── Runs ──
export interface RunMeta {
  run_id: string;
  project_id: string;
  stage: string;
  terrain_id: string;
  algorithm?: string;
  device?: string;
  seed?: number;
  started_at: string;
  finished_at?: string;
  status: string;
  config_hash: string;
  tags: string[];
  metrics_summary?: Record<string, number>;
}

// ── Reports ──
export interface ReportConfig {
  run_ids: string[];
  template: string;
  include_sections: string[];
  include_png: boolean;
  include_config_diff: boolean;
}

export interface Report {
  report_id: string;
  content_markdown: string;
  content_html: string;
  created_at: string;
  artifacts: string[];
}

// ── Settings ──
export interface AppSettings {
  workspace_root: string;
  default_device: string;
  plotting_theme: 'light' | 'dark';
  autosave_seconds: number;
  job_polling_interval_ms: number;
  log_retention_days: number;
  external_editor_path: string;
}

// ── Console / Log ──
export interface ConsoleEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'debug';
  message: string;
  source?: string;
}

// ── Tab definition ──
export type TabId =
  | 'dashboard'
  | 'resources'
  | 'terrain'
  | 'hazard'
  | 'mission'
  | 'candidate'
  | 'training'
  | 'evaluation'
  | 'simulation'
  | 'compare'
  | 'reports'
  | 'settings';

export interface TabDef {
  id: TabId;
  label: string;
  description: string;
}
