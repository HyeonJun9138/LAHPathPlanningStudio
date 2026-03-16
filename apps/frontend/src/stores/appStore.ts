import { create } from 'zustand';
import type { TabId, Project, CudaInfo, Job, ConsoleEntry, AppSettings } from '../types';
import type { Locale } from '../i18n';

interface AppState {
  // Navigation
  currentTab: TabId;
  sidebarExpanded: boolean;
  setCurrentTab: (tab: TabId) => void;
  toggleSidebar: () => void;

  // Project
  currentProject: Project | null;
  projects: Project[];
  setCurrentProject: (project: Project | null) => void;
  setProjects: (projects: Project[]) => void;

  // CUDA
  cudaInfo: CudaInfo | null;
  selectedDevice: string;
  setCudaInfo: (info: CudaInfo) => void;
  setSelectedDevice: (device: string) => void;

  // Jobs
  jobs: Job[];
  setJobs: (jobs: Job[]) => void;
  updateJob: (job: Job) => void;

  // Console
  consoleExpanded: boolean;
  consoleTab: 'logs' | 'progress' | 'artifacts';
  consoleLogs: ConsoleEntry[];
  toggleConsole: () => void;
  setConsoleTab: (tab: 'logs' | 'progress' | 'artifacts') => void;
  addLog: (entry: Omit<ConsoleEntry, 'id' | 'timestamp'>) => void;
  clearLogs: () => void;

  // Locale
  locale: Locale;
  setLocale: (locale: Locale) => void;

  // Settings
  settings: AppSettings;
  updateSettings: (s: Partial<AppSettings>) => void;
}

let logCounter = 0;

export const useAppStore = create<AppState>((set) => ({
  // Navigation
  currentTab: 'dashboard',
  sidebarExpanded: true,
  setCurrentTab: (tab) => set({ currentTab: tab }),
  toggleSidebar: () => set((s) => ({ sidebarExpanded: !s.sidebarExpanded })),

  // Project
  currentProject: {
    project_id: 'default_project',
    name: 'Default Project',
    created_at: '2026-03-14T12:00:00',
    workspace_path: './workspace/projects/default_project',
  },
  projects: [],
  setCurrentProject: (project) => set({ currentProject: project }),
  setProjects: (projects) => set({ projects }),

  // CUDA
  cudaInfo: null,
  selectedDevice: 'cuda:0',
  setCudaInfo: (info) => set({ cudaInfo: info }),
  setSelectedDevice: (device) => set({ selectedDevice: device }),

  // Jobs
  jobs: [],
  setJobs: (jobs) => set({ jobs }),
  updateJob: (job) =>
    set((s) => ({
      jobs: s.jobs.map((j) => (j.job_id === job.job_id ? job : j)),
    })),

  // Console
  consoleExpanded: false,
  consoleTab: 'logs',
  consoleLogs: [],
  toggleConsole: () => set((s) => ({ consoleExpanded: !s.consoleExpanded })),
  setConsoleTab: (tab) => set({ consoleTab: tab }),
  addLog: (entry) =>
    set((s) => ({
      consoleLogs: [
        ...s.consoleLogs.slice(-499),
        {
          ...entry,
          id: `log-${++logCounter}`,
          timestamp: new Date().toISOString(),
        },
      ],
    })),
  clearLogs: () => set({ consoleLogs: [] }),

  // Locale
  locale: 'ko' as Locale,
  setLocale: (locale) => set({ locale }),

  // Settings
  settings: {
    workspace_root: './workspace/projects',
    default_device: 'cuda:0',
    plotting_theme: 'light',
    autosave_seconds: 30,
    job_polling_interval_ms: 2000,
    log_retention_days: 7,
    external_editor_path: '',
  },
  updateSettings: (s) =>
    set((state) => ({ settings: { ...state.settings, ...s } })),
}));
