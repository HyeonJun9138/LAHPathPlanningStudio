import { TrendingUp, TrendingDown } from 'lucide-react';

interface MetricPillProps {
  label: string;
  value: string | number;
  unit?: string;
  change?: number;
  className?: string;
}

export default function MetricPill({ label, value, unit, change, className = '' }: MetricPillProps) {
  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-100/80 text-sm ${className}`}>
      <span className="text-gray-500">{label}</span>
      <span className="font-semibold text-gray-900">
        {value}
        {unit && <span className="text-gray-400 font-normal ml-0.5">{unit}</span>}
      </span>
      {change !== undefined && (
        <span className={`flex items-center gap-0.5 text-xs ${change >= 0 ? 'text-green-600' : 'text-red-500'}`}>
          {change >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
          {Math.abs(change).toFixed(1)}%
        </span>
      )}
    </div>
  );
}
