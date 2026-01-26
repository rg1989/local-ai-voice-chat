import { useState } from 'react';
import { Message } from '../types';
import { formatTime } from '../utils/audioUtils';
import { MarkdownRenderer } from './MarkdownRenderer';

interface ChatMessageProps {
  message: Message;
  onContentChange?: () => void;
}

// Copy icon
function CopyIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  );
}

// Check icon for copy confirmation
function CheckIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  );
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

// Tool icon for tool call messages
function ToolIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

// Check if content is a tool call
function isToolCall(content: string): boolean {
  const trimmed = content.trim();
  // Check for raw JSON tool call pattern
  if (trimmed.match(/^\s*\{[\s\S]*"tool"\s*:\s*"[^"]+"/)) {
    return true;
  }
  // Check for <tool_call> wrapper
  if (trimmed.includes('<tool_call>') && trimmed.includes('</tool_call>')) {
    return true;
  }
  // Check for code block containing tool call
  if (trimmed.match(/```(?:json)?\s*\{[\s\S]*"tool"\s*:/)) {
    return true;
  }
  return false;
}

// Extract tool name from content
function getToolName(content: string): string | null {
  const match = content.match(/"tool"\s*:\s*"([^"]+)"/);
  return match ? match[1] : null;
}

export function ChatMessage({ message, onContentChange }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className={`group flex gap-3 mb-5 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      {isUser ? <UserAvatar /> : <BotAvatar />}

      {/* Message bubble */}
      <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[75%]`}>
        <div
          className={`rounded-2xl px-4 py-3 shadow-md ${
            isUser
              ? 'bg-gradient-to-br from-indigo-600 to-indigo-700 text-white rounded-tr-md'
              : isToolCall(message.content)
                ? 'bg-[#2a2d32] text-slate-100 rounded-tl-md border border-amber-500/50'
                : 'bg-[#2a2d32] text-slate-100 rounded-tl-md border border-slate-700/50'
          }`}
        >
          {isUser ? (
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
          ) : isToolCall(message.content) ? (
            <div>
              <div className="flex items-center gap-2 text-amber-400 text-sm font-medium mb-2">
                <ToolIcon />
                <span>Using tool: {getToolName(message.content) || 'unknown'}</span>
              </div>
              <MarkdownRenderer content={message.content} onContentChange={onContentChange} />
            </div>
          ) : (
            <MarkdownRenderer content={message.content} onContentChange={onContentChange} />
          )}
        </div>
        <div className={`flex items-center gap-2 mt-1.5 px-1 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
          <p className={`text-xs ${isUser ? 'text-slate-400' : 'text-slate-500'}`}>
            {formatTime(message.timestamp)}
          </p>
          <button
            onClick={handleCopy}
            className={`opacity-0 group-hover:opacity-100 transition-opacity text-slate-500 hover:text-slate-300 cursor-pointer ${
              copied ? 'opacity-100' : ''
            }`}
            title="Copy message"
          >
            {copied ? (
              <span className="text-emerald-400 flex items-center gap-1">
                <CheckIcon />
              </span>
            ) : (
              <CopyIcon />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
