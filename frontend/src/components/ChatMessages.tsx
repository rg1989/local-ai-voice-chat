import { useEffect, useRef, useState } from 'react';
import { Message } from '../types';
import { ChatMessage } from './ChatMessage';
import { MarkdownRenderer } from './MarkdownRenderer';
import { formatTime } from '../utils/audioUtils';

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

// Envelope icon for messages counter
function EnvelopeIcon() {
  return (
    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  );
}

// Copy icon
function CopyIcon() {
  return (
    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  );
}

// Download icon
function DownloadIcon() {
  return (
    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
    </svg>
  );
}

// Check icon
function CheckIcon() {
  return (
    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
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
  const [copied, setCopied] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

  // Format messages for export
  const formatMessagesForExport = () => {
    return messages.map(msg => {
      const role = msg.role === 'user' ? 'User' : 'Assistant';
      const time = formatTime(msg.timestamp);
      return `${role} (${time}):\n${msg.content}\n`;
    }).join('\n---\n\n');
  };

  // Copy entire chat to clipboard
  const handleCopyChat = async () => {
    try {
      const text = formatMessagesForExport();
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy chat:', err);
    }
  };

  // Download chat as markdown file
  const handleDownloadChat = () => {
    const text = formatMessagesForExport();
    const blob = new Blob([text], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-${new Date().toISOString().split('T')[0]}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex-1 flex flex-col bg-[#15181c] relative overflow-hidden">
      {/* Floating Messages Counter - fixed position relative to container */}
      {messages.length > 0 && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10
                       opacity-50 hover:opacity-100 px-3 py-1.5 text-xs text-slate-400 hover:text-amber-400
                       bg-slate-800/80 hover:bg-slate-800 backdrop-blur-sm
                       border border-slate-700/50 hover:border-amber-500/50
                       rounded-full flex items-center gap-1.5 transition-all duration-200 cursor-default select-none">
          <EnvelopeIcon />
          {messages.length} {messages.length === 1 ? 'message' : 'messages'}
        </div>
      )}

      {/* Floating action buttons - fixed position relative to container */}
      {messages.length > 0 && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2">
          {/* Copy Chat button */}
          <button
            onClick={handleCopyChat}
            className="opacity-40 hover:opacity-100 px-3 py-1.5 text-xs text-slate-400 hover:text-emerald-400 
                       bg-slate-800/80 hover:bg-slate-800 backdrop-blur-sm
                       border border-slate-700/50 hover:border-emerald-500/50 
                       rounded-full transition-all duration-200 flex items-center gap-1.5 cursor-pointer"
          >
            {copied ? <CheckIcon /> : <CopyIcon />}
            {copied ? 'Copied!' : 'Copy Chat'}
          </button>

          {/* Download Chat button */}
          <button
            onClick={handleDownloadChat}
            className="opacity-40 hover:opacity-100 px-3 py-1.5 text-xs text-slate-400 hover:text-blue-400 
                       bg-slate-800/80 hover:bg-slate-800 backdrop-blur-sm
                       border border-slate-700/50 hover:border-blue-500/50 
                       rounded-full transition-all duration-200 flex items-center gap-1.5 cursor-pointer"
          >
            <DownloadIcon />
            Download
          </button>

          {/* Clear Chat button */}
          <button
            onClick={onClearChat}
            className="opacity-40 hover:opacity-100 px-3 py-1.5 text-xs text-slate-400 hover:text-red-400 
                       bg-slate-800/80 hover:bg-slate-800 backdrop-blur-sm
                       border border-slate-700/50 hover:border-red-500/50 
                       rounded-full transition-all duration-200 flex items-center gap-1.5 cursor-pointer"
          >
            <TrashIcon />
            Clear
          </button>
        </div>
      )}

      {/* Scrollable content area */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
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
              <ChatMessage message={message} onContentChange={scrollToBottom} />
            </div>
          ))}

          {streamingContent && (
            <div className="flex gap-3 mb-5 animate-fade-in">
              <StreamingBotAvatar />
              <div className="flex flex-col items-start max-w-[75%]">
                <div className="rounded-2xl rounded-tl-md px-4 py-3 shadow-md bg-[#2a2d32] text-slate-100 border border-slate-700/50">
                  <div className="relative">
                    <MarkdownRenderer content={streamingContent} isStreaming={true} onContentChange={scrollToBottom} />
                    <span className="inline-block w-2 h-4 bg-emerald-500 ml-1 animate-pulse rounded-sm align-middle" />
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>
    </div>
  );
}
