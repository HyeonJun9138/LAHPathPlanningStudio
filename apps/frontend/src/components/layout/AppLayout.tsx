import { lazy, Suspense } from 'react';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import BottomConsole from './BottomConsole';
import { useAppStore } from '../../stores/appStore';
import type { TabId } from '../../types';

const Dashboard = lazy(() => import('../tabs/Dashboard'));
const ResourceManager = lazy(() => import('../tabs/ResourceManager'));
const TerrainAnalysis = lazy(() => import('../tabs/TerrainAnalysis'));
const HazardBuilder = lazy(() => import('../tabs/HazardBuilder'));
const MissionDesigner = lazy(() => import('../tabs/MissionDesigner'));
const CandidateLab = lazy(() => import('../tabs/CandidateLab'));
const TrainingCenter = lazy(() => import('../tabs/TrainingCenter'));
const Evaluation = lazy(() => import('../tabs/Evaluation'));
const SimulationPlayer = lazy(() => import('../tabs/SimulationPlayer'));
const ExperimentCompare = lazy(() => import('../tabs/ExperimentCompare'));
const Reports = lazy(() => import('../tabs/Reports'));
const SettingsTab = lazy(() => import('../tabs/Settings'));

const tabComponents: Record<TabId, React.LazyExoticComponent<() => React.JSX.Element>> = {
  dashboard: Dashboard,
  resources: ResourceManager,
  terrain: TerrainAnalysis,
  hazard: HazardBuilder,
  mission: MissionDesigner,
  candidate: CandidateLab,
  training: TrainingCenter,
  evaluation: Evaluation,
  simulation: SimulationPlayer,
  compare: ExperimentCompare,
  reports: Reports,
  settings: SettingsTab,
};

function LoadingFallback() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="w-6 h-6 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
    </div>
  );
}

export default function AppLayout() {
  const { currentTab } = useAppStore();
  const TabComponent = tabComponents[currentTab];

  return (
    <div className="flex h-screen w-screen bg-[#f5f5f7]">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-6">
          <Suspense fallback={<LoadingFallback />}>
            <TabComponent />
          </Suspense>
        </main>
        <BottomConsole />
      </div>
    </div>
  );
}
