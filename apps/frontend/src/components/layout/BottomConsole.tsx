import { useRef, useEffect } from 'react';
import { Terminal, Activity, Package, ChevronUp, ChevronDown, Trash2 } from 'lucide-react';
import { useAppStore } from '../../stores/appStore';
import { useT } from '../../i18n';
import type { TranslationKey } from '../../i18n';

const tabConfig: { key: 'logs' | 'progress' | 'artifacts'; labelKey: TranslationKey; icon: typeof Terminal }[] = [
  { key: 'logs', labelKey: 'console.logs', icon: Terminal },
  { key: 'progress', labelKey: 'console.progress', icon: Activity },
  { key: 'artifacts', labelKey: 'console.artifacts', icon: Package },
];

export default function BottomConsole() {
  const { consoleExpanded, toggleConsole, consoleTab, setConsoleTab, consoleLogs, clearLogs, jobs } = useAppStore();
  const t = useT();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [consoleLogs]);

  const levelColors = {
    info: 'text-gray-600',
    warn: 'text-amber-600',
    error: 'text-red-500',
    debug: 'text-gray-400',
  };

  const runningJobs = jobs.filter((j) => j.status === 'running');

  return (
    <div
      className="border-t border-gray-200/50 bg-white/70 backdrop-blur-xl transition-all duration-300 flex flex-col shrink-0"
      style={{ height: consoleExpanded ? 220 : 36 }}
    >
      {/* Header bar */}
      <div
        className="flex items-center gap-3 px-4 h-9 shrink-0 cursor-pointer select-none"
        onClick={toggleConsole}
      >
        <div className="flex items-center gap-1">
          {tabConfig.map(({ key, labelKey, icon: Icon }) => (
            <button
              key={key}
              onClick={(e) => {
                e.stopPropagation();
                setConsoleTab(key);
                if (!consoleExpanded) toggleConsole();
              }}
              className={`flex items-center gap-1 px-2 py-0.5 text-xs rounded-md transition-colors ${
                consoleTab === key ? 'bg-gray-200/60 text-gray-800 font-medium' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <Icon size={12} />
              {t(labelKey)}
            </button>
          ))}
        </div>
        <div className="flex-1" />
        {runningJobs.length > 0 && (
          <span className="text-xs text-amber-600 font-medium animate-pulse">
            {runningJobs.length} {t('console.jobsRunning')}
          </span>
        )}
        {consoleTab === 'logs' && consoleLogs.length > 0 && (
          <button
            onClick={(e) => { e.stopPropagation(); clearLogs(); }}
            className="p-0.5 text-gray-400 hover:text-gray-600"
            title={t('console.clearLogs')}
          >
            <Trash2 size={12} />
          </button>
        )}
        {consoleExpanded ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronUp size={14} className="text-gray-400" />}
      </div>

      {/* Content */}
      {consoleExpanded && (
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 pb-2 text-xs font-mono">
          {consoleTab === 'logs' && (
            consoleLogs.length === 0 ? (
              <div className="text-gray-400 italic py-4">{t('console.noLogs')}</div>
            ) : (
              consoleLogs.map((log) => (
                <div key={log.id} className="flex gap-3 py-0.5 leading-5">
                  <span className="text-gray-400 shrink-0">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span className={`uppercase w-10 shrink-0 font-semibold ${levelColors[log.level]}`}>
                    {log.level}
                  </span>
                  <span className="text-gray-700">{log.message}</span>
                </div>
              ))
            )
          )}

          {consoleTab === 'progress' && (
            jobs.length === 0 ? (
              <div className="text-gray-400 italic py-4">{t('console.noActiveJobs')}</div>
            ) : (
              <div className="space-y-2 py-2">
                {jobs.map((job) => (
                  <div key={job.job_id} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-700 font-medium">{job.stage} — {job.job_id}</span>
                      <span className="text-gray-500">{(job.progress * 100).toFixed(0)}%</span>
                    </div>
                    <div className="w-full h-1.5 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          job.status === 'completed' ? 'bg-green-500' :
                          job.status === 'failed' ? 'bg-red-500' :
                          'bg-blue-500'
                        }`}
                        style={{ width: `${job.progress * 100}%` }}
                      />
                    </div>
                    {job.message && <div className="text-gray-500">{job.message}</div>}
                  </div>
                ))}
              </div>
            )
          )}

          {consoleTab === 'artifacts' && (
            <div className="text-gray-400 italic py-4">{t('console.artifactsAfterJob')}</div>
          )}
        </div>
      )}
    </div>
  );
}
