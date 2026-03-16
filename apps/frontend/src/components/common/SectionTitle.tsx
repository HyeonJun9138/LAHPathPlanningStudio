import type { ReactNode } from 'react';

interface SectionTitleProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}

export default function SectionTitle({ title, description, actions, className = '' }: SectionTitleProps) {
  return (
    <div className={`flex items-start justify-between mb-4 ${className}`}>
      <div>
        <h3 className="text-base font-semibold text-gray-900">{title}</h3>
        {description && <p className="text-sm text-gray-500 mt-0.5">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
