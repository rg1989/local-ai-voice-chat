import { memo, useCallback, useEffect, useRef, useState } from 'react';
import { Message, AppState } from '../types';
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
  state: AppState;
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

// Robot icon SVG (shared by bot avatars)
function RobotIcon() {
  return (
    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      {/* Robot head */}
      <rect x="5" y="8" width="14" height="10" rx="2" strokeWidth={1.5} />
      {/* Antenna */}
      <line x1="12" y1="8" x2="12" y2="5" strokeWidth={1.5} strokeLinecap="round" />
      <circle cx="12" cy="4" r="1" fill="currentColor" />
      {/* Eyes */}
      <circle cx="9" cy="12" r="1.5" fill="currentColor" />
      <circle cx="15" cy="12" r="1.5" fill="currentColor" />
      {/* Mouth */}
      <line x1="9" y1="15" x2="15" y2="15" strokeWidth={1.5} strokeLinecap="round" />
    </svg>
  );
}

// Bot avatar for streaming
function StreamingBotAvatar() {
  return (
    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shrink-0 shadow-lg shadow-emerald-500/20">
      <RobotIcon />
    </div>
  );
}

// Bot avatar with thinking/loading animation
function ThinkingBotAvatar() {
  return (
    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shrink-0 shadow-lg shadow-emerald-500/20 animate-pulse">
      <RobotIcon />
    </div>
  );
}

// User avatar with transcribing animation
function TranscribingUserAvatar() {
  return (
    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shrink-0 shadow-lg shadow-violet-500/30 animate-pulse">
      <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
    </div>
  );
}

// Typing dots animation
function TypingDots() {
  return (
    <div className="flex items-center gap-1">
      <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
      <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
      <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
    </div>
  );
}

// Tool icon for streaming tool calls
function ToolIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

// Check if content is a tool call
function isStreamingToolCall(content: string): boolean {
  return content.includes('"tool"') && content.includes('"args"');
}

// Extract tool name from streaming content
function getStreamingToolName(content: string): string | null {
  const match = content.match(/"tool"\s*:\s*"([^"]+)"/);
  return match ? match[1] : null;
}

// Extract tool arguments from streaming content
function getStreamingToolArgs(content: string): Record<string, unknown> | null {
  // Match the args object - handles nested objects by finding balanced braces
  const argsMatch = content.match(/"args"\s*:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})/);
  if (argsMatch) {
    try {
      const args = JSON.parse(argsMatch[1]);
      // Return null if args is empty
      if (Object.keys(args).length === 0) {
        return null;
      }
      return args;
    } catch {
      return null;
    }
  }
  return null;
}

// Format args for display
function formatStreamingArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
    .join(', ');
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

export const ChatMessages = memo(function ChatMessages({ 
  messages, 
  streamingContent,
  isListening,
  onToggleListening,
  onClearChat,
  isDisabled,
  state,
}: ChatMessagesProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  // Memoize scrollToBottom to prevent child re-renders
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  // Scroll when messages change, streaming content changes, or state changes
  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent, state, scrollToBottom]);
  
  // Check if we should show the transcribing indicator (user avatar with "Transcribing...")
  const isTranscribing = state === AppState.TRANSCRIBING;
  
  // Check if we should show the thinking indicator (LLM avatar with dots)
  const isThinking = state === AppState.THINKING && !streamingContent;

  // Format messages for export - memoized
  const formatMessagesForExport = useCallback(() => {
    return messages.map(msg => {
      const role = msg.role === 'user' ? 'User' : 'Assistant';
      const time = formatTime(msg.timestamp);
      return `${role} (${time}):\n${msg.content}\n`;
    }).join('\n---\n\n');
  }, [messages]);

  // Copy entire chat to clipboard - memoized
  const handleCopyChat = useCallback(async () => {
    try {
      const text = formatMessagesForExport();
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy chat:', err);
    }
  }, [formatMessagesForExport]);

  // Download chat as markdown file - memoized
  const handleDownloadChat = useCallback(() => {
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
  }, [formatMessagesForExport]);

  return (
    <div className="flex-1 flex flex-col bg-[#15181c] relative overflow-hidden">
      {/* Recording Overlay - shown when listening */}
      {isListening && (
        <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-black/70 backdrop-blur-sm">
          {/* Pulsing microphone icon */}
          <div className="relative mb-8">
            <div className="absolute inset-0 bg-emerald-500/30 rounded-full animate-ping" />
            <div className="relative w-32 h-32 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-2xl shadow-emerald-500/40">
              <svg className="w-16 h-16 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            </div>
          </div>

          {/* Recording text with animated waves */}
          <div className="flex items-center gap-3 mb-8">
            <div className="flex items-center gap-1">
              <div className="w-1 h-4 bg-emerald-400 rounded-full animate-wave" style={{ animationDelay: '0ms' }} />
              <div className="w-1 h-6 bg-emerald-400 rounded-full animate-wave" style={{ animationDelay: '100ms' }} />
              <div className="w-1 h-8 bg-emerald-400 rounded-full animate-wave" style={{ animationDelay: '200ms' }} />
              <div className="w-1 h-6 bg-emerald-400 rounded-full animate-wave" style={{ animationDelay: '300ms' }} />
              <div className="w-1 h-4 bg-emerald-400 rounded-full animate-wave" style={{ animationDelay: '400ms' }} />
            </div>
            <h2 className="text-3xl font-bold text-white">Recording</h2>
            <div className="flex items-center gap-1">
              <div className="w-1 h-4 bg-emerald-400 rounded-full animate-wave" style={{ animationDelay: '400ms' }} />
              <div className="w-1 h-6 bg-emerald-400 rounded-full animate-wave" style={{ animationDelay: '300ms' }} />
              <div className="w-1 h-8 bg-emerald-400 rounded-full animate-wave" style={{ animationDelay: '200ms' }} />
              <div className="w-1 h-6 bg-emerald-400 rounded-full animate-wave" style={{ animationDelay: '100ms' }} />
              <div className="w-1 h-4 bg-emerald-400 rounded-full animate-wave" style={{ animationDelay: '0ms' }} />
            </div>
          </div>

          <p className="text-slate-300 text-lg mb-8">Speak now... the assistant will respond when you pause.</p>

          {/* Stop recording button */}
          <button
            onClick={onToggleListening}
            className="px-8 py-4 bg-red-600 hover:bg-red-700 text-white text-lg font-semibold rounded-xl 
                       transition-all duration-200 flex items-center gap-3 shadow-xl shadow-red-500/30
                       hover:scale-105 cursor-pointer"
          >
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
            Stop Recording
          </button>
        </div>
      )}

      {/* Floating Messages Counter - fixed position relative to container */}
      {messages.length > 0 && !isListening && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10
                       opacity-50 hover:opacity-100 px-3 py-1.5 text-xs text-slate-400 hover:text-violet-400
                       bg-slate-800/80 hover:bg-slate-800 backdrop-blur-sm
                       border border-slate-700/50 hover:border-violet-500/50
                       rounded-full flex items-center gap-1.5 transition-all duration-200 cursor-default select-none">
          <EnvelopeIcon />
          {messages.length} {messages.length === 1 ? 'message' : 'messages'}
        </div>
      )}

      {/* Floating action buttons - fixed position relative to container (hidden during recording) */}
      {messages.length > 0 && !isListening && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2">
          {/* Copy Chat button */}
          <button
            onClick={handleCopyChat}
            className="opacity-40 hover:opacity-100 px-3 py-1.5 text-xs text-slate-400 hover:text-violet-400 
                       bg-slate-800/80 hover:bg-slate-800 backdrop-blur-sm
                       border border-slate-700/50 hover:border-violet-500/50 
                       rounded-full transition-all duration-200 flex items-center gap-1.5 cursor-pointer"
          >
            {copied ? <CheckIcon /> : <CopyIcon />}
            {copied ? 'Copied!' : 'Copy Chat'}
          </button>

          {/* Download Chat button */}
          <button
            onClick={handleDownloadChat}
            className="opacity-40 hover:opacity-100 px-3 py-1.5 text-xs text-slate-400 hover:text-violet-400 
                       bg-slate-800/80 hover:bg-slate-800 backdrop-blur-sm
                       border border-slate-700/50 hover:border-violet-500/50 
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

          {/* Transcribing indicator - show user avatar when speech is being converted to text */}
          {isTranscribing && (
            <div className="flex gap-3 mb-5 animate-fade-in flex-row-reverse">
              <TranscribingUserAvatar />
              <div className="flex flex-col items-end max-w-[75%]">
                <div className="rounded-2xl rounded-tr-md px-4 py-3 shadow-md bg-gradient-to-br from-indigo-600 to-indigo-700 text-white border border-indigo-500/50">
                  <div className="flex items-center gap-2 text-sm">
                    <svg className="w-4 h-4 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                    </svg>
                    <span>Transcribing...</span>
                    <div className="flex items-center gap-1">
                      <div className="w-1.5 h-1.5 bg-white/70 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-1.5 h-1.5 bg-white/70 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-1.5 h-1.5 bg-white/70 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {streamingContent && (
            <div className="flex gap-3 mb-5 animate-fade-in">
              <StreamingBotAvatar />
              <div className="flex flex-col items-start max-w-[75%]">
                <div className={`rounded-2xl rounded-tl-md px-4 py-3 bg-[#2a2d32] text-slate-100 ${
                  isStreamingToolCall(streamingContent) 
                    ? 'border border-amber-500/50 shadow-lg shadow-amber-500/10' 
                    : 'border border-emerald-500/20 shadow-lg shadow-emerald-500/10'
                }`}>
                  {isStreamingToolCall(streamingContent) ? (
                    <div>
                      <div className="flex items-center gap-2 text-amber-400 text-sm font-medium">
                        <ToolIcon />
                        <span>Using tool: {getStreamingToolName(streamingContent) || '...'}()</span>
                        <span className="inline-block w-2 h-4 bg-amber-500 animate-pulse rounded-sm" />
                      </div>
                      {getStreamingToolArgs(streamingContent) && (
                        <div className="mt-2 text-xs text-slate-400 font-mono bg-slate-800/50 rounded px-2 py-1">
                          {formatStreamingArgs(getStreamingToolArgs(streamingContent)!)}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="relative">
                      <MarkdownRenderer content={streamingContent} isStreaming={true} onContentChange={scrollToBottom} />
                      <span className="inline-block w-2 h-4 bg-emerald-500 ml-1 animate-pulse rounded-sm align-middle" />
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Thinking indicator - show LLM avatar when processing, before streaming starts */}
          {isThinking && (
            <div className="flex gap-3 mb-5 animate-fade-in">
              <ThinkingBotAvatar />
              <div className="flex flex-col items-start max-w-[75%]">
                <div className="rounded-2xl rounded-tl-md px-4 py-3 shadow-md bg-[#2a2d32] text-slate-100 border border-slate-700/50">
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-slate-400">Thinking...</span>
                    <TypingDots />
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
});
