import { useEffect, useRef } from 'react';
import { Message } from '../types';
import { ChatMessage } from './ChatMessage';

interface ChatMessagesProps {
  messages: Message[];
  streamingContent: string;
  isListening: boolean;
  onToggleListening: () => void;
  onClearChat: () => void;
  isDisabled: boolean;
}

// Microphone icon
function MicrophoneIcon() {
  return (
    <svg
      className="w-12 h-12 text-white"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
      />
    </svg>
  );
}

// Listening animation icon (sound waves)
function ListeningIcon() {
  return (
    <div className="flex items-center justify-center gap-1.5">
      <div className="w-1.5 h-5 bg-white rounded-full animate-wave" style={{ animationDelay: '0ms' }} />
      <div className="w-1.5 h-8 bg-white rounded-full animate-wave" style={{ animationDelay: '150ms' }} />
      <div className="w-1.5 h-10 bg-white rounded-full animate-wave" style={{ animationDelay: '300ms' }} />
      <div className="w-1.5 h-8 bg-white rounded-full animate-wave" style={{ animationDelay: '450ms' }} />
      <div className="w-1.5 h-5 bg-white rounded-full animate-wave" style={{ animationDelay: '600ms' }} />
    </div>
  );
}

// Bot avatar for streaming
function StreamingBotAvatar() {
  return (
    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shrink-0 shadow-lg shadow-emerald-500/20">
      <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    </div>
  );
}

// Trash icon for clear chat
function TrashIcon() {
  return (
    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  );
}

export function ChatMessages({ 
  messages, 
  streamingContent,
  isListening,
  onToggleListening,
  onClearChat,
  isDisabled,
}: ChatMessagesProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6 bg-[#15181c] relative">
      <div className="max-w-3xl mx-auto">
        {messages.length === 0 && !streamingContent && (
          <div className="flex flex-col items-center justify-center min-h-[400px] text-center py-16">
            {/* Clickable microphone button */}
            <button
              onClick={onToggleListening}
              disabled={isDisabled}
              className={`w-28 h-28 rounded-full flex items-center justify-center mb-8 transition-all duration-300 shadow-xl ${
                isListening
                  ? 'bg-gradient-to-br from-emerald-500 to-teal-600 scale-110 cursor-pointer shadow-emerald-500/30'
                  : isDisabled
                    ? 'bg-slate-800 cursor-not-allowed opacity-50'
                    : 'bg-gradient-to-br from-emerald-500 to-teal-600 hover:scale-110 cursor-pointer shadow-emerald-500/30 hover:shadow-emerald-500/50'
              }`}
            >
              {isListening ? <ListeningIcon /> : <MicrophoneIcon />}
            </button>
            
            <h2 className="text-xl font-semibold text-slate-200 mb-3">
              {isListening ? 'Listening...' : 'Start Listening'}
            </h2>
            <p className="text-slate-400 text-sm max-w-md leading-relaxed">
              {isListening 
                ? 'Speak now. The assistant will respond when you pause.'
                : isDisabled
                  ? 'Ollama is not available. Please check the error message above.'
                  : 'Click the microphone above to start speaking, or type a message below.'
              }
            </p>
          </div>
        )}

        {messages.map((message, index) => (
          <div key={message.id} className="animate-fade-in" style={{ animationDelay: `${index * 50}ms` }}>
            <ChatMessage message={message} />
          </div>
        ))}

        {streamingContent && (
          <div className="flex gap-3 mb-5 animate-fade-in">
            <StreamingBotAvatar />
            <div className="flex flex-col items-start max-w-[75%]">
              <div className="rounded-2xl rounded-tl-md px-4 py-3 shadow-md bg-[#2a2d32] text-slate-100 border border-slate-700/50">
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {streamingContent}
                  <span className="inline-block w-2 h-4 bg-emerald-500 ml-1 animate-pulse rounded-sm" />
                </p>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Floating Clear Chat button */}
      {messages.length > 0 && (
        <button
          onClick={onClearChat}
          className="absolute bottom-4 left-1/2 -translate-x-1/2 opacity-40 hover:opacity-100 
                     px-3 py-1.5 text-xs text-slate-400 hover:text-red-400 
                     bg-slate-800/80 hover:bg-slate-800 backdrop-blur-sm
                     border border-slate-700/50 hover:border-red-500/50 
                     rounded-full transition-all duration-200 flex items-center gap-1.5 cursor-pointer"
        >
          <TrashIcon />
          Clear Chat
        </button>
      )}
    </div>
  );
}
