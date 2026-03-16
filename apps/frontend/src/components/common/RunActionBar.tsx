import { Play, Square, CheckCircle2, Loader2 } from 'lucide-react';
import StatusBadge from './StatusBadge';
import { useT } from '../../i18n';

interface RunActionBarProps {
  status: string;
  onValidate?: () => void;
  onRun?: () => void;
  onStop?: () => void;
  elapsed?: string;
  disableRun?: boolean;
  disableValidate?: boolean;
  className?: string;
}

export default function RunActionBar({
  status, onValidate, onRun, onStop, elapsed,
  disableRun, disableValidate, className = '',
}: RunActionBarProps) {
  const t = useT();
  const isRunning = status === 'running';

  return (
    <div className={`flex items-center gap-3 py-3 px-4 bg-gray-50/80 rounded-xl border border-gray-200/40 ${className}`}>
      {onValidate && (
        <button
          onClick={onValidate}
          disabled={disableValidate || isRunning}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <CheckCircle2 size={15} />
          {t('common.validate')}
        </button>
      )}
      {onRun && (
        <button
          onClick={onRun}
          disabled={disableRun || isRunning}
          className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium text-white bg-[#0071e3] rounded-lg hover:bg-[#0077ED] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {isRunning ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
          {isRunning ? t('common.running') : t('common.run')}
        </button>
      )}
      {onStop && isRunning && (
        <button
          onClick={onStop}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-600 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100"
        >
          <Square size={15} />
          {t('common.stop')}
        </button>
      )}
      <div className="flex-1" />
      <StatusBadge status={status} />
      {elapsed && <span className="text-xs text-gray-400">{elapsed}</span>}
    </div>
  );
}
