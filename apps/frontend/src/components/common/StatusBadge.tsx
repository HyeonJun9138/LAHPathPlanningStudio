type StatusType = 'idle' | 'ready' | 'running' | 'completed' | 'failed' | 'stopped' | 'queued';

const styles: Record<StatusType, string> = {
  idle: 'bg-gray-100 text-gray-600',
  ready: 'bg-blue-50 text-blue-600',
  queued: 'bg-blue-50 text-blue-600',
  running: 'bg-amber-50 text-amber-600',
  completed: 'bg-green-50 text-green-700',
  failed: 'bg-red-50 text-red-600',
  stopped: 'bg-orange-50 text-orange-600',
};

const dots: Record<StatusType, string> = {
  idle: 'bg-gray-400',
  ready: 'bg-blue-500',
  queued: 'bg-blue-500',
  running: 'bg-amber-500 animate-pulse',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  stopped: 'bg-orange-500',
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export default function StatusBadge({ status, className = '' }: StatusBadgeProps) {
  const s = (status as StatusType) in styles ? (status as StatusType) : 'idle';
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${styles[s]} ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dots[s]}`} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}
