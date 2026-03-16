import { useState, useMemo } from 'react';
import { Play, Pause, SkipForward, Download, ChevronRight } from 'lucide-react';
import GlassCard from '../common/GlassCard';
import SectionTitle from '../common/SectionTitle';
import PlotCard from '../common/PlotCard';

function generateEpisode(n: number) {
  const steps = [];
  let x = 1000, y = 1000, z = 100, agl = 30;
  const modes = ['transit', 'transit', 'transit', 'hold', 'observe_setup', 'popup_observe', 'transit', 'egress', 'return'];
  for (let i = 0; i < n; i++) {
    const mode = modes[Math.min(Math.floor(i / (n / modes.length)), modes.length - 1)];
    x += (22000 - 1000) / n + (Math.random() - 0.5) * 500;
    y += (18000 - 1000) / n + (Math.random() - 0.5) * 500;
    agl = mode === 'popup_observe' ? 150 + Math.random() * 30 : mode === 'transit' ? 60 + Math.random() * 40 : 30 + Math.random() * 20;
    z = 200 + Math.sin(i * 0.1) * 50 + agl;
    steps.push({
      step: i,
      x: Math.round(x),
      y: Math.round(y),
      z: Math.round(z),
      agl_m: Math.round(agl),
      mode,
      primitive: mode,
      risk: Math.random() * 0.4,
      reward: Math.random() * 5 - 1,
      event: i === Math.floor(n * 0.6) ? 'Observation started' : i === Math.floor(n * 0.7) ? 'Observation complete' : undefined,
    });
  }
  return steps;
}

export default function SimulationPlayer() {
  const steps = useMemo(() => generateEpisode(80), []);
  const [currentStep, setCurrentStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  const current = steps[currentStep];
  const pathX = steps.slice(0, currentStep + 1).map((s) => s.x);
  const pathY = steps.slice(0, currentStep + 1).map((s) => s.y);

  return (
    <div className="space-y-4">
      {/* TOP - Controls */}
      <GlassCard padding="p-4">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <select className="px-3 py-1.5 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30">
              <option>Run: 04_training__Hongik_48km__a1b2c3</option>
            </select>
            <select className="px-3 py-1.5 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30">
              <option>Episode: ep_001 (Success)</option>
              <option>Episode: ep_002 (Failed)</option>
            </select>
          </div>

          <div className="flex-1" />

          {/* Playback */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPlaying(!playing)}
              className="p-2 text-white bg-[#0071e3] rounded-xl hover:bg-[#0077ED]"
            >
              {playing ? <Pause size={16} /> : <Play size={16} />}
            </button>
            <button
              onClick={() => setCurrentStep(Math.min(currentStep + 1, steps.length - 1))}
              className="p-2 text-gray-600 bg-gray-100 rounded-xl hover:bg-gray-200"
            >
              <SkipForward size={16} />
            </button>

            {[1, 2, 4, 8].map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`px-2 py-1 text-xs font-medium rounded-lg ${
                  speed === s ? 'bg-[#0071e3] text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                ×{s}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <button className="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200">
              <Download size={13} /> PNG
            </button>
            <button className="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200">
              <Download size={13} /> CSV
            </button>
          </div>
        </div>

        {/* Time scrubber */}
        <div className="mt-3">
          <input
            type="range"
            min={0}
            max={steps.length - 1}
            value={currentStep}
            onChange={(e) => setCurrentStep(Number(e.target.value))}
            className="w-full h-1.5 bg-gray-200 rounded-full appearance-none cursor-pointer accent-[#0071e3]"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>Step 0</span>
            <span>Step {currentStep} / {steps.length - 1}</span>
            <span>Step {steps.length - 1}</span>
          </div>
        </div>
      </GlassCard>

      {/* CENTER */}
      <div className="grid grid-cols-12 gap-4">
        {/* Map */}
        <div className="col-span-7">
          <PlotCard
            title="Top-Down Path View"
            data={[
              {
                x: steps.map((s) => s.x),
                y: steps.map((s) => s.y),
                mode: 'lines',
                type: 'scatter',
                line: { color: '#d1d5db', width: 1, dash: 'dot' },
                name: 'Full Path',
                showlegend: false,
              },
              {
                x: pathX,
                y: pathY,
                mode: 'lines',
                type: 'scatter',
                line: { color: '#0071e3', width: 2 },
                name: 'Traveled',
              },
              {
                x: [current.x],
                y: [current.y],
                mode: 'markers',
                type: 'scatter',
                marker: { size: 12, color: '#0071e3', symbol: 'diamond', line: { width: 2, color: 'white' } },
                name: 'Current',
              },
              {
                x: [steps[0].x],
                y: [steps[0].y],
                mode: 'text+markers' as const,
                type: 'scatter',
                marker: { size: 10, color: '#34c759' },
                text: ['Start'],
                textposition: 'top right',
                name: 'Start',
              },
              {
                x: [steps[steps.length - 1].x],
                y: [steps[steps.length - 1].y],
                mode: 'text+markers' as const,
                type: 'scatter',
                marker: { size: 10, color: '#ff3b30' },
                text: ['Goal'],
                textposition: 'top right',
                name: 'Goal',
              },
            ]}
            layout={{
              xaxis: { title: { text: 'X (m)' } },
              yaxis: { title: { text: 'Y (m)' }, scaleanchor: 'x' },
              showlegend: true,
              legend: { x: 0, y: 1, bgcolor: 'rgba(255,255,255,0.7)', font: { size: 10 } },
            }}
            height={380}
          />
        </div>

        {/* Altitude profile */}
        <div className="col-span-5">
          <PlotCard
            title="Altitude Profile"
            data={[
              {
                x: steps.map((s) => s.step),
                y: steps.map((s) => s.z),
                type: 'scatter',
                mode: 'lines',
                line: { color: '#8b5cf6', width: 2 },
                fill: 'tozeroy',
                fillcolor: 'rgba(139,92,246,0.08)',
                name: 'Altitude (ASL)',
              },
              {
                x: steps.map((s) => s.step),
                y: steps.map((s) => s.z - s.agl_m),
                type: 'scatter',
                mode: 'lines',
                line: { color: '#78716c', width: 1 },
                name: 'Ground',
              },
              {
                x: [currentStep],
                y: [current.z],
                mode: 'markers',
                type: 'scatter',
                marker: { size: 10, color: '#8b5cf6', symbol: 'diamond' },
                name: 'Now',
                showlegend: false,
              },
            ]}
            layout={{
              xaxis: { title: { text: 'Step' } },
              yaxis: { title: { text: 'Altitude (m)' } },
              showlegend: true,
              legend: { x: 0, y: 1, bgcolor: 'rgba(255,255,255,0.7)', font: { size: 10 } },
            }}
            height={380}
          />
        </div>
      </div>

      {/* BOTTOM */}
      <div className="grid grid-cols-12 gap-4">
        {/* Events */}
        <div className="col-span-7">
          <GlassCard padding="p-4">
            <SectionTitle title="Event Timeline" />
            <div className="flex gap-2 overflow-x-auto pb-2">
              {steps.filter((s) => s.event).map((s) => (
                <button
                  key={s.step}
                  onClick={() => setCurrentStep(s.step)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-amber-50 text-amber-700 rounded-lg whitespace-nowrap hover:bg-amber-100"
                >
                  <ChevronRight size={12} />
                  Step {s.step}: {s.event}
                </button>
              ))}
              {steps.filter((s) => s.event).length === 0 && (
                <span className="text-xs text-gray-400 italic">No events in this episode</span>
              )}
            </div>
          </GlassCard>
        </div>

        {/* Current state */}
        <div className="col-span-5">
          <GlassCard padding="p-4">
            <SectionTitle title="Current State" />
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">Position</span><span className="font-mono text-xs">{current.x}, {current.y}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Altitude</span><span className="font-mono text-xs">{current.z}m ({current.agl_m}m AGL)</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Mode</span><span className="font-medium">{current.mode}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Primitive</span><span className="font-medium">{current.primitive}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Risk</span><span className={`font-medium ${current.risk > 0.3 ? 'text-red-500' : 'text-green-600'}`}>{current.risk.toFixed(3)}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Reward</span><span className="font-medium">{current.reward.toFixed(2)}</span></div>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
