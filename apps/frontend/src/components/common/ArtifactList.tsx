import { FileText, Image, Database, File, ExternalLink } from 'lucide-react';
import type { TerrainArtifact } from '../../types';
import { useT } from '../../i18n';

const iconMap: Record<string, typeof FileText> = {
  tif: Database,
  tiff: Database,
  png: Image,
  json: FileText,
  yaml: FileText,
  csv: FileText,
};

interface ArtifactListProps {
  artifacts: TerrainArtifact[];
  className?: string;
}

export default function ArtifactList({ artifacts, className = '' }: ArtifactListProps) {
  const t = useT();

  if (artifacts.length === 0) {
    return (
      <div className={`text-sm text-gray-400 italic ${className}`}>
        {t('common.noArtifacts')}
      </div>
    );
  }

  return (
    <div className={`space-y-1 ${className}`}>
      {artifacts.map((a) => {
        const ext = a.name.split('.').pop()?.toLowerCase() ?? '';
        const Icon = iconMap[ext] ?? File;
        return (
          <div
            key={a.name}
            className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg hover:bg-gray-100/60 group"
          >
            <Icon size={15} className="text-gray-400" />
            <span className="flex-1 truncate text-gray-700">{a.name}</span>
            <span className="text-xs text-gray-400">{a.size_mb.toFixed(1)} MB</span>
            <button
              className="p-1 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-blue-500"
              title={t('common.open')}
            >
              <ExternalLink size={13} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
