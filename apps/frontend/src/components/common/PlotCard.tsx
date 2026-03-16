import { Download } from 'lucide-react';
import GlassCard from './GlassCard';
import Plot from 'react-plotly.js';
import type { Data, Layout } from 'plotly.js';
import { useCallback, useRef } from 'react';

interface PlotCardProps {
  title: string;
  data: Data[];
  layout?: Partial<Layout>;
  height?: number;
  className?: string;
}

export default function PlotCard({ title, data, layout = {}, height = 300, className = '' }: PlotCardProps) {
  const plotRef = useRef<HTMLDivElement>(null);

  const handleExport = useCallback(() => {
    const plotEl = plotRef.current?.querySelector('.js-plotly-plot') as HTMLElement | null;
    if (plotEl) {
      import('plotly.js').then((Plotly) => {
        Plotly.downloadImage(plotEl as unknown as Plotly.PlotlyHTMLElement, {
          format: 'png',
          width: 1200,
          height: 800,
          filename: title.toLowerCase().replace(/\s+/g, '_'),
        });
      });
    }
  }, [title]);

  const mergedLayout: Partial<Layout> = {
    autosize: true,
    height,
    margin: { l: 48, r: 24, t: 8, b: 40 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { family: '-apple-system, BlinkMacSystemFont, sans-serif', size: 11, color: '#6b7280' },
    xaxis: { gridcolor: 'rgba(0,0,0,0.06)', ...layout.xaxis },
    yaxis: { gridcolor: 'rgba(0,0,0,0.06)', ...layout.yaxis },
    ...layout,
  };

  return (
    <GlassCard className={className} padding="p-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-semibold text-gray-800">{title}</h4>
        <button
          onClick={handleExport}
          className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg"
          title="Export PNG"
        >
          <Download size={14} />
        </button>
      </div>
      <div ref={plotRef}>
        <Plot
          data={data}
          layout={mergedLayout}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: '100%' }}
        />
      </div>
    </GlassCard>
  );
}
