import { useState } from 'react';
import { Award, Filter } from 'lucide-react';
import GlassCard from '../common/GlassCard';
import SectionTitle from '../common/SectionTitle';
import StatusBadge from '../common/StatusBadge';
import PlotCard from '../common/PlotCard';

interface RunEntry {
  id: string;
  stage: string;
  terrain: string;
  algorithm: string;
  success: number;
  reward: number;
  risk: number;
  pathLen: number;
  status: string;
  tags: string[];
}

const demoRuns: RunEntry[] = [
  { id: '04_train__Hongik__currA__a1b2', stage: 'training', terrain: 'Hongik_48km', algorithm: 'MaskablePPO', success: 0.71, reward: 89.3, risk: 0.18, pathLen: 24500, status: 'completed', tags: ['baseline'] },
  { id: '04_train__Hongik__currB__c3d4', stage: 'training', terrain: 'Hongik_48km', algorithm: 'MaskablePPO', success: 0.68, reward: 85.1, risk: 0.21, pathLen: 25100, status: 'completed', tags: ['curriculum_b'] },
  { id: '04_train__Inje__currA__e5f6', stage: 'training', terrain: 'Inje_48km', algorithm: 'MaskablePPO', success: 0.62, reward: 74.8, risk: 0.24, pathLen: 27300, status: 'completed', tags: [] },
  { id: '04_train__Jipo__currA__g7h8', stage: 'training', terrain: 'Jipo_48km', algorithm: 'PPO', success: 0.45, reward: 52.4, risk: 0.35, pathLen: 30200, status: 'completed', tags: [] },
  { id: '04_train__Hongik__currC__i9j0', stage: 'training', terrain: 'Hongik_48km', algorithm: 'MaskablePPO', success: 0.58, reward: 70.2, risk: 0.28, pathLen: 26800, status: 'running', tags: ['experimental'] },
];

export default function ExperimentCompare() {
  const [selected, setSelected] = useState<Set<string>>(new Set([demoRuns[0].id, demoRuns[1].id]));
  const [stageFilter, setStageFilter] = useState('all');
  const [terrainFilter, setTerrainFilter] = useState('all');
  const [sortBy, setSortBy] = useState<keyof RunEntry>('success');

  const toggleRun = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const filtered = demoRuns
    .filter((r) => stageFilter === 'all' || r.stage === stageFilter)
    .filter((r) => terrainFilter === 'all' || r.terrain === terrainFilter)
    .sort((a, b) => (b[sortBy] as number) - (a[sortBy] as number));

  const selectedRuns = demoRuns.filter((r) => selected.has(r.id));
  const bestRun = selectedRuns.length > 0
    ? selectedRuns.reduce((a, b) => (a.success > b.success ? a : b))
    : null;

  return (
    <div className="grid grid-cols-12 gap-6 h-full">
      {/* LEFT - Run list */}
      <div className="col-span-4 space-y-4 overflow-y-auto">
        <GlassCard padding="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Filter size={15} className="text-gray-400" />
            <span className="text-sm font-medium text-gray-700">Filters</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <select value={stageFilter} onChange={(e) => setStageFilter(e.target.value)} className="px-2 py-1.5 text-xs bg-white/60 border border-gray-200/60 rounded-lg">
              <option value="all">All Stages</option>
              <option value="training">Training</option>
              <option value="evaluation">Evaluation</option>
            </select>
            <select value={terrainFilter} onChange={(e) => setTerrainFilter(e.target.value)} className="px-2 py-1.5 text-xs bg-white/60 border border-gray-200/60 rounded-lg">
              <option value="all">All Terrains</option>
              <option value="Hongik_48km">Hongik</option>
              <option value="Inje_48km">Inje</option>
              <option value="Jipo_48km">Jipo</option>
            </select>
          </div>
          <div className="mt-2">
            <label className="text-xs text-gray-500">Sort by:</label>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as keyof RunEntry)} className="ml-2 px-2 py-1 text-xs bg-white/60 border border-gray-200/60 rounded-lg">
              <option value="success">Success Rate</option>
              <option value="risk">Risk</option>
              <option value="reward">Reward</option>
              <option value="pathLen">Path Length</option>
            </select>
          </div>
        </GlassCard>

        <GlassCard padding="p-3">
          <SectionTitle title="Runs" description={`${selected.size} selected`} />
          <div className="space-y-1.5">
            {filtered.map((r) => (
              <label
                key={r.id}
                className={`flex items-start gap-2 px-3 py-2.5 rounded-xl cursor-pointer border transition-colors ${
                  selected.has(r.id)
                    ? 'border-blue-300 bg-blue-50/50'
                    : 'border-gray-200/40 bg-white/30 hover:bg-gray-50/60'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selected.has(r.id)}
                  onChange={() => toggleRun(r.id)}
                  className="mt-1 rounded border-gray-300 text-blue-500"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-mono text-gray-700 truncate">{r.id}</div>
                  <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                    <span>{r.terrain}</span>
                    <span>·</span>
                    <span>{r.algorithm}</span>
                    <StatusBadge status={r.status} />
                  </div>
                  <div className="flex gap-3 mt-1 text-xs">
                    <span className="text-green-600">S: {(r.success * 100).toFixed(0)}%</span>
                    <span className="text-blue-600">R: {r.reward.toFixed(1)}</span>
                    <span className="text-red-500">Risk: {r.risk.toFixed(2)}</span>
                  </div>
                </div>
              </label>
            ))}
          </div>
        </GlassCard>
      </div>

      {/* CENTER - Comparison */}
      <div className="col-span-5 space-y-4 overflow-y-auto">
        {/* Comparison table */}
        <GlassCard>
          <SectionTitle title="Metrics Comparison" />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b border-gray-200/50">
                  <th className="pb-2 font-medium">Run</th>
                  <th className="pb-2 font-medium">Success</th>
                  <th className="pb-2 font-medium">Reward</th>
                  <th className="pb-2 font-medium">Risk</th>
                  <th className="pb-2 font-medium">Path Len</th>
                </tr>
              </thead>
              <tbody>
                {selectedRuns.map((r) => (
                  <tr key={r.id} className={`border-b border-gray-50 ${bestRun?.id === r.id ? 'bg-green-50/50' : ''}`}>
                    <td className="py-2 font-mono text-xs text-gray-700 truncate max-w-[120px]">{r.id.split('__').slice(0, 2).join('_')}</td>
                    <td className="py-2 font-medium">{(r.success * 100).toFixed(0)}%</td>
                    <td className="py-2">{r.reward.toFixed(1)}</td>
                    <td className="py-2">{r.risk.toFixed(2)}</td>
                    <td className="py-2">{r.pathLen.toLocaleString()}m</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>

        <PlotCard
          title="Performance Comparison"
          data={selectedRuns.map((r, i) => ({
            x: ['Success', 'Reward/100', 'Low Risk', 'Short Path'],
            y: [r.success, r.reward / 100, 1 - r.risk, 1 - r.pathLen / 35000],
            type: 'bar' as const,
            name: r.id.split('__')[1],
            marker: { color: ['#0071e3', '#34c759', '#ff9f0a', '#8b5cf6', '#ff3b30'][i % 5] },
          }))}
          layout={{
            barmode: 'group',
            yaxis: { title: { text: 'Score' }, range: [0, 1] },
            showlegend: true,
          }}
          height={280}
        />

        {/* Config diff */}
        <GlassCard>
          <SectionTitle title="Config Diff" description="Side-by-side parameter comparison" />
          {selectedRuns.length >= 2 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-200/50">
                    <th className="pb-2 font-medium font-sans">Parameter</th>
                    {selectedRuns.slice(0, 3).map((r) => (
                      <th key={r.id} className="pb-2 font-medium font-sans truncate max-w-[100px]">{r.id.split('__')[1]}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {['algorithm', 'terrain', 'success', 'reward', 'risk'].map((param) => (
                    <tr key={param} className="border-b border-gray-50">
                      <td className="py-1.5 text-gray-600 font-sans">{param}</td>
                      {selectedRuns.slice(0, 3).map((r) => (
                        <td key={r.id} className="py-1.5 text-gray-800">
                          {String(r[param as keyof RunEntry])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-gray-400 italic">Select at least 2 runs to compare configs</p>
          )}
        </GlassCard>
      </div>

      {/* RIGHT - Best run */}
      <div className="col-span-3 space-y-4 overflow-y-auto">
        {bestRun && (
          <GlassCard className="border-2 border-green-200">
            <div className="flex items-center gap-2 mb-3">
              <Award size={18} className="text-amber-500" />
              <SectionTitle title="Best Run" className="mb-0" />
            </div>
            <div className="space-y-2 text-sm">
              <div className="text-xs font-mono text-gray-600 truncate">{bestRun.id}</div>
              <div className="flex justify-between"><span className="text-gray-500">Terrain</span><span className="font-medium">{bestRun.terrain}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Algorithm</span><span className="font-medium">{bestRun.algorithm}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Success</span><span className="font-medium text-green-600">{(bestRun.success * 100).toFixed(0)}%</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Reward</span><span className="font-medium text-green-600">{bestRun.reward.toFixed(1)}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Risk</span><span className="font-medium">{bestRun.risk.toFixed(2)}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Path Length</span><span className="font-medium">{bestRun.pathLen.toLocaleString()}m</span></div>
              {bestRun.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {bestRun.tags.map((t) => (
                    <span key={t} className="px-2 py-0.5 text-xs bg-blue-50 text-blue-600 rounded-full">{t}</span>
                  ))}
                </div>
              )}
            </div>
          </GlassCard>
        )}

        <GlassCard>
          <SectionTitle title="Selection Summary" />
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-500">Selected Runs</span><span className="font-medium">{selected.size}</span></div>
            {selectedRuns.length > 0 && (
              <>
                <div className="flex justify-between"><span className="text-gray-500">Avg Success</span><span className="font-medium">{(selectedRuns.reduce((a, r) => a + r.success, 0) / selectedRuns.length * 100).toFixed(0)}%</span></div>
                <div className="flex justify-between"><span className="text-gray-500">Avg Reward</span><span className="font-medium">{(selectedRuns.reduce((a, r) => a + r.reward, 0) / selectedRuns.length).toFixed(1)}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">Terrains</span><span className="font-medium">{new Set(selectedRuns.map((r) => r.terrain)).size}</span></div>
              </>
            )}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
