import type { ReactNode } from 'react';

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  padding?: string;
}

export default function GlassCard({ children, className = '', padding = 'p-6' }: GlassCardProps) {
  return (
    <div
      className={`bg-white/80 backdrop-blur-xl rounded-2xl border border-gray-200/50 shadow-sm ${padding} ${className}`}
    >
      {children}
    </div>
  );
}
