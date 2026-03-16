import { useState } from 'react';
import GlassCard from '../common/GlassCard';
import SectionTitle from '../common/SectionTitle';
import ParameterRow from '../common/ParameterRow';
import RunActionBar from '../common/RunActionBar';
import PlotCard from '../common/PlotCard';
import ArtifactList from '../common/ArtifactList';

const derivatives = [
  'slope', 'aspect', 'roughness', 'curvature', 'tpi',
  'openness', 'local_relief', 'ridge_valley_index', 'clearance_cost_base',
];

const derivativeTabs = ['Elevation', 'Slope', 'Roughness', 'Curvature', 'TPI', 'Aspect'];

function generateHeatmapData(name: string) {
  const size = 50;
  const z: number[][] = [];
  for (let i = 0; i < size; i++) {
    const row: number[] = [];
    for (let j = 0; j < size; j++) {
      row.push(
        Math.sin(i * 0.15 + (name.length * 0.3)) * Math.cos(j * 0.12) * 500 +
        Math.random() * 100 + 200
      );
    }
    z.push(row);
  }
  return z;
}

function generateHistogramData(name: string) {
  const vals: number[] = [];
  const offset = name.length * 10;
  for (let i = 0; i < 500; i++) {
    vals.push(Math.random() * 200 + offset + (Math.random() - 0.5) * 100);
  }
  return vals;
}

const demoArtifacts = [
  { name: 'elevation.tif', path: '/out/elevation.tif', type: 'tif', size_mb: 9.8 },
  { name: 'slope.tif', path: '/out/slope.tif', type: 'tif', size_mb: 9.8 },
  { name: 'roughness.tif', path: '/out/roughness.tif', type: 'tif', size_mb: 9.8 },
  { name: 'elevation_preview.png', path: '/out/elevation_preview.png', type: 'png', size_mb: 0.3 },
  { name: 'slope_preview.png', path: '/out/slope_preview.png', type: 'png', size_mb: 0.2 },
];

export default function TerrainAnalysis() {
  const [terrain, setTerrain] = useState('Hongik_48km');
  const [resolution, setResolution] = useState('30');
  const [checkedDerivs, setCheckedDerivs] = useState<Record<string, boolean>>(
    Object.fromEntries(derivatives.map((d) => [d, true]))
  );
  const [activePreview, setActivePreview] = useState('Elevation');
  const [status, setStatus] = useState('idle');

  const toggleDeriv = (d: string) =>
    setCheckedDerivs((prev) => ({ ...prev, [d]: !prev[d] }));

  const handleRun = () => {
    setStatus('running');
    setTimeout(() => setStatus('completed'), 2000);
  };

  const heatmapZ = generateHeatmapData(activePreview);
  const histData = generateHistogramData(activePreview);

  return (
    <div className="grid grid-cols-12 gap-6 h-full">
      {/* LEFT PANEL */}
      <div className="col-span-3 space-y-4 overflow-y-auto">
        <GlassCard>
          <SectionTitle title="Configuration" />
          <div className="space-y-2">
            <div className="space-y-1">
              <label className="text-xs text-gray-500 font-medium">Terrain File</label>
              <select
                value={terrain}
                onChange={(e) => setTerrain(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              >
                <option value="Hongik_48km">Hongik_48km.tif</option>
                <option value="Inje_48km">Inje_48km.tif</option>
                <option value="Jipo_48km">Jipo_48km.tif</option>
              </select>
            </div>
            <ParameterRow
              label="Resolution"
              value={resolution}
              onChange={setResolution}
              type="number"
              unit="m"
              tooltip="Target spatial resolution for analysis. Smaller values give more detail but slower processing."
              defaultValue="30"
              min={5}
              max={200}
              step={5}
            />
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle title="Derivatives" description="Select maps to generate" />
          <div className="space-y-1.5">
            {derivatives.map((d) => (
              <label
                key={d}
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-100/60 cursor-pointer text-sm"
              >
                <input
                  type="checkbox"
                  checked={checkedDerivs[d]}
                  onChange={() => toggleDeriv(d)}
                  className="rounded border-gray-300 text-blue-500 focus:ring-blue-500"
                />
                <span className="text-gray-700">{d.replace(/_/g, ' ')}</span>
              </label>
            ))}
          </div>
        </GlassCard>

        <RunActionBar
          status={status}
          onValidate={() => setStatus('ready')}
          onRun={handleRun}
          onStop={() => setStatus('stopped')}
        />
      </div>

      {/* CENTER */}
      <div className="col-span-6 space-y-4 overflow-y-auto">
        <GlassCard padding="p-4">
          <div className="flex items-center gap-1 mb-3 overflow-x-auto">
            {derivativeTabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setActivePreview(tab)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg whitespace-nowrap transition-colors ${
                  activePreview === tab
                    ? 'bg-[#0071e3] text-white'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
          <PlotCard
            title={`${activePreview} Map — ${terrain}`}
            data={[
              {
                z: heatmapZ,
                type: 'heatmap',
                colorscale: activePreview === 'Elevation' ? 'Earth' : activePreview === 'Slope' ? 'YlOrRd' : 'Viridis',
                colorbar: { thickness: 15, len: 0.8 },
              },
            ]}
            layout={{ xaxis: { title: { text: 'X (cells)' } }, yaxis: { title: { text: 'Y (cells)' } } }}
            height={400}
          />
        </GlassCard>
      </div>

      {/* RIGHT PANEL */}
      <div className="col-span-3 space-y-4 overflow-y-auto">
        <GlassCard>
          <SectionTitle title="Statistics" description={activePreview} />
          <div className="space-y-3">
            {[
              { label: 'Min', value: '12.3', unit: 'm' },
              { label: 'Max', value: '847.6', unit: 'm' },
              { label: 'Mean', value: '324.1', unit: 'm' },
              { label: 'Std Dev', value: '142.8', unit: 'm' },
            ].map((s) => (
              <div key={s.label} className="flex justify-between items-center text-sm">
                <span className="text-gray-500">{s.label}</span>
                <span className="font-medium text-gray-800">
                  {s.value} <span className="text-gray-400 text-xs">{s.unit}</span>
                </span>
              </div>
            ))}
          </div>
        </GlassCard>

        <PlotCard
          title="Distribution"
          data={[
            {
              x: histData,
              type: 'histogram',
              marker: { color: 'rgba(0, 113, 227, 0.5)' },
              nbinsx: 30,
            } as never,
          ]}
          height={200}
        />

        <GlassCard>
          <SectionTitle title="Generated Files" />
          <ArtifactList artifacts={demoArtifacts} />
        </GlassCard>
      </div>
    </div>
  );
}
