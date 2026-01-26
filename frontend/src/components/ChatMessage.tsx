import { Message } from '../types';
import { formatTime } from '../utils/audioUtils';

interface ChatMessageProps {
  message: Message;
}

// User avatar icon
function UserAvatar() {
  return (
    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-pink-500 to-rose-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-pink-500/20">
      <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
    </div>
  );
}

// AI/Bot avatar icon
function BotAvatar() {
  return (
    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-emerald-500/20">
      <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    </div>
  );
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 mb-5 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      {isUser ? <UserAvatar /> : <BotAvatar />}

      {/* Message bubble */}
      <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[75%]`}>
        <div
          className={`rounded-2xl px-4 py-3 shadow-md ${
            isUser
              ? 'bg-gradient-to-br from-indigo-600 to-indigo-700 text-white rounded-tr-md'
              : 'bg-[#2a2d32] text-slate-100 rounded-tl-md border border-slate-700/50'
          }`}
        >
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        </div>
        <p className={`text-xs mt-1.5 px-1 ${isUser ? 'text-slate-400' : 'text-slate-500'}`}>
          {formatTime(message.timestamp)}
        </p>
      </div>
    </div>
  );
}
