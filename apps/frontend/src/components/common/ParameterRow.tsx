import { RotateCcw, Info } from 'lucide-react';
import { useState } from 'react';

interface ParameterRowProps {
  label: string;
  value: string | number;
  onChange: (val: string) => void;
  type?: 'text' | 'number';
  unit?: string;
  tooltip?: string;
  defaultValue?: string | number;
  min?: number;
  max?: number;
  step?: number;
  className?: string;
}

export default function ParameterRow({
  label, value, onChange, type = 'text', unit, tooltip,
  defaultValue, min, max, step, className = '',
}: ParameterRowProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <div className={`flex items-center gap-3 py-2 ${className}`}>
      <div className="flex items-center gap-1.5 min-w-[140px]">
        <label className="text-sm text-gray-700 font-medium">{label}</label>
        {tooltip && (
          <div className="relative">
            <Info
              size={14}
              className="text-gray-400 cursor-help"
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
            />
            {showTooltip && (
              <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg w-56 shadow-lg">
                {tooltip}
                <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 w-2 h-2 bg-gray-900 rotate-45" />
              </div>
            )}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 flex-1">
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          min={min}
          max={max}
          step={step}
          className="flex-1 px-3 py-1.5 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"
          title={tooltip}
        />
        {unit && <span className="text-xs text-gray-400 min-w-[24px]">{unit}</span>}
        {defaultValue !== undefined && (
          <button
            onClick={() => onChange(String(defaultValue))}
            className="p-1 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
            title={`Reset to ${defaultValue}`}
          >
            <RotateCcw size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
