import { useState, useMemo } from 'react';
import { Cpu, Award, Save } from 'lucide-react';
import GlassCard from '../common/GlassCard';
import SectionTitle from '../common/SectionTitle';
import ParameterRow from '../common/ParameterRow';
import PlotCard from '../common/PlotCard';
import StatusBadge from '../common/StatusBadge';
import { useT } from '../../i18n';

function generateTrainingData(n: number) {
  const ts: number[] = [];
  const rewards: number[] = [];
  const success: number[] = [];
  const lengths: number[] = [];
  let r = -50;
  let s = 0;
  for (let i = 0; i < n; i++) {
    ts.push(i * 5000);
    r += (Math.random() - 0.3) * 10;
    r = Math.min(r, 120);
    rewards.push(r);
    s = Math.min(1, Math.max(0, s + (Math.random() - 0.35) * 0.05));
    success.push(s);
    lengths.push(Math.max(50, 500 - i * 2 + Math.random() * 50));
  }
  return { ts, rewards, success, lengths };
}

const checkpoints = [
  { path: 'checkpoint_100000.zip', timestep: 100000, reward: 42.5, success: 0.35, time: '23:30' },
  { path: 'checkpoint_200000.zip', timestep: 200000, reward: 68.2, success: 0.52, time: '00:15' },
  { path: 'checkpoint_300000.zip', timestep: 300000, reward: 85.1, success: 0.68, time: '01:02' },
  { path: 'best_model.zip', timestep: 280000, reward: 89.3, success: 0.71, time: '00:50' },
];

export default function TrainingCenter() {
  const [algorithm, setAlgorithm] = useState('MaskablePPO');
  const [device, setDevice] = useState('cuda:0');
  const [seed, setSeed] = useState('42');
  const [nEnvs, setNEnvs] = useState('4');
  const [totalSteps, setTotalSteps] = useState('1000000');
  const [batchSize, setBatchSize] = useState('256');
  const [lr, setLr] = useState('0.0003');
  const [curriculum, setCurriculum] = useState('curriculum_b');
  const [checkpointInterval, setCheckpointInterval] = useState('50000');
  const [status, setStatus] = useState('idle');
  const t = useT();

  const data = useMemo(() => generateTrainingData(60), []);

  const handleStart = () => {
    setStatus('running');
    setTimeout(() => setStatus('completed'), 3000);
  };

  return (
    <div className="grid grid-cols-12 gap-6 h-full">
      {/* LEFT */}
      <div className="col-span-3 space-y-4 overflow-y-auto">
        <GlassCard>
          <SectionTitle title={t('training.algorithm')} />
          <select
            value={algorithm}
            onChange={(e) => setAlgorithm(e.target.value)}
            className="w-full px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30"
          >
            <option value="MaskablePPO">MaskablePPO</option>
            <option value="PPO">PPO</option>
          </select>
        </GlassCard>

        <GlassCard>
          <SectionTitle title={t('training.hyperparameters')} />
          <div className="space-y-0.5">
            <div>
              <label className="text-xs text-gray-500 font-medium">{t('training.device')}</label>
              <select value={device} onChange={(e) => setDevice(e.target.value)} className="w-full mt-1 px-3 py-1.5 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                <option value="cpu">CPU</option>
                <option value="cuda:0">CUDA:0</option>
              </select>
            </div>
            <ParameterRow label={t('training.seed')} value={seed} onChange={setSeed} type="number" tooltip="Random seed for reproducibility" defaultValue="42" />
            <ParameterRow label="n_envs" value={nEnvs} onChange={setNEnvs} type="number" tooltip="Number of parallel environments. More envs = faster but more VRAM." defaultValue="4" min={1} max={32} />
            <ParameterRow label={t('training.totalSteps')} value={totalSteps} onChange={setTotalSteps} type="number" tooltip="Total training timesteps" defaultValue="1000000" />
            <ParameterRow label={t('training.batchSize')} value={batchSize} onChange={setBatchSize} type="number" tooltip="Minibatch size for PPO updates" defaultValue="256" />
            <ParameterRow label={t('training.learningRate')} value={lr} onChange={setLr} type="number" tooltip="Optimizer learning rate. 1e-4 to 5e-4 typical." defaultValue="0.0003" step={0.0001} />
            <div>
              <label className="text-xs text-gray-500 font-medium">{t('training.curriculum')}</label>
              <select value={curriculum} onChange={(e) => setCurriculum(e.target.value)} className="w-full mt-1 px-3 py-1.5 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                <option value="curriculum_a">Curriculum A</option>
                <option value="curriculum_b">Curriculum B</option>
                <option value="curriculum_c">Curriculum C</option>
              </select>
            </div>
            <ParameterRow label={t('training.checkpointInterval')} value={checkpointInterval} onChange={setCheckpointInterval} type="number" tooltip="Save checkpoint every N timesteps" defaultValue="50000" />
          </div>
        </GlassCard>

        {/* Action buttons */}
        <GlassCard padding="p-4">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleStart}
              disabled={status === 'running'}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-[#0071e3] rounded-xl hover:bg-[#0077ED] disabled:opacity-40"
            >
              {status === 'running' ? t('training.training') : t('common.start')}
            </button>
            <button
              disabled={status !== 'running'}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-xl hover:bg-gray-200 disabled:opacity-40"
            >
              {t('common.pause')}
            </button>
            <button
              disabled={status !== 'running'}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-xl hover:bg-gray-200 disabled:opacity-40"
            >
              {t('common.resume')}
            </button>
            <button
              onClick={() => setStatus('stopped')}
              disabled={status !== 'running'}
              className="px-4 py-2 text-sm font-medium text-red-600 bg-red-50 rounded-xl hover:bg-red-100 disabled:opacity-40"
            >
              {t('common.stop')}
            </button>
          </div>
          <div className="mt-3 flex items-center justify-between">
            <StatusBadge status={status} />
            {status === 'running' && (
              <span className="text-xs text-gray-400 animate-pulse">Step 285,000 / {totalSteps}</span>
            )}
          </div>
        </GlassCard>
      </div>

      {/* CENTER - Charts */}
      <div className="col-span-6 space-y-4 overflow-y-auto">
        <PlotCard
          title={t('training.rewardCurve')}
          data={[
            {
              x: data.ts,
              y: data.rewards,
              type: 'scatter',
              mode: 'lines',
              line: { color: '#0071e3', width: 2, shape: 'spline' },
              fill: 'tozeroy',
              fillcolor: 'rgba(0,113,227,0.08)',
            },
          ]}
          layout={{ xaxis: { title: { text: 'Timestep' } }, yaxis: { title: { text: 'Mean Reward' } } }}
          height={250}
        />

        <div className="grid grid-cols-2 gap-4">
          <PlotCard
            title={t('training.successRate')}
            data={[
              {
                x: data.ts,
                y: data.success,
                type: 'scatter',
                mode: 'lines',
                line: { color: '#34c759', width: 2, shape: 'spline' },
                fill: 'tozeroy',
                fillcolor: 'rgba(52,199,89,0.08)',
              },
            ]}
            layout={{ yaxis: { title: { text: 'Rate' }, range: [0, 1] } }}
            height={200}
          />

          <PlotCard
            title={t('training.episodeLength')}
            data={[
              {
                x: data.ts,
                y: data.lengths,
                type: 'scatter',
                mode: 'lines',
                line: { color: '#ff9f0a', width: 2, shape: 'spline' },
              },
            ]}
            layout={{ yaxis: { title: { text: 'Steps' } } }}
            height={200}
          />
        </div>
      </div>

      {/* RIGHT */}
      <div className="col-span-3 space-y-4 overflow-y-auto">
        <GlassCard>
          <div className="flex items-center gap-2 mb-3">
            <Cpu size={16} className="text-blue-500" />
            <SectionTitle title={t('training.gpuStatus')} className="mb-0" />
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">{t('training.device')}</span>
              <span className="font-medium">NVIDIA RTX 4090</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">{t('training.utilization')}</span>
              <span className="font-medium">78%</span>
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-gray-500">{t('training.memory')}</span>
                <span className="text-xs text-gray-400">6.2 / 24.0 GB</span>
              </div>
              <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                <div className="h-full bg-green-500 rounded-full" style={{ width: '26%' }} />
              </div>
            </div>
          </div>
        </GlassCard>

        <GlassCard>
          <div className="flex items-center gap-2 mb-3">
            <Award size={16} className="text-amber-500" />
            <SectionTitle title={t('training.bestCheckpoint')} className="mb-0" />
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">{t('training.model')}</span>
              <span className="font-medium font-mono text-xs">best_model.zip</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">{t('training.reward')}</span>
              <span className="font-medium text-green-600">89.3</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">{t('training.success')}</span>
              <span className="font-medium text-green-600">71.0%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">{t('training.timestep')}</span>
              <span className="font-medium">280,000</span>
            </div>
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle title={t('training.checkpoints')} />
          <div className="space-y-1.5">
            {checkpoints.map((ck) => (
              <div key={ck.path} className="flex items-center gap-2 px-2 py-2 bg-gray-50/60 rounded-lg text-xs">
                <Save size={13} className="text-gray-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-gray-700 truncate">{ck.path}</div>
                  <div className="text-gray-400">Step {ck.timestep.toLocaleString()} · R={ck.reward} · S={(ck.success * 100).toFixed(0)}%</div>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard>
          <SectionTitle title={t('training.summary')} />
          <div className="space-y-2 text-sm">
            {[
              { label: t('training.totalTimesteps'), value: '300,000' },
              { label: t('training.episodes'), value: '1,847' },
              { label: t('training.meanReward'), value: '82.4' },
              { label: t('training.bestReward'), value: '89.3' },
              { label: t('training.wallTime'), value: '2h 14m' },
            ].map((m) => (
              <div key={m.label} className="flex justify-between">
                <span className="text-gray-500">{m.label}</span>
                <span className="font-medium text-gray-800">{m.value}</span>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
