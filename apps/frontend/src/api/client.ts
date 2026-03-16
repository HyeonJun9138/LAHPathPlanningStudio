import axios from 'axios';
import type {
  HealthResponse, SystemInfo, CudaInfo,
  Project, ResourceFile, Job,
  TerrainMetadata, TerrainArtifact, PreprocessConfig,
  HazardConfig, HazardSummary,
  MissionConfig, MissionValidation,
  DryRunResult,
  TrainingConfig, TrainingMetrics,
  EvaluationConfig, EvaluationResults,
  EpisodeData, RunMeta, Report, ReportConfig,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// ── Health & System ──
export const getHealth = () =>
  api.get<HealthResponse>('/health').then(r => r.data);

export const getSystemInfo = () =>
  api.get<SystemInfo>('/system/info').then(r => r.data);

export const getCudaInfo = () =>
  api.get<CudaInfo>('/system/cuda').then(r => r.data);

// ── Projects ──
export const getProjects = () =>
  api.get<Project[]>('/projects').then(r => r.data);

export const createProject = (data: { name: string; description?: string }) =>
  api.post<Project>('/projects', data).then(r => r.data);

export const scanResources = (projectId: string) =>
  api.post<ResourceFile[]>(`/projects/${projectId}/scan-resources`).then(r => r.data);

// ── Jobs ──
export const getJobs = () =>
  api.get<Job[]>('/jobs').then(r => r.data);

export const getJob = (jobId: string) =>
  api.get<Job>(`/jobs/${jobId}`).then(r => r.data);

export const stopJob = (jobId: string) =>
  api.post(`/jobs/${jobId}/stop`).then(r => r.data);

// ── Terrain ──
export const registerTerrain = (data: { project_id: string; source_path: string; terrain_id: string }) =>
  api.post('/terrain/register', data).then(r => r.data);

export const preprocessTerrain = (data: { project_id: string; terrain_id: string; config: PreprocessConfig }) =>
  api.post('/terrain/preprocess', data).then(r => r.data);

export const getTerrainMetadata = (terrainId: string) =>
  api.get<TerrainMetadata>(`/terrain/${terrainId}/metadata`).then(r => r.data);

export const getTerrainArtifacts = (terrainId: string) =>
  api.get<TerrainArtifact[]>(`/terrain/${terrainId}/artifacts`).then(r => r.data);

export const getTerrainPreview = (terrainId: string, artifactName: string) =>
  api.get<string>(`/terrain/${terrainId}/preview/${artifactName}`, { responseType: 'text' }).then(r => r.data);

// ── Hazard ──
export const buildHazard = (data: { project_id: string; terrain_id: string; config: HazardConfig }) =>
  api.post('/hazard/build', data).then(r => r.data);

export const getHazardSummary = (runId: string) =>
  api.get<HazardSummary>(`/hazard/${runId}/summary`).then(r => r.data);

export const getHazardPreview = (runId: string, name: string) =>
  api.get<string>(`/hazard/${runId}/preview/${name}`, { responseType: 'text' }).then(r => r.data);

// ── Mission ──
export const validateMission = (data: MissionConfig) =>
  api.post<MissionValidation>('/missions/validate', data).then(r => r.data);

export const getMissionPresets = () =>
  api.get<MissionConfig[]>('/missions/presets').then(r => r.data);

// ── Env / Candidate ──
export const createEnv = (data: { project_id: string; terrain_id: string; mission_id: string }) =>
  api.post('/envs/create', data).then(r => r.data);

export const dryRun = (data: { project_id: string; env_id: string }) =>
  api.post<DryRunResult>('/envs/dry-run', data).then(r => r.data);

export const getSampleObservation = (envId: string) =>
  api.get(`/envs/${envId}/sample-observation`).then(r => r.data);

// ── Training ──
export const startTraining = (data: { project_id: string; run_id?: string; config: TrainingConfig }) =>
  api.post('/training/start', data).then(r => r.data);

export const stopTraining = (runId: string) =>
  api.post('/training/stop', { run_id: runId }).then(r => r.data);

export const getTrainingMetrics = (runId: string) =>
  api.get<TrainingMetrics>(`/training/${runId}/metrics`).then(r => r.data);

// ── Evaluation ──
export const runEvaluation = (data: EvaluationConfig) =>
  api.post('/evaluation/run', data).then(r => r.data);

export const getEvaluationResults = (runId: string) =>
  api.get<EvaluationResults>(`/evaluation/${runId}/results`).then(r => r.data);

// ── Simulation ──
export const executeRollout = (data: { project_id: string; run_id: string; checkpoint_path: string }) =>
  api.post('/simulation/rollout', data).then(r => r.data);

export const getEpisode = (runId: string, episodeId: string) =>
  api.get<EpisodeData>(`/simulation/${runId}/episode/${episodeId}`).then(r => r.data);

// ── Runs ──
export const getRuns = (params?: { stage?: string; terrain_id?: string }) =>
  api.get<RunMeta[]>('/runs', { params }).then(r => r.data);

export const getRun = (runId: string) =>
  api.get<RunMeta>(`/runs/${runId}`).then(r => r.data);

export const getRunArtifacts = (runId: string) =>
  api.get<string[]>(`/runs/${runId}/artifacts`).then(r => r.data);

export const addRunTags = (runId: string, tags: string[]) =>
  api.post(`/runs/${runId}/tags`, { tags }).then(r => r.data);

// ── Reports ──
export const generateReport = (data: ReportConfig) =>
  api.post('/reports/generate', data).then(r => r.data);

export const getReport = (reportId: string) =>
  api.get<Report>(`/reports/${reportId}`).then(r => r.data);
