import { useState } from 'react';
import { Plus, Trash2, Eye } from 'lucide-react';
import GlassCard from '../common/GlassCard';
import SectionTitle from '../common/SectionTitle';
import RunActionBar from '../common/RunActionBar';
import PlotCard from '../common/PlotCard';

interface HazardRow {
  id: string;
  name: string;
  type: string;
  x: number;
  y: number;
  radius: number;
  enabled: boolean;
}

const initialHazards: HazardRow[] = [
  { id: 'hz_001', name: 'sensitive_zone_a', type: 'visibility_sensitive_zone', x: 1000, y: 2000, radius: 2500, enabled: true },
  { id: 'hz_002', name: 'restricted_area_b', type: 'restricted_zone', x: 5000, y: 8000, radius: 1500, enabled: true },
  { id: 'hz_003', name: 'radar_site_c', type: 'radar', x: 12000, y: 4000, radius: 3000, enabled: false },
];

function generateRiskMap() {
  const size = 60;
  const z: number[][] = [];
  for (let i = 0; i < size; i++) {
    const row: number[] = [];
    for (let j = 0; j < size; j++) {
      const d1 = Math.sqrt((i - 15) ** 2 + (j - 30) ** 2);
      const d2 = Math.sqrt((i - 40) ** 2 + (j - 20) ** 2);
      row.push(
        Math.max(0, 1 - d1 / 20) * 0.8 +
        Math.max(0, 1 - d2 / 15) * 0.6 +
        Math.random() * 0.1
      );
    }
    z.push(row);
  }
  return z;
}

export default function HazardBuilder() {
  const [hazards, setHazards] = useState<HazardRow[]>(initialHazards);
  const [altBand, setAltBand] = useState('mid_transit');
  const [fusionMode, setFusionMode] = useState('probabilistic_union');
  const [status, setStatus] = useState('idle');

  const toggleHazard = (id: string) =>
    setHazards((h) => h.map((hz) => (hz.id === id ? { ...hz, enabled: !hz.enabled } : hz)));

  const removeHazard = (id: string) =>
    setHazards((h) => h.filter((hz) => hz.id !== id));

  const addHazard = () => {
    const next = hazards.length + 1;
    setHazards([
      ...hazards,
      { id: `hz_new_${next}`, name: `new_hazard_${next}`, type: 'generic', x: 0, y: 0, radius: 1000, enabled: true },
    ]);
  };

  const riskZ = generateRiskMap();
  const riskValues = riskZ.flat();

  return (
    <div className="grid grid-cols-12 gap-6 h-full">
      {/* LEFT */}
      <div className="col-span-3 space-y-4 overflow-y-auto">
        <GlassCard>
          <SectionTitle
            title="Hazard Sources"
            actions={
              <button
                onClick={addHazard}
                className="flex items-center gap-1 px-2 py-1 text-xs text-[#0071e3] bg-blue-50 rounded-lg hover:bg-blue-100"
              >
                <Plus size={13} /> Add
              </button>
            }
          />
          <div className="space-y-2">
            {hazards.map((hz) => (
              <div
                key={hz.id}
                className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border text-sm ${
                  hz.enabled ? 'border-gray-200/60 bg-white/40' : 'border-gray-100 bg-gray-50/40 opacity-50'
                }`}
              >
                <input
                  type="checkbox"
                  checked={hz.enabled}
                  onChange={() => toggleHazard(hz.id)}
                  className="rounded border-gray-300"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-gray-800 font-medium truncate">{hz.name}</div>
                  <div className="text-xs text-gray-400">{hz.type} · r={hz.radius}m</div>
                </div>
                <button
                  onClick={() => removeHazard(hz.id)}
                  className="p-1 text-gray-400 hover:text-red-500"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle title="Settings" />
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-500 font-medium">Altitude Band</label>
              <select
                value={altBand}
                onChange={(e) => setAltBand(e.target.value)}
                className="w-full mt-1 px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              >
                <option value="low_masked">Low Masked (20m AGL)</option>
                <option value="mid_transit">Mid Transit (80m AGL)</option>
                <option value="high_observe">High Observe (180m AGL)</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 font-medium">Fusion Mode</label>
              <select
                value={fusionMode}
                onChange={(e) => setFusionMode(e.target.value)}
                className="w-full mt-1 px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              >
                <option value="probabilistic_union">Probabilistic Union</option>
                <option value="sum_clip">Sum Clip</option>
                <option value="max">Max</option>
              </select>
            </div>
          </div>
        </GlassCard>

        <RunActionBar
          status={status}
          onValidate={() => setStatus('ready')}
          onRun={() => { setStatus('running'); setTimeout(() => setStatus('completed'), 1500); }}
          onStop={() => setStatus('stopped')}
        />
      </div>

      {/* CENTER */}
      <div className="col-span-6 space-y-4 overflow-y-auto">
        <PlotCard
          title={`Fused Risk Map — ${altBand}`}
          data={[
            {
              z: riskZ,
              type: 'heatmap',
              colorscale: 'YlOrRd',
              colorbar: { title: { text: 'Risk' }, thickness: 15, len: 0.8 },
            },
          ]}
          layout={{
            xaxis: { title: { text: 'X (cells)' } },
            yaxis: { title: { text: 'Y (cells)' } },
          }}
          height={450}
        />
      </div>

      {/* RIGHT */}
      <div className="col-span-3 space-y-4 overflow-y-auto">
        <PlotCard
          title="Risk Distribution"
          data={[
            {
              x: riskValues,
              type: 'histogram',
              marker: { color: 'rgba(255, 59, 48, 0.5)' },
              nbinsx: 40,
            } as never,
          ]}
          height={200}
        />

        <GlassCard>
          <SectionTitle title="Statistics" />
          <div className="space-y-2 text-sm">
            {[
              { label: 'Min Risk', value: '0.00' },
              { label: 'Max Risk', value: '0.94' },
              { label: 'Mean Risk', value: '0.18' },
              { label: 'High Risk Cells', value: '12.3%' },
              { label: 'Active Sources', value: String(hazards.filter((h) => h.enabled).length) },
            ].map((s) => (
              <div key={s.label} className="flex justify-between">
                <span className="text-gray-500">{s.label}</span>
                <span className="font-medium text-gray-800">{s.value}</span>
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle title="Cell Risk Decomposition" description="Click on the map to inspect" />
          <div className="flex items-center justify-center py-8">
            <Eye size={24} className="text-gray-300" />
          </div>
          <p className="text-xs text-gray-400 text-center">
            Click any cell on the risk map to see per-source risk breakdown
          </p>
        </GlassCard>
      </div>
    </div>
  );
}
