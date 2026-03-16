import { useState, useMemo } from 'react';
import GlassCard from '../common/GlassCard';
import SectionTitle from '../common/SectionTitle';
import ParameterRow from '../common/ParameterRow';
import RunActionBar from '../common/RunActionBar';
import PlotCard from '../common/PlotCard';
import { useT } from '../../i18n';

const primitiveTypes = [
  { name: 'transit', count: 16, desc: 'Straight-line movement between waypoints' },
  { name: 'hold', count: 4, desc: 'Stationary hovering at a waypoint' },
  { name: 'observe_setup', count: 4, desc: 'Positioning for observation' },
  { name: 'popup_observe', count: 3, desc: 'Pop-up maneuver for observation' },
  { name: 'egress', count: 3, desc: 'Exit from observation area' },
  { name: 'return', count: 1, desc: 'Return to base/LZ' },
  { name: 'divert', count: 1, desc: 'Divert to alternate LZ' },
];

function generateCandidates() {
  const candidates = [];
  for (let i = 0; i < 32; i++) {
    const angle = (i / 32) * Math.PI * 2;
    const dist = 500 + Math.random() * 2000;
    candidates.push({
      index: i,
      x: 12000 + Math.cos(angle) * dist,
      y: 9000 + Math.sin(angle) * dist,
      agl_m: 20 + Math.random() * 160,
      primitive: primitiveTypes[Math.floor(Math.random() * primitiveTypes.length)].name,
      distance_m: dist,
      risk: Math.random() * 0.8,
      clearance_m: 15 + Math.random() * 80,
      progress: Math.random(),
      visible_ratio: Math.random(),
      masked: Math.random() > 0.75,
    });
  }
  return candidates;
}

export default function CandidateLab() {
  const [maxCandidates, setMaxCandidates] = useState('32');
  const [distBands, setDistBands] = useState('500,1000,1500,2500');
  const [headingSamples, setHeadingSamples] = useState('-90,-60,-30,0,30,60,90');
  const [status, setStatus] = useState('idle');
  const [sortCol, setSortCol] = useState<string>('risk');
  const [sortAsc, setSortAsc] = useState(true);
  const t = useT();

  const candidates = useMemo(() => generateCandidates(), []);

  const sorted = useMemo(() => {
    const key = sortCol as keyof (typeof candidates)[0];
    return [...candidates].sort((a, b) => {
      const av = a[key] as number;
      const bv = b[key] as number;
      return sortAsc ? av - bv : bv - av;
    });
  }, [candidates, sortCol, sortAsc]);

  const handleSort = (col: string) => {
    if (sortCol === col) setSortAsc(!sortAsc);
    else { setSortCol(col); setSortAsc(true); }
  };

  return (
    <div className="grid grid-cols-12 gap-6 h-full">
      {/* LEFT */}
      <div className="col-span-3 space-y-4 overflow-y-auto">
        <GlassCard>
          <SectionTitle title={t('candidate.primitives')} />
          <div className="space-y-1.5">
            {primitiveTypes.map((p) => (
              <div key={p.name} className="flex items-center justify-between px-3 py-2 bg-gray-50/60 rounded-lg text-sm">
                <div>
                  <span className="font-medium text-gray-800">{p.name}</span>
                  <div className="text-xs text-gray-400">{p.desc}</div>
                </div>
                <span className="text-xs text-gray-500 font-mono">×{p.count}</span>
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle title={t('candidate.generationConfig')} />
          <ParameterRow label={t('candidate.maxCandidates')} value={maxCandidates} onChange={setMaxCandidates} type="number" tooltip="Maximum number of candidate waypoints per decision step. 16-64 recommended." defaultValue="32" />
          <ParameterRow label={t('candidate.distanceBands')} value={distBands} onChange={setDistBands} unit="m" tooltip="Comma-separated distance bands in meters" />
          <ParameterRow label={t('candidate.headingSamples')} value={headingSamples} onChange={setHeadingSamples} unit="°" tooltip="Comma-separated heading offsets in degrees" />
        </GlassCard>

        <RunActionBar
          status={status}
          onValidate={() => setStatus('ready')}
          onRun={() => { setStatus('running'); setTimeout(() => setStatus('completed'), 1500); }}
          onStop={() => setStatus('stopped')}
        />
      </div>

      {/* CENTER - Candidate Map */}
      <div className="col-span-5 space-y-4 overflow-y-auto">
        <PlotCard
          title={t('candidate.waypointsOnTerrain')}
          data={[
            {
              x: candidates.filter((c) => !c.masked).map((c) => c.x),
              y: candidates.filter((c) => !c.masked).map((c) => c.y),
              text: candidates.filter((c) => !c.masked).map((c) => `#${c.index} ${c.primitive}\nRisk: ${c.risk.toFixed(2)}`),
              mode: 'markers',
              type: 'scatter',
              marker: {
                size: 10,
                color: candidates.filter((c) => !c.masked).map((c) => c.risk),
                colorscale: 'YlOrRd',
                colorbar: { title: { text: 'Risk' }, thickness: 12 },
                line: { width: 1, color: 'white' },
              },
              name: 'Valid',
            },
            {
              x: candidates.filter((c) => c.masked).map((c) => c.x),
              y: candidates.filter((c) => c.masked).map((c) => c.y),
              mode: 'markers',
              type: 'scatter',
              marker: { size: 8, color: '#ccc', symbol: 'x' },
              name: 'Masked',
            },
          ]}
          layout={{
            xaxis: { title: { text: 'X (m)' } },
            yaxis: { title: { text: 'Y (m)' }, scaleanchor: 'x' },
            showlegend: true,
            legend: { x: 0, y: 1, bgcolor: 'rgba(255,255,255,0.7)' },
          }}
          height={400}
        />

        <PlotCard
          title={t('candidate.rewardBreakdown')}
          data={[
            {
              x: ['Progress', 'Risk', 'Clearance', 'Visibility', 'Distance'],
              y: [2.0, -1.5, 0.8, 1.2, -0.3],
              type: 'bar',
              marker: {
                color: [2.0, -1.5, 0.8, 1.2, -0.3].map((v) => v >= 0 ? 'rgba(52, 199, 89, 0.6)' : 'rgba(255, 59, 48, 0.6)'),
              },
            },
          ]}
          height={200}
        />
      </div>

      {/* RIGHT - Feature Table */}
      <div className="col-span-4 overflow-y-auto">
        <GlassCard padding="p-3">
          <SectionTitle title={t('candidate.features')} description={t('candidate.clickToSort')} />
          <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-white/90 backdrop-blur">
                <tr className="text-left text-gray-500 border-b border-gray-200/50">
                  {['index', 'primitive', 'risk', 'distance_m', 'clearance_m', 'progress', 'masked'].map((col) => (
                    <th
                      key={col}
                      className="pb-2 px-1.5 font-medium cursor-pointer hover:text-gray-800"
                      onClick={() => handleSort(col)}
                    >
                      {col.replace('_', ' ')}
                      {sortCol === col && (sortAsc ? ' ↑' : ' ↓')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((c) => (
                  <tr
                    key={c.index}
                    className={`border-b border-gray-50 ${c.masked ? 'opacity-40' : ''}`}
                  >
                    <td className="py-1.5 px-1.5 font-mono">{c.index}</td>
                    <td className="py-1.5 px-1.5 text-gray-700">{c.primitive}</td>
                    <td className="py-1.5 px-1.5">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        c.risk > 0.6 ? 'bg-red-50 text-red-600' : c.risk > 0.3 ? 'bg-amber-50 text-amber-600' : 'bg-green-50 text-green-600'
                      }`}>
                        {c.risk.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-1.5 px-1.5">{c.distance_m.toFixed(0)}</td>
                    <td className="py-1.5 px-1.5">{c.clearance_m.toFixed(1)}</td>
                    <td className="py-1.5 px-1.5">{c.progress.toFixed(2)}</td>
                    <td className="py-1.5 px-1.5">{c.masked ? '✕' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
