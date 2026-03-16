import { Cpu, FolderPlus, Play, Zap, Clock, CheckCircle2, Mountain } from 'lucide-react';
import GlassCard from '../common/GlassCard';
import StatusBadge from '../common/StatusBadge';
import { useAppStore } from '../../stores/appStore';

const pipelineStages = [
  { id: 1, name: 'Preprocess', status: 'completed' },
  { id: 2, name: 'Hazard Build', status: 'completed' },
  { id: 3, name: 'Mission Setup', status: 'completed' },
  { id: 4, name: 'Training', status: 'running' },
  { id: 5, name: 'Evaluation', status: 'idle' },
  { id: 6, name: 'Simulation', status: 'idle' },
];

const recentRuns = [
  { run_id: '01_preprocess__Hongik_48km__20260314_220101__ab12cd', stage: 'Preprocess', status: 'completed', terrain: 'Hongik_48km', time: '22:01' },
  { run_id: '02_hazard__Hongik_48km__20260314_223000__cd34ef', stage: 'Hazard Build', status: 'completed', terrain: 'Hongik_48km', time: '22:30' },
  { run_id: '04_training__Hongik_48km__20260314_231500__a1b2c3', stage: 'Training', status: 'running', terrain: 'Hongik_48km', time: '23:15' },
];

const quickActions = [
  { label: 'New Project', icon: FolderPlus, color: 'bg-blue-50 text-blue-600' },
  { label: 'Run Preprocess', icon: Play, color: 'bg-green-50 text-green-600' },
  { label: 'Start Training', icon: Zap, color: 'bg-purple-50 text-purple-600' },
];

export default function Dashboard() {
  const { currentProject, cudaInfo, setCurrentTab } = useAppStore();

  return (
    <div className="space-y-6">
      {/* Welcome + Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <GlassCard className="lg:col-span-2">
          <h2 className="text-xl font-semibold text-gray-900 mb-1">
            Welcome to LAH Studio
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Terrain-based 3D sparse waypoint path planning research platform
          </p>
          <div className="flex items-center gap-3 text-sm text-gray-600">
            <span className="flex items-center gap-1.5">
              <Mountain size={15} className="text-blue-500" />
              Project: <strong>{currentProject?.name ?? 'None'}</strong>
            </span>
            <span className="text-gray-300">|</span>
            <span className="flex items-center gap-1.5">
              <Clock size={15} className="text-gray-400" />
              {new Date().toLocaleDateString()}
            </span>
          </div>
        </GlassCard>

        <GlassCard>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Quick Actions</h3>
          <div className="space-y-2">
            {quickActions.map((a) => (
              <button
                key={a.label}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium ${a.color} hover:opacity-80 transition-opacity`}
              >
                <a.icon size={16} />
                {a.label}
              </button>
            ))}
          </div>
        </GlassCard>
      </div>

      {/* CUDA Status + Pipeline */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <GlassCard>
          <div className="flex items-center gap-2 mb-4">
            <Cpu size={18} className="text-blue-500" />
            <h3 className="text-sm font-semibold text-gray-700">CUDA Status</h3>
          </div>
          {cudaInfo?.available ? (
            <div className="space-y-3">
              {cudaInfo.devices.map((d) => (
                <div key={d.index}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium text-gray-800">{d.name}</span>
                    <span className="text-gray-500">{d.torch_name}</span>
                  </div>
                  <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-green-400 to-green-500 rounded-full"
                      style={{ width: `${((d.total_memory_mb - d.free_memory_mb) / d.total_memory_mb) * 100}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>{((d.total_memory_mb - d.free_memory_mb) / 1024).toFixed(1)} GB used</span>
                    <span>{(d.total_memory_mb / 1024).toFixed(1)} GB total</span>
                  </div>
                </div>
              ))}
              <div className="text-xs text-gray-400 mt-2">
                CUDA {cudaInfo.cuda_version} · PyTorch {cudaInfo.torch_version}
              </div>
            </div>
          ) : (
            <div className="text-center py-6">
              <Cpu size={32} className="mx-auto text-gray-300 mb-2" />
              <p className="text-sm text-gray-500">No CUDA device detected</p>
              <p className="text-xs text-gray-400 mt-1">Running on CPU mode</p>
            </div>
          )}
        </GlassCard>

        <GlassCard className="lg:col-span-2">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Pipeline Progress</h3>
          <div className="flex items-center gap-2">
            {pipelineStages.map((stage, i) => (
              <div key={stage.id} className="flex items-center gap-2 flex-1">
                <div className="flex flex-col items-center flex-1">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold ${
                      stage.status === 'completed'
                        ? 'bg-green-100 text-green-700'
                        : stage.status === 'running'
                        ? 'bg-amber-100 text-amber-700 animate-pulse'
                        : 'bg-gray-100 text-gray-400'
                    }`}
                  >
                    {stage.status === 'completed' ? <CheckCircle2 size={16} /> : stage.id}
                  </div>
                  <span className="text-[10px] text-gray-500 mt-1 text-center leading-tight">
                    {stage.name}
                  </span>
                </div>
                {i < pipelineStages.length - 1 && (
                  <div
                    className={`h-0.5 flex-1 rounded-full mt-[-14px] ${
                      stage.status === 'completed' ? 'bg-green-300' : 'bg-gray-200'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      {/* Recent Runs */}
      <GlassCard>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-700">Recent Runs</h3>
          <button
            onClick={() => setCurrentTab('compare')}
            className="text-xs text-[#0071e3] hover:underline"
          >
            View all →
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-gray-200/50">
                <th className="pb-2 font-medium">Run ID</th>
                <th className="pb-2 font-medium">Stage</th>
                <th className="pb-2 font-medium">Terrain</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Time</th>
              </tr>
            </thead>
            <tbody>
              {recentRuns.map((run) => (
                <tr key={run.run_id} className="border-b border-gray-100 last:border-0">
                  <td className="py-2.5 text-gray-700 font-mono text-xs truncate max-w-[200px]">{run.run_id}</td>
                  <td className="py-2.5 text-gray-600">{run.stage}</td>
                  <td className="py-2.5 text-gray-600">{run.terrain}</td>
                  <td className="py-2.5"><StatusBadge status={run.status} /></td>
                  <td className="py-2.5 text-gray-500">{run.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* Recent Projects */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Projects</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {['Default Project', 'Hongik Analysis', 'Inje Comparison'].map((name, i) => (
            <GlassCard key={name} className="cursor-pointer hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-2">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-100 to-indigo-100 flex items-center justify-center">
                  <Mountain size={18} className="text-blue-600" />
                </div>
                <span className="text-[10px] text-gray-400">
                  {i === 0 ? 'Active' : i === 1 ? '2 days ago' : '1 week ago'}
                </span>
              </div>
              <h4 className="text-sm font-semibold text-gray-800">{name}</h4>
              <p className="text-xs text-gray-500 mt-1">
                {i === 0 ? '3 terrains · 5 runs' : i === 1 ? '1 terrain · 2 runs' : '2 terrains · 1 run'}
              </p>
            </GlassCard>
          ))}
        </div>
      </div>
    </div>
  );
}
