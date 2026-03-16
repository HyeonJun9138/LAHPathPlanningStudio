import { useState, useRef, useEffect } from 'react';
import { MessageCircleQuestion, X, Send, Sparkles, ChevronRight } from 'lucide-react';
import { useAppStore } from '../../stores/appStore';
import { useT } from '../../i18n';
import { tabPrompts } from '../../ai/prompts';
import { chatWithAI } from '../../api/client';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

let msgId = 0;

export default function AIAssistant() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const currentTab = useAppStore((s) => s.currentTab);
  const t = useT();

  const prompt = tabPrompts[currentTab];

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;

    const userMsg: ChatMessage = { id: `msg-${++msgId}`, role: 'user', content: text.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const response = await chatWithAI({
        message: text.trim(),
        system_prompt: prompt.system,
        tab: currentTab,
      });
      const assistantMsg: ChatMessage = {
        id: `msg-${++msgId}`,
        role: 'assistant',
        content: response.reply,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      const errorMsg: ChatMessage = {
        id: `msg-${++msgId}`,
        role: 'assistant',
        content: '죄송합니다. 요청을 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const renderMarkdown = (text: string) => {
    return text.split('\n').map((line, i) => {
      if (line.startsWith('### ')) return <h3 key={i} className="font-semibold text-sm mt-2 mb-1">{line.slice(4)}</h3>;
      if (line.startsWith('## ')) return <h2 key={i} className="font-semibold text-sm mt-2 mb-1">{line.slice(3)}</h2>;
      if (line.startsWith('# ')) return <h1 key={i} className="font-bold text-sm mt-2 mb-1">{line.slice(2)}</h1>;
      if (line.startsWith('- ')) return <div key={i} className="ml-3 text-xs leading-relaxed">• {line.slice(2)}</div>;
      if (line.startsWith('**') && line.endsWith('**')) return <div key={i} className="font-semibold text-xs">{line.slice(2, -2)}</div>;
      if (line.trim() === '') return <div key={i} className="h-1.5" />;
      return <p key={i} className="text-xs leading-relaxed">{line}</p>;
    });
  };

  return (
    <>
      {/* FAB Button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-20 right-6 z-50 w-12 h-12 bg-[#0071e3] text-white rounded-full shadow-lg hover:bg-[#0077ED] transition-all hover:scale-105 flex items-center justify-center"
          title={t('ai.title')}
        >
          <MessageCircleQuestion size={22} />
        </button>
      )}

      {/* Sliding Panel */}
      <div
        className={`fixed top-0 right-0 z-50 h-full w-[360px] transform transition-transform duration-300 ease-in-out ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="h-full flex flex-col bg-white/90 backdrop-blur-2xl border-l border-gray-200/60 shadow-2xl">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200/50">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <Sparkles size={16} className="text-white" />
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-800">{t('ai.title')}</div>
                <div className="text-[10px] text-gray-400">LAH Studio</div>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X size={18} />
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {messages.length === 0 && (
              <div className="space-y-4">
                {/* Welcome */}
                <div className="text-center py-6">
                  <div className="w-14 h-14 mx-auto mb-3 rounded-2xl bg-gradient-to-br from-blue-50 to-purple-50 flex items-center justify-center">
                    <Sparkles size={24} className="text-blue-500" />
                  </div>
                  <p className="text-sm font-medium text-gray-700">{t('ai.title')}</p>
                  <p className="text-xs text-gray-400 mt-1">무엇이든 물어보세요</p>
                </div>

                {/* Suggested questions */}
                <div>
                  <div className="text-[10px] font-medium text-gray-400 uppercase tracking-wider mb-2 px-1">
                    {t('ai.suggestedQuestions')}
                  </div>
                  <div className="space-y-1.5">
                    {prompt.suggestions.map((q, i) => (
                      <button
                        key={i}
                        onClick={() => sendMessage(q)}
                        className="w-full text-left flex items-center gap-2 px-3 py-2.5 text-xs text-gray-600 bg-gray-50/80 border border-gray-200/40 rounded-xl hover:bg-blue-50/60 hover:border-blue-200/50 hover:text-blue-700 transition-colors"
                      >
                        <ChevronRight size={12} className="text-gray-300 shrink-0" />
                        <span className="line-clamp-2">{q}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl ${
                    msg.role === 'user'
                      ? 'bg-[#0071e3] text-white rounded-br-md'
                      : 'bg-gray-100/80 text-gray-700 rounded-bl-md border border-gray-200/40'
                  }`}
                >
                  {msg.role === 'assistant' ? (
                    <div className="space-y-0.5">{renderMarkdown(msg.content)}</div>
                  ) : (
                    <p className="text-xs leading-relaxed">{msg.content}</p>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="px-4 py-3 bg-gray-100/80 rounded-2xl rounded-bl-md border border-gray-200/40">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                    <span className="text-[10px] text-gray-400">{t('ai.thinking')}</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Next Step Button */}
          {messages.length > 0 && !loading && (
            <div className="px-4 pb-2">
              <button
                onClick={() => sendMessage('다음 단계로 무엇을 해야 하나요?')}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 text-xs font-medium text-purple-600 bg-purple-50/80 border border-purple-200/40 rounded-xl hover:bg-purple-100/80 transition-colors"
              >
                <Sparkles size={13} />
                {t('ai.nextStep')}
              </button>
            </div>
          )}

          {/* Input */}
          <div className="px-4 pb-4 pt-2 border-t border-gray-200/50">
            <div className="flex items-center gap-2 bg-gray-50/80 border border-gray-200/50 rounded-xl px-3 py-2 focus-within:ring-2 focus-within:ring-blue-500/30 focus-within:border-blue-300/50">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('ai.placeholder')}
                disabled={loading}
                className="flex-1 bg-transparent text-sm text-gray-700 placeholder:text-gray-400 focus:outline-none disabled:opacity-50"
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={!input.trim() || loading}
                className="p-1.5 text-white bg-[#0071e3] rounded-lg hover:bg-[#0077ED] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Send size={14} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/10 backdrop-blur-[1px]"
          onClick={() => setOpen(false)}
        />
      )}
    </>
  );
}
