import { Cpu, ChevronDown } from 'lucide-react';
import { useAppStore } from '../../stores/appStore';
import type { TabId } from '../../types';

const tabMeta: Record<TabId, { title: string; description: string }> = {
  dashboard: { title: 'Dashboard', description: 'Project overview and quick actions' },
  resources: { title: 'Resource Manager', description: 'Manage terrain files and presets' },
  terrain: { title: 'Terrain Analysis', description: 'Preprocess and analyze terrain data' },
  hazard: { title: 'Hazard & LoS', description: 'Build risk maps and line-of-sight analysis' },
  mission: { title: 'Mission Designer', description: 'Configure mission parameters and waypoints' },
  candidate: { title: 'Candidate Lab', description: 'Generate and evaluate candidate waypoints' },
  training: { title: 'Training Center', description: 'Train RL policies with MaskablePPO' },
  evaluation: { title: 'Evaluation', description: 'Evaluate and compare model performance' },
  simulation: { title: 'Simulation Player', description: 'Replay episodes and analyze trajectories' },
  compare: { title: 'Experiment Compare', description: 'Compare runs and configurations' },
  reports: { title: 'Reports', description: 'Generate and export research reports' },
  settings: { title: 'Settings', description: 'Application configuration' },
};

export default function TopBar() {
  const { currentTab, currentProject, cudaInfo, selectedDevice, setSelectedDevice } = useAppStore();
  const meta = tabMeta[currentTab];

  return (
    <header className="h-14 flex items-center px-6 bg-white/60 backdrop-blur-xl border-b border-gray-200/50 shrink-0">
      {/* Tab info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-semibold text-gray-900 truncate">{meta.title}</h1>
          <span className="text-sm text-gray-400 hidden sm:inline">—</span>
          <span className="text-sm text-gray-500 truncate hidden sm:inline">{meta.description}</span>
        </div>
      </div>

      {/* Project name */}
      <div className="hidden md:flex items-center gap-4 mr-4">
        <span className="text-xs text-gray-400">Project:</span>
        <span className="text-sm font-medium text-gray-700 truncate max-w-[160px]">
          {currentProject?.name ?? 'No Project'}
        </span>
      </div>

      {/* CUDA status */}
      <div className="flex items-center gap-2">
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
            cudaInfo?.available
              ? 'bg-green-50 text-green-700'
              : 'bg-gray-100 text-gray-500'
          }`}
        >
          <Cpu size={13} />
          <span>{cudaInfo?.available ? 'CUDA' : 'CPU'}</span>
        </div>

        {/* Device selector */}
        {cudaInfo?.available && cudaInfo.devices.length > 0 && (
          <div className="relative">
            <select
              value={selectedDevice}
              onChange={(e) => setSelectedDevice(e.target.value)}
              className="appearance-none pl-2 pr-6 py-1 text-xs bg-white/70 border border-gray-200/50 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-400 cursor-pointer"
            >
              <option value="cpu">CPU</option>
              {cudaInfo.devices.map((d) => (
                <option key={d.torch_name} value={d.torch_name}>
                  {d.name} ({d.torch_name})
                </option>
              ))}
            </select>
            <ChevronDown size={12} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
          </div>
        )}
      </div>
    </header>
  );
}
