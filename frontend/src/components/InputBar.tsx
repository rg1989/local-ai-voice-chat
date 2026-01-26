import { useState, useRef, useEffect, KeyboardEvent, ChangeEvent } from 'react';

interface InputBarProps {
  onSend: (text: string) => void;
  disabled: boolean;
}

export function InputBar({ onSend, disabled }: InputBarProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Only resize when text contains newlines
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      const lineCount = (text.match(/\n/g) || []).length + 1;
      const lineHeight = 20; // approximate line height
      const baseHeight = 36;
      const maxHeight = 100;
      
      if (lineCount > 1) {
        const newHeight = Math.min(baseHeight + (lineCount - 1) * lineHeight, maxHeight);
        textarea.style.height = `${newHeight}px`;
      } else {
        textarea.style.height = `${baseHeight}px`;
      }
    }
  }, [text]);

  const handleSend = () => {
    if (text.trim() && !disabled) {
      onSend(text.trim());
      setText('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Send on Enter without Shift
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    // Shift+Enter allows new line (default behavior)
  };

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
  };

  return (
    <div className="flex gap-2 items-end">
      <textarea
        ref={textareaRef}
        value={text}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder="Type a message..."
        disabled={disabled}
        rows={1}
        className="flex-1 bg-[#2a2d32] border border-slate-600/50 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all resize-none overflow-y-auto"
        style={{ height: '36px', maxHeight: '100px' }}
      />
      <button
        onClick={handleSend}
        disabled={disabled || !text.trim()}
        className="h-9 px-4 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-all cursor-pointer flex items-center gap-1.5 shrink-0 border border-slate-600/50 disabled:border-slate-700/50 disabled:text-slate-500"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
        </svg>
        Send
      </button>
    </div>
  );
}
