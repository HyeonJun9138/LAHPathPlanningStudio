import { useState } from 'react';
import { Save, RotateCcw, FolderOpen, Monitor, Palette, Clock, HardDrive, Terminal } from 'lucide-react';
import GlassCard from '../common/GlassCard';
import SectionTitle from '../common/SectionTitle';
import { useT } from '../../i18n';
import type { TranslationKey } from '../../i18n';

interface SettingsState {
  workspacePath: string;
  defaultDevice: string;
  plotTheme: string;
  autosaveInterval: number;
  jobPollingInterval: number;
  logRetentionDays: number;
  externalEditor: string;
  apiBaseUrl: string;
  maxConcurrentJobs: number;
  enableNotifications: boolean;
  darkMode: boolean;
  compactSidebar: boolean;
}

const defaultSettings: SettingsState = {
  workspacePath: '/home/user/workspace/LAHPathPlanningStudio',
  defaultDevice: 'cuda:0',
  plotTheme: 'plotly_white',
  autosaveInterval: 30,
  jobPollingInterval: 5,
  logRetentionDays: 7,
  externalEditor: 'code',
  apiBaseUrl: 'http://127.0.0.1:8000',
  maxConcurrentJobs: 2,
  enableNotifications: true,
  darkMode: false,
  compactSidebar: false,
};

export default function Settings() {
  const [settings, setSettings] = useState<SettingsState>({ ...defaultSettings });
  const [saved, setSaved] = useState(false);
  const t = useT();

  const update = <K extends keyof SettingsState>(key: K, value: SettingsState[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleReset = () => {
    setSettings({ ...defaultSettings });
    setSaved(false);
  };

  const toggles: { key: 'enableNotifications' | 'darkMode' | 'compactSidebar'; labelKey: TranslationKey; descKey: TranslationKey }[] = [
    { key: 'enableNotifications', labelKey: 'settings.enableNotifications', descKey: 'settings.notificationsDesc' },
    { key: 'darkMode', labelKey: 'settings.darkMode', descKey: 'settings.darkModeDesc' },
    { key: 'compactSidebar', labelKey: 'settings.compactSidebar', descKey: 'settings.compactSidebarDesc' },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* General */}
      <GlassCard>
        <SectionTitle title={t('settings.general')} description={t('settings.generalDesc')} />
        <div className="space-y-4">
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1">
              <FolderOpen size={15} className="text-gray-400" />
              {t('settings.workspacePath')}
            </label>
            <input
              type="text"
              value={settings.workspacePath}
              onChange={(e) => update('workspacePath', e.target.value)}
              className="w-full px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30 font-mono"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1">
                <Monitor size={15} className="text-gray-400" />
                {t('settings.defaultDevice')}
              </label>
              <select
                value={settings.defaultDevice}
                onChange={(e) => update('defaultDevice', e.target.value)}
                className="w-full px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              >
                <option value="cuda:0">cuda:0</option>
                <option value="cuda:1">cuda:1</option>
                <option value="cpu">cpu</option>
              </select>
            </div>
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1">
                <Palette size={15} className="text-gray-400" />
                {t('settings.plotTheme')}
              </label>
              <select
                value={settings.plotTheme}
                onChange={(e) => update('plotTheme', e.target.value)}
                className="w-full px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              >
                <option value="plotly_white">Plotly White</option>
                <option value="plotly_dark">Plotly Dark</option>
                <option value="ggplot2">GGPlot2</option>
                <option value="seaborn">Seaborn</option>
                <option value="simple_white">Simple White</option>
              </select>
            </div>
          </div>

          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1">
              <Terminal size={15} className="text-gray-400" />
              {t('settings.externalEditor')}
            </label>
            <input
              type="text"
              value={settings.externalEditor}
              onChange={(e) => update('externalEditor', e.target.value)}
              className="w-full px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30 font-mono"
              placeholder="e.g., code, vim, subl"
            />
          </div>
        </div>
      </GlassCard>

      {/* Intervals */}
      <GlassCard>
        <SectionTitle title={t('settings.intervals')} description={t('settings.intervalsDesc')} />
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1">
              <Clock size={15} className="text-gray-400" />
              {t('settings.autosaveInterval')}
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                value={settings.autosaveInterval}
                onChange={(e) => update('autosaveInterval', Number(e.target.value))}
                min={5}
                max={300}
                className="w-full px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              />
              <span className="text-xs text-gray-400 whitespace-nowrap">{t('settings.seconds')}</span>
            </div>
          </div>
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1">
              <Clock size={15} className="text-gray-400" />
              {t('settings.jobPollingInterval')}
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                value={settings.jobPollingInterval}
                onChange={(e) => update('jobPollingInterval', Number(e.target.value))}
                min={1}
                max={60}
                className="w-full px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              />
              <span className="text-xs text-gray-400 whitespace-nowrap">{t('settings.seconds')}</span>
            </div>
          </div>
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1">
              <HardDrive size={15} className="text-gray-400" />
              {t('settings.logRetention')}
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                value={settings.logRetentionDays}
                onChange={(e) => update('logRetentionDays', Number(e.target.value))}
                min={1}
                max={90}
                className="w-full px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              />
              <span className="text-xs text-gray-400 whitespace-nowrap">{t('settings.days')}</span>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* API & Jobs */}
      <GlassCard>
        <SectionTitle title={t('settings.apiJobs')} description={t('settings.apiJobsDesc')} />
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1 block">{t('settings.apiBaseUrl')}</label>
            <input
              type="text"
              value={settings.apiBaseUrl}
              onChange={(e) => update('apiBaseUrl', e.target.value)}
              className="w-full px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30 font-mono"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1 block">{t('settings.maxConcurrentJobs')}</label>
            <input
              type="number"
              value={settings.maxConcurrentJobs}
              onChange={(e) => update('maxConcurrentJobs', Number(e.target.value))}
              min={1}
              max={8}
              className="w-full px-3 py-2 text-sm bg-white/60 border border-gray-200/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            />
          </div>
        </div>
      </GlassCard>

      {/* Toggles */}
      <GlassCard>
        <SectionTitle title={t('settings.preferences')} description={t('settings.preferencesDesc')} />
        <div className="space-y-3">
          {toggles.map((toggle) => (
            <label key={toggle.key} className="flex items-center justify-between px-3 py-3 rounded-xl hover:bg-gray-50/60 cursor-pointer">
              <div>
                <div className="text-sm font-medium text-gray-700">{t(toggle.labelKey)}</div>
                <div className="text-xs text-gray-400">{t(toggle.descKey)}</div>
              </div>
              <div
                onClick={() => update(toggle.key, !settings[toggle.key])}
                className={`relative w-10 h-6 rounded-full transition-colors cursor-pointer ${
                  settings[toggle.key] ? 'bg-[#0071e3]' : 'bg-gray-300'
                }`}
              >
                <div
                  className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    settings[toggle.key] ? 'translate-x-[18px]' : 'translate-x-0.5'
                  }`}
                />
              </div>
            </label>
          ))}
        </div>
      </GlassCard>

      {/* Actions */}
      <div className="flex items-center justify-between pb-6">
        <button
          onClick={handleReset}
          className="flex items-center gap-2 px-4 py-2.5 text-sm text-gray-600 bg-white/60 border border-gray-200/60 rounded-xl hover:bg-gray-100/60 transition-colors"
        >
          <RotateCcw size={15} />
          {t('settings.resetDefaults')}
        </button>
        <div className="flex items-center gap-3">
          {saved && (
            <span className="text-sm text-green-600 font-medium animate-fade-in">{t('settings.saved')}</span>
          )}
          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-6 py-2.5 text-sm font-medium text-white bg-[#0071e3] rounded-xl hover:bg-[#0077ED] transition-colors shadow-sm"
          >
            <Save size={15} />
            {t('settings.saveSettings')}
          </button>
        </div>
      </div>
    </div>
  );
}
