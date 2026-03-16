import { useState } from 'react';
import GlassCard from '../common/GlassCard';
import SectionTitle from '../common/SectionTitle';
import RunActionBar from '../common/RunActionBar';
import PlotCard from '../common/PlotCard';

const baselines = ['RL (Ours)', 'Random', 'A*', 'FSM'];
const terrainSplits = ['Hongik_48km', 'Inje_48km', 'Jipo_48km'];
const scenarios = ['standard', 'high_risk', 'long_range', 'multi_observe'];

const metrics = {
  'RL (Ours)': { success: 0.71, reward: 89.3, risk: 0.18, pathLen: 24500, epLen: 320 },
  Random: { success: 0.08, reward: -42.1, risk: 0.52, pathLen: 31000, epLen: 500 },
  'A*': { success: 0.55, reward: 52.0, risk: 0.25, pathLen: 22000, epLen: 280 },
  FSM: { success: 0.42, reward: 38.5, risk: 0.31, pathLen: 26000, epLen: 350 },
};

export default function Evaluation() {
  const [selectedRun, setSelectedRun] = useState('04_training__Hongik_48km__20260314_231500__a1b2c3');
  const [checkpoint, setCheckpoint] = useState('best_model.zip');
  const [checkedBaselines, setCheckedBaselines] = useState<Record<string, boolean>>(
    Object.fromEntries(baselines.map((b) => [b, true]))
  );
  const [terrainSplit, setTerrainSplit] = useState('all');
  const [scenario, setScenario] = useState('standard');
  const [status, setStatus] = useState('idle');

  const toggleBaseline = (b: string) =>
    setCheckedBaselines((prev) => ({ ...prev, [b]: !prev[b] }));

  const activeBaselines = baselines.filter((b) => checkedBaselines[b]);

  return (
    <div className="grid grid-cols-12 gap-6 h-full">
      {/* LEFT */}
      <div className="col-span-3 space-y-4 overflow-y-auto">
        <GlassCard>
          <SectionTitle title="Configuration" />
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-500 font-medium">Run</label>
              <select
                value={selectedRun}
                onChange={(e) => setSelectedRun(e.target.value)}
                className="w-full mt-1 px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              >
                <option value="04_training__Hongik_48km__20260314_231500__a1b2c3">Training Run (Hongik)</option>
                <option value="04_training__Inje_48km__20260315_100000__xyz">Training Run (Inje)</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 font-medium">Checkpoint</label>
              <select
                value={checkpoint}
                onChange={(e) => setCheckpoint(e.target.value)}
                className="w-full mt-1 px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              >
                <option value="best_model.zip">best_model.zip (Step 280K)</option>
                <option value="checkpoint_300000.zip">checkpoint_300000.zip</option>
                <option value="checkpoint_200000.zip">checkpoint_200000.zip</option>
              </select>
            </div>
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle title="Baselines" />
          <div className="space-y-1.5">
            {baselines.map((b) => (
              <label key={b} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-100/60 cursor-pointer text-sm">
                <input type="checkbox" checked={checkedBaselines[b]} onChange={() => toggleBaseline(b)} className="rounded border-gray-300 text-blue-500" />
                <span className="text-gray-700">{b}</span>
              </label>
            ))}
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle title="Filters" />
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-500 font-medium">Terrain Split</label>
              <select value={terrainSplit} onChange={(e) => setTerrainSplit(e.target.value)} className="w-full mt-1 px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                <option value="all">All Terrains</option>
                {terrainSplits.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 font-medium">Scenario</label>
              <select value={scenario} onChange={(e) => setScenario(e.target.value)} className="w-full mt-1 px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                {scenarios.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
        </GlassCard>

        <RunActionBar
          status={status}
          onRun={() => { setStatus('running'); setTimeout(() => setStatus('completed'), 2000); }}
          onStop={() => setStatus('stopped')}
        />
      </div>

      {/* CENTER */}
      <div className="col-span-6 space-y-4 overflow-y-auto">
        <PlotCard
          title="Success Rate Comparison"
          data={[
            {
              x: activeBaselines,
              y: activeBaselines.map((b) => metrics[b as keyof typeof metrics].success * 100),
              type: 'bar',
              marker: {
                color: activeBaselines.map((b) =>
                  b === 'RL (Ours)' ? '#0071e3' : '#d1d5db'
                ),
              },
            },
          ]}
          layout={{ yaxis: { title: { text: 'Success Rate (%)' }, range: [0, 100] } }}
          height={250}
        />

        <div className="grid grid-cols-2 gap-4">
          <PlotCard
            title="Integrated Risk"
            data={[
              {
                y: activeBaselines.map((b) => {
                  const base = metrics[b as keyof typeof metrics].risk;
                  return Array.from({ length: 20 }, () => base + (Math.random() - 0.5) * 0.15);
                }),
                x: activeBaselines.map((b) => Array.from({ length: 20 }, () => b)),
                type: 'box',
                marker: { color: '#ff9f0a' },
              },
            ]}
            layout={{ yaxis: { title: { text: 'Risk' } } }}
            height={220}
          />

          <PlotCard
            title="Path Length"
            data={[
              {
                x: activeBaselines,
                y: activeBaselines.map((b) => metrics[b as keyof typeof metrics].pathLen),
                type: 'bar',
                marker: { color: 'rgba(139, 92, 246, 0.6)' },
              },
            ]}
            layout={{ yaxis: { title: { text: 'Length (m)' } } }}
            height={220}
          />
        </div>
      </div>

      {/* RIGHT */}
      <div className="col-span-3 space-y-4 overflow-y-auto">
        <GlassCard>
          <SectionTitle title="Metrics Summary" />
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-200/50">
                  <th className="pb-2 font-medium">Agent</th>
                  <th className="pb-2 font-medium">Succ</th>
                  <th className="pb-2 font-medium">Risk</th>
                  <th className="pb-2 font-medium">Reward</th>
                </tr>
              </thead>
              <tbody>
                {activeBaselines.map((b) => {
                  const m = metrics[b as keyof typeof metrics];
                  const isOurs = b === 'RL (Ours)';
                  return (
                    <tr key={b} className={`border-b border-gray-50 ${isOurs ? 'bg-blue-50/50' : ''}`}>
                      <td className="py-1.5 font-medium text-gray-700">{b}</td>
                      <td className="py-1.5">{(m.success * 100).toFixed(0)}%</td>
                      <td className="py-1.5">{m.risk.toFixed(2)}</td>
                      <td className="py-1.5">{m.reward.toFixed(1)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle title="Terrain Split Heatmap" />
          <PlotCard
            title=""
            data={[
              {
                z: [
                  [0.71, 0.08, 0.55, 0.42],
                  [0.65, 0.06, 0.48, 0.38],
                  [0.58, 0.10, 0.52, 0.40],
                ],
                x: baselines,
                y: terrainSplits,
                type: 'heatmap',
                colorscale: 'Greens',
                colorbar: { title: { text: 'Success' }, thickness: 12 },
              },
            ]}
            height={200}
          />
        </GlassCard>
      </div>
    </div>
  );
}
