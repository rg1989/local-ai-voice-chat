import { ConversationSummary } from '../types';

interface ChatHeaderProps {
  conversation: ConversationSummary | null;
  isConnected: boolean;
}

// Bot/AI icon
function BotIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  );
}

export function ChatHeader({ conversation, isConnected }: ChatHeaderProps) {
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
              {conversation?.title || 'Voice Assistant'}
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-red-500'}`} />
              <span className="text-xs text-slate-400">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </div>

        {/* Message count badge */}
        {conversation && conversation.message_count > 0 && (
          <div className="text-xs text-slate-400 bg-slate-700/50 px-3 py-1.5 rounded-full">
            {conversation.message_count} messages
          </div>
        )}
      </div>
    </header>
  );
}
