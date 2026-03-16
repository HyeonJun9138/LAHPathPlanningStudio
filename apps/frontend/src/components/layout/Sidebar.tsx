import {
  LayoutDashboard, FolderOpen, Mountain, ShieldAlert,
  Target, FlaskConical, Brain, BarChart3, Play,
  GitCompare, FileText, Settings, ChevronLeft, ChevronRight,
} from 'lucide-react';
import { useAppStore } from '../../stores/appStore';
import { useT } from '../../i18n';
import type { TabId } from '../../types';
import type { TranslationKey } from '../../i18n';

const tabs: { id: TabId; labelKey: TranslationKey; icon: typeof LayoutDashboard }[] = [
  { id: 'dashboard', labelKey: 'tab.dashboard', icon: LayoutDashboard },
  { id: 'resources', labelKey: 'tab.resources', icon: FolderOpen },
  { id: 'terrain', labelKey: 'tab.terrain', icon: Mountain },
  { id: 'hazard', labelKey: 'tab.hazard', icon: ShieldAlert },
  { id: 'mission', labelKey: 'tab.mission', icon: Target },
  { id: 'candidate', labelKey: 'tab.candidate', icon: FlaskConical },
  { id: 'training', labelKey: 'tab.training', icon: Brain },
  { id: 'evaluation', labelKey: 'tab.evaluation', icon: BarChart3 },
  { id: 'simulation', labelKey: 'tab.simulation', icon: Play },
  { id: 'compare', labelKey: 'tab.compare', icon: GitCompare },
  { id: 'reports', labelKey: 'tab.reports', icon: FileText },
  { id: 'settings', labelKey: 'tab.settings', icon: Settings },
];

export default function Sidebar() {
  const { currentTab, setCurrentTab, sidebarExpanded, toggleSidebar } = useAppStore();
  const t = useT();

  return (
    <aside
      className="h-full flex flex-col bg-white/60 backdrop-blur-xl border-r border-gray-200/50 transition-all duration-300 ease-in-out"
      style={{ width: sidebarExpanded ? 240 : 64 }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-14 border-b border-gray-200/40">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shrink-0">
          <Mountain size={16} className="text-white" />
        </div>
        {sidebarExpanded && (
          <span className="text-sm font-semibold text-gray-800 truncate">LAH Studio</span>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-2 px-2 space-y-0.5 overflow-y-auto">
        {tabs.map(({ id, labelKey, icon: Icon }) => {
          const active = currentTab === id;
          const label = t(labelKey);
          return (
            <button
              key={id}
              onClick={() => setCurrentTab(id)}
              className={`
                relative w-full flex items-center gap-3 rounded-xl text-sm font-medium transition-all duration-150
                ${sidebarExpanded ? 'px-3 py-2.5' : 'px-0 py-2.5 justify-center'}
                ${active
                  ? 'bg-blue-50/80 text-[#0071e3]'
                  : 'text-gray-600 hover:bg-gray-100/60 hover:text-gray-800'
                }
              `}
              title={!sidebarExpanded ? label : undefined}
            >
              {active && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-[#0071e3] rounded-r-full" />
              )}
              <Icon size={18} className="shrink-0" />
              {sidebarExpanded && <span className="truncate">{label}</span>}
            </button>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="px-2 py-3 border-t border-gray-200/40">
        <button
          onClick={toggleSidebar}
          className="w-full flex items-center justify-center gap-2 py-2 text-gray-400 hover:text-gray-600 rounded-xl hover:bg-gray-100/60 text-sm"
        >
          {sidebarExpanded ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
          {sidebarExpanded && <span>{t('sidebar.collapse')}</span>}
        </button>
      </div>
    </aside>
  );
}
