import { Cpu, ChevronDown } from 'lucide-react';
import { useAppStore } from '../../stores/appStore';
import { useT } from '../../i18n';
import type { TabId } from '../../types';
import type { TranslationKey } from '../../i18n';

const tabMeta: Record<TabId, { titleKey: TranslationKey; descKey: TranslationKey }> = {
  dashboard: { titleKey: 'tab.dashboard', descKey: 'topbar.desc.dashboard' },
  resources: { titleKey: 'tab.resources', descKey: 'topbar.desc.resources' },
  terrain: { titleKey: 'tab.terrain', descKey: 'topbar.desc.terrain' },
  hazard: { titleKey: 'tab.hazard', descKey: 'topbar.desc.hazard' },
  mission: { titleKey: 'tab.mission', descKey: 'topbar.desc.mission' },
  candidate: { titleKey: 'tab.candidate', descKey: 'topbar.desc.candidate' },
  training: { titleKey: 'tab.training', descKey: 'topbar.desc.training' },
  evaluation: { titleKey: 'tab.evaluation', descKey: 'topbar.desc.evaluation' },
  simulation: { titleKey: 'tab.simulation', descKey: 'topbar.desc.simulation' },
  compare: { titleKey: 'tab.compare', descKey: 'topbar.desc.compare' },
  reports: { titleKey: 'tab.reports', descKey: 'topbar.desc.reports' },
  settings: { titleKey: 'tab.settings', descKey: 'topbar.desc.settings' },
};

export default function TopBar() {
  const { currentTab, currentProject, cudaInfo, selectedDevice, setSelectedDevice, locale, setLocale } = useAppStore();
  const t = useT();
  const meta = tabMeta[currentTab];

  return (
    <header className="h-14 flex items-center px-6 bg-white/60 backdrop-blur-xl border-b border-gray-200/50 shrink-0">
      {/* Tab info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 min-w-0">
          <h1 className="text-base font-semibold text-gray-900 truncate">{t(meta.titleKey)}</h1>
          <span className="text-sm text-gray-400 hidden sm:inline shrink-0">—</span>
          <span className="text-sm text-gray-500 truncate hidden sm:inline">{t(meta.descKey)}</span>
        </div>
      </div>

      {/* Project name */}
      <div className="hidden md:flex items-center gap-4 mr-4 shrink-0">
        <span className="text-xs text-gray-400">{t('topbar.project')}</span>
        <span className="text-sm font-medium text-gray-700 truncate max-w-[160px]">
          {currentProject?.name ?? t('topbar.noProject')}
        </span>
      </div>

      {/* Language toggle */}
      <div className="flex items-center mr-3 shrink-0">
        <button
          onClick={() => setLocale(locale === 'ko' ? 'en' : 'ko')}
          className="flex items-center h-7 rounded-full bg-gray-100/80 border border-gray-200/50 text-xs font-medium overflow-hidden"
        >
          <span
            className={`px-2.5 py-1 rounded-full transition-all duration-200 ${
              locale === 'ko'
                ? 'bg-blue-500 text-white shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            한
          </span>
          <span
            className={`px-2.5 py-1 rounded-full transition-all duration-200 ${
              locale === 'en'
                ? 'bg-blue-500 text-white shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            EN
          </span>
        </button>
      </div>

      {/* CUDA status */}
      <div className="flex items-center gap-2 shrink-0">
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
            cudaInfo?.available
              ? 'bg-green-50 text-green-700'
              : 'bg-gray-100 text-gray-500'
          }`}
        >
          <Cpu size={13} />
          <span>{cudaInfo?.available ? 'CUDA' : 'CPU'}</span>
        </div>

        {/* Device selector */}
        {cudaInfo?.available && cudaInfo.devices.length > 0 && (
          <div className="relative">
            <select
              value={selectedDevice}
              onChange={(e) => setSelectedDevice(e.target.value)}
              className="appearance-none pl-2 pr-6 py-1 text-xs bg-white/70 border border-gray-200/50 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-400 cursor-pointer"
            >
              <option value="cpu">CPU</option>
              {cudaInfo.devices.map((d) => (
                <option key={d.torch_name} value={d.torch_name}>
                  {d.name} ({d.torch_name})
                </option>
              ))}
            </select>
            <ChevronDown size={12} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
          </div>
        )}
      </div>
    </header>
  );
}
