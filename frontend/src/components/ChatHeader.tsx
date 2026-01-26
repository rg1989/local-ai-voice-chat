import { ConversationSummary, MemoryUsage } from '../types';
import { MemoryIndicator } from './MemoryIndicator';

interface ChatHeaderProps {
  conversation: ConversationSummary | null;
  isConnected: boolean;
  ttsEnabled: boolean;
  onTtsToggle: () => void;
  memoryUsage: MemoryUsage | null;
}

// Bot/AI icon
function BotIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  );
}

// Speaker on icon
function SpeakerOnIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
    </svg>
  );
}

// Speaker off/muted icon
function SpeakerOffIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
    </svg>
  );
}

export function ChatHeader({ conversation, isConnected, ttsEnabled, onTtsToggle, memoryUsage }: ChatHeaderProps) {
  return (
    <header className="bg-[#1e2227] border-b border-slate-700/50 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* AI Avatar */}
          <div className="w-11 h-11 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <BotIcon />
          </div>
          
          <div>
            <h1 className="text-lg font-semibold text-white">
              {conversation?.title || 'New Conversation'}
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-red-500'}`} />
              <span className="text-xs text-slate-400">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Memory Usage Indicator */}
          <MemoryIndicator memory={memoryUsage} />

          {/* TTS Toggle Button */}
          <button
            onClick={onTtsToggle}
            className={`p-2 rounded-lg transition-all cursor-pointer ${
              ttsEnabled
                ? 'bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30'
                : 'bg-slate-700/50 text-slate-500 hover:bg-slate-700 hover:text-slate-400'
            }`}
            title={ttsEnabled ? 'Voice responses enabled' : 'Voice responses disabled'}
          >
            {ttsEnabled ? <SpeakerOnIcon /> : <SpeakerOffIcon />}
          </button>
        </div>
      </div>
    </header>
  );
}
