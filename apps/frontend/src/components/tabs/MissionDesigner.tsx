import { useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import GlassCard from '../common/GlassCard';
import SectionTitle from '../common/SectionTitle';
import ParameterRow from '../common/ParameterRow';
import RunActionBar from '../common/RunActionBar';

interface PointXYZ {
  x: string;
  y: string;
  agl: string;
}

export default function MissionDesigner() {
  const [start, setStart] = useState<PointXYZ>({ x: '1000', y: '1000', agl: '30' });
  const [goal, setGoal] = useState<PointXYZ>({ x: '22000', y: '18000', agl: '40' });
  const [observe, setObserve] = useState({
    cx: '16000', cy: '9000', cz: '250',
    sx: '500', sy: '500', sz: '200',
    duration: '10',
  });
  const [safeHolds, setSafeHolds] = useState<PointXYZ[]>([{ x: '12000', y: '8000', agl: '25' }]);
  const [altLZs, setAltLZs] = useState<PointXYZ[]>([{ x: '5000', y: '22000', agl: '0' }]);
  const [timeLimit, setTimeLimit] = useState('1800');
  const [status, setStatus] = useState('idle');

  const missionJson = JSON.stringify(
    {
      mission_id: 'mission_hongik_001',
      terrain_id: 'Hongik_48km',
      max_episode_time_sec: Number(timeLimit),
      start: { x: +start.x, y: +start.y, agl_m: +start.agl },
      goal: { x: +goal.x, y: +goal.y, agl_m: +goal.agl },
      observe_box: {
        center_x: +observe.cx, center_y: +observe.cy, center_z: +observe.cz,
        size_x: +observe.sx, size_y: +observe.sy, size_z: +observe.sz,
        required_duration_sec: +observe.duration,
      },
      safe_hold_points: safeHolds.map((p) => ({ x: +p.x, y: +p.y, agl_m: +p.agl })),
      alternate_lz: altLZs.map((p) => ({ x: +p.x, y: +p.y, agl_m: +p.agl })),
    },
    null,
    2
  );

  const addPoint = (list: PointXYZ[], setter: (v: PointXYZ[]) => void) =>
    setter([...list, { x: '0', y: '0', agl: '0' }]);

  const removePoint = (list: PointXYZ[], setter: (v: PointXYZ[]) => void, idx: number) =>
    setter(list.filter((_, i) => i !== idx));

  const updatePoint = (list: PointXYZ[], setter: (v: PointXYZ[]) => void, idx: number, field: keyof PointXYZ, val: string) =>
    setter(list.map((p, i) => (i === idx ? { ...p, [field]: val } : p)));

  return (
    <div className="grid grid-cols-12 gap-6 h-full">
      {/* LEFT */}
      <div className="col-span-4 space-y-4 overflow-y-auto">
        <GlassCard>
          <SectionTitle title="Start Point" />
          <div className="grid grid-cols-3 gap-2">
            <ParameterRow label="X" value={start.x} onChange={(v) => setStart({ ...start, x: v })} type="number" unit="m" />
            <ParameterRow label="Y" value={start.y} onChange={(v) => setStart({ ...start, y: v })} type="number" unit="m" />
            <ParameterRow label="AGL" value={start.agl} onChange={(v) => setStart({ ...start, agl: v })} type="number" unit="m" />
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle title="Goal Point" />
          <div className="grid grid-cols-3 gap-2">
            <ParameterRow label="X" value={goal.x} onChange={(v) => setGoal({ ...goal, x: v })} type="number" unit="m" />
            <ParameterRow label="Y" value={goal.y} onChange={(v) => setGoal({ ...goal, y: v })} type="number" unit="m" />
            <ParameterRow label="AGL" value={goal.agl} onChange={(v) => setGoal({ ...goal, agl: v })} type="number" unit="m" />
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle title="Observe Box" />
          <div className="space-y-1">
            <div className="grid grid-cols-3 gap-2">
              <ParameterRow label="CX" value={observe.cx} onChange={(v) => setObserve({ ...observe, cx: v })} type="number" unit="m" />
              <ParameterRow label="CY" value={observe.cy} onChange={(v) => setObserve({ ...observe, cy: v })} type="number" unit="m" />
              <ParameterRow label="CZ" value={observe.cz} onChange={(v) => setObserve({ ...observe, cz: v })} type="number" unit="m" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <ParameterRow label="SX" value={observe.sx} onChange={(v) => setObserve({ ...observe, sx: v })} type="number" unit="m" />
              <ParameterRow label="SY" value={observe.sy} onChange={(v) => setObserve({ ...observe, sy: v })} type="number" unit="m" />
              <ParameterRow label="SZ" value={observe.sz} onChange={(v) => setObserve({ ...observe, sz: v })} type="number" unit="m" />
            </div>
            <ParameterRow label="Duration" value={observe.duration} onChange={(v) => setObserve({ ...observe, duration: v })} type="number" unit="sec" />
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle
            title="Safe Hold Points"
            actions={
              <button onClick={() => addPoint(safeHolds, setSafeHolds)} className="flex items-center gap-1 px-2 py-1 text-xs text-[#0071e3] bg-blue-50 rounded-lg hover:bg-blue-100">
                <Plus size={13} /> Add
              </button>
            }
          />
          {safeHolds.map((p, i) => (
            <div key={i} className="flex items-center gap-2 mb-2">
              <input type="number" value={p.x} onChange={(e) => updatePoint(safeHolds, setSafeHolds, i, 'x', e.target.value)} className="flex-1 px-2 py-1 text-sm bg-white/60 border border-gray-200/60 rounded-lg" placeholder="X" />
              <input type="number" value={p.y} onChange={(e) => updatePoint(safeHolds, setSafeHolds, i, 'y', e.target.value)} className="flex-1 px-2 py-1 text-sm bg-white/60 border border-gray-200/60 rounded-lg" placeholder="Y" />
              <input type="number" value={p.agl} onChange={(e) => updatePoint(safeHolds, setSafeHolds, i, 'agl', e.target.value)} className="flex-1 px-2 py-1 text-sm bg-white/60 border border-gray-200/60 rounded-lg" placeholder="AGL" />
              <button onClick={() => removePoint(safeHolds, setSafeHolds, i)} className="p-1 text-gray-400 hover:text-red-500"><Trash2 size={13} /></button>
            </div>
          ))}
        </GlassCard>

        <GlassCard>
          <SectionTitle
            title="Alternate LZ"
            actions={
              <button onClick={() => addPoint(altLZs, setAltLZs)} className="flex items-center gap-1 px-2 py-1 text-xs text-[#0071e3] bg-blue-50 rounded-lg hover:bg-blue-100">
                <Plus size={13} /> Add
              </button>
            }
          />
          {altLZs.map((p, i) => (
            <div key={i} className="flex items-center gap-2 mb-2">
              <input type="number" value={p.x} onChange={(e) => updatePoint(altLZs, setAltLZs, i, 'x', e.target.value)} className="flex-1 px-2 py-1 text-sm bg-white/60 border border-gray-200/60 rounded-lg" placeholder="X" />
              <input type="number" value={p.y} onChange={(e) => updatePoint(altLZs, setAltLZs, i, 'y', e.target.value)} className="flex-1 px-2 py-1 text-sm bg-white/60 border border-gray-200/60 rounded-lg" placeholder="Y" />
              <input type="number" value={p.agl} onChange={(e) => updatePoint(altLZs, setAltLZs, i, 'agl', e.target.value)} className="flex-1 px-2 py-1 text-sm bg-white/60 border border-gray-200/60 rounded-lg" placeholder="AGL" />
              <button onClick={() => removePoint(altLZs, setAltLZs, i)} className="p-1 text-gray-400 hover:text-red-500"><Trash2 size={13} /></button>
            </div>
          ))}
        </GlassCard>

        <GlassCard>
          <ParameterRow label="Time Limit" value={timeLimit} onChange={setTimeLimit} type="number" unit="sec" tooltip="Maximum episode time in seconds" defaultValue="1800" />
        </GlassCard>

        <RunActionBar
          status={status}
          onValidate={() => setStatus('ready')}
          onRun={() => { setStatus('running'); setTimeout(() => setStatus('completed'), 1000); }}
        />
      </div>

      {/* CENTER - Map */}
      <div className="col-span-5 overflow-y-auto">
        <GlassCard className="h-full">
          <SectionTitle title="Mission Map" description="Terrain outline with mission points" />
          <div className="relative w-full h-[500px] bg-gradient-to-br from-gray-100 to-gray-200 rounded-xl overflow-hidden">
            {/* Terrain background grid */}
            <svg className="w-full h-full" viewBox="0 0 500 500">
              {/* Grid */}
              {Array.from({ length: 11 }).map((_, i) => (
                <g key={i}>
                  <line x1={i * 50} y1={0} x2={i * 50} y2={500} stroke="#ddd" strokeWidth={0.5} />
                  <line x1={0} y1={i * 50} x2={500} y2={i * 50} stroke="#ddd" strokeWidth={0.5} />
                </g>
              ))}
              {/* Terrain boundary */}
              <rect x={20} y={20} width={460} height={460} fill="none" stroke="#ccc" strokeWidth={1} strokeDasharray="4,4" />
              {/* Start */}
              <circle cx={23} cy={477} r={8} fill="#34c759" stroke="white" strokeWidth={2} />
              <text x={35} y={481} fontSize={10} fill="#34c759" fontWeight="600">Start</text>
              {/* Goal */}
              <circle cx={477} cy={90} r={8} fill="#ff3b30" stroke="white" strokeWidth={2} />
              <text x={445} y={80} fontSize={10} fill="#ff3b30" fontWeight="600">Goal</text>
              {/* Observe box */}
              <rect x={300} y={200} width={60} height={60} fill="rgba(0,113,227,0.15)" stroke="#0071e3" strokeWidth={1.5} strokeDasharray="3,3" rx={4} />
              <text x={310} y={195} fontSize={9} fill="#0071e3">Observe</text>
              {/* Safe Hold */}
              <circle cx={250} cy={300} r={6} fill="#ff9f0a" stroke="white" strokeWidth={1.5} />
              <text x={260} y={304} fontSize={9} fill="#ff9f0a">Hold</text>
              {/* Alt LZ */}
              <polygon points="100,70 106,82 94,82" fill="#8b5cf6" stroke="white" strokeWidth={1} />
              <text x={110} y={80} fontSize={9} fill="#8b5cf6">Alt LZ</text>
              {/* Path hint */}
              <polyline
                points="23,477 100,400 200,350 250,300 320,230 477,90"
                fill="none"
                stroke="#0071e3"
                strokeWidth={1.5}
                strokeDasharray="5,5"
                opacity={0.5}
              />
            </svg>

            {/* Legend */}
            <div className="absolute bottom-3 left-3 bg-white/80 backdrop-blur-md rounded-lg px-3 py-2 text-[10px] space-y-1">
              <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-green-500" /> Start</div>
              <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-red-500" /> Goal</div>
              <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-[#0071e3]" /> Observe</div>
              <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-amber-500" /> Safe Hold</div>
              <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-purple-500" /> Alt LZ</div>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* RIGHT - JSON Preview */}
      <div className="col-span-3 overflow-y-auto">
        <GlassCard className="h-full">
          <SectionTitle title="Mission JSON" />
          <pre className="text-xs text-gray-700 bg-gray-50/60 rounded-xl p-3 overflow-auto max-h-[600px] font-mono leading-5">
            {missionJson}
          </pre>
        </GlassCard>
      </div>
    </div>
  );
}
