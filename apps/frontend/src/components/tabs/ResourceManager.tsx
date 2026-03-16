import { useState } from 'react';
import { Search, RefreshCw, Upload, Eye, Database, FileText, Map } from 'lucide-react';
import GlassCard from '../common/GlassCard';
import SectionTitle from '../common/SectionTitle';
import StatusBadge from '../common/StatusBadge';
import { useT } from '../../i18n';

interface ResourceItem {
  filename: string;
  type: string;
  crs: string;
  resolution: string;
  dimensions: string;
  size: string;
  registered: boolean;
}

const demoResources: ResourceItem[] = [
  { filename: 'Hongik_48km.tif', type: 'GeoTIFF', crs: 'EPSG:5186', resolution: '30m', dimensions: '1600×1600', size: '9.8 MB', registered: true },
  { filename: 'Inje_48km.tif', type: 'GeoTIFF', crs: 'EPSG:5186', resolution: '30m', dimensions: '1600×1600', size: '10.2 MB', registered: true },
  { filename: 'Jipo_48km.tif', type: 'GeoTIFF', crs: 'EPSG:5186', resolution: '30m', dimensions: '1600×1600', size: '9.5 MB', registered: false },
];

const presets = [
  { name: 'sample_hazards.json', type: 'Hazard Config', size: '2.1 KB' },
  { name: 'sample_mission.yaml', type: 'Mission Preset', size: '1.3 KB' },
  { name: 'curriculum_a.yaml', type: 'Curriculum', size: '0.8 KB' },
  { name: 'curriculum_b.yaml', type: 'Curriculum', size: '0.9 KB' },
  { name: 'curriculum_c.yaml', type: 'Curriculum', size: '0.7 KB' },
];

export default function ResourceManager() {
  const [scanning, setScanning] = useState(false);
  const [filter, setFilter] = useState('');
  const t = useT();

  const filtered = demoResources.filter((r) =>
    r.filename.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Scan & filter bar */}
      <GlassCard>
        <div className="flex items-center gap-4">
          <button
            onClick={() => { setScanning(true); setTimeout(() => setScanning(false), 1500); }}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-[#0071e3] rounded-xl hover:bg-[#0077ED]"
          >
            <RefreshCw size={15} className={scanning ? 'animate-spin' : ''} />
            {t('resources.scanResources')}
          </button>
          <div className="relative flex-1 max-w-sm">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder={t('resources.filterPlaceholder')}
              className="w-full pl-9 pr-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            />
          </div>
        </div>
      </GlassCard>

      {/* Terrain files */}
      <GlassCard>
        <SectionTitle
          title={t('resources.terrainFiles')}
          description={t('resources.terrainDesc')}
        />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-gray-200/50">
                <th className="pb-2 font-medium">{t('common.preview')}</th>
                <th className="pb-2 font-medium">{t('resources.filename')}</th>
                <th className="pb-2 font-medium">{t('resources.type')}</th>
                <th className="pb-2 font-medium">CRS</th>
                <th className="pb-2 font-medium">{t('resources.resolution')}</th>
                <th className="pb-2 font-medium">{t('resources.dimensions')}</th>
                <th className="pb-2 font-medium">{t('resources.size')}</th>
                <th className="pb-2 font-medium">{t('dashboard.status')}</th>
                <th className="pb-2 font-medium">{t('resources.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.filename} className="border-b border-gray-100 last:border-0">
                  <td className="py-3">
                    <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-green-100 to-emerald-200 flex items-center justify-center">
                      <Map size={18} className="text-green-600" />
                    </div>
                  </td>
                  <td className="py-3 font-medium text-gray-800">{r.filename}</td>
                  <td className="py-3 text-gray-600">
                    <span className="flex items-center gap-1">
                      <Database size={13} className="text-gray-400" />
                      {r.type}
                    </span>
                  </td>
                  <td className="py-3 text-gray-600 font-mono text-xs">{r.crs}</td>
                  <td className="py-3 text-gray-600">{r.resolution}</td>
                  <td className="py-3 text-gray-600">{r.dimensions}</td>
                  <td className="py-3 text-gray-500">{r.size}</td>
                  <td className="py-3">
                    <StatusBadge status={r.registered ? 'completed' : 'idle'} />
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-1">
                      <button className="p-1.5 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg" title={t('common.preview')}>
                        <Eye size={15} />
                      </button>
                      {!r.registered && (
                        <button className="px-2.5 py-1 text-xs font-medium text-[#0071e3] bg-blue-50 rounded-lg hover:bg-blue-100">
                          <Upload size={13} className="inline mr-1" />
                          {t('common.register')}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* Presets */}
      <GlassCard>
        <SectionTitle title={t('resources.presetsConfigs')} description={t('resources.presetsDesc')} />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {presets.map((p) => (
            <div key={p.name} className="flex items-center gap-3 px-4 py-3 bg-gray-50/60 rounded-xl hover:bg-gray-100/60 transition-colors">
              <FileText size={18} className="text-gray-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-700 truncate">{p.name}</div>
                <div className="text-xs text-gray-400">{p.type} · {p.size}</div>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}
