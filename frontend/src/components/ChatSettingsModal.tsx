import { useState, useEffect, useRef } from 'react';

interface ChatSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  conversationId: string;
  currentRules: string;
  onSave: (rules: string) => Promise<void>;
}

// Close icon
function CloseIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

export function ChatSettingsModal({
  isOpen,
  onClose,
  conversationId,
  currentRules,
  onSave,
}: ChatSettingsModalProps) {
  const [rules, setRules] = useState(currentRules);
  const [isSaving, setIsSaving] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Update local state when modal opens or currentRules changes
  useEffect(() => {
    if (isOpen) {
      setRules(currentRules);
      // Focus textarea when modal opens
      setTimeout(() => {
        textareaRef.current?.focus();
      }, 100);
    }
  }, [isOpen, currentRules]);

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave(rules);
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Cmd/Ctrl + Enter to save
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-slate-800 rounded-2xl shadow-2xl w-full max-w-lg mx-4 border border-slate-700/50">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700/50">
          <div>
            <h2 className="text-lg font-semibold text-white">Chat Settings</h2>
            <p className="text-sm text-slate-400 mt-0.5">
              Custom rules for this conversation
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Custom Rules
          </label>
          <textarea
            ref={textareaRef}
            value={rules}
            onChange={(e) => setRules(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Add custom instructions for this chat...

Examples:
• Always respond in Spanish
• You are a Python expert
• Keep responses under 100 words
• Explain things simply"
            className="w-full h-48 px-4 py-3 bg-slate-900/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/25 resize-none"
          />
          <p className="text-xs text-slate-500 mt-2">
            These rules will be applied to every response in this chat.
            Press <kbd className="px-1.5 py-0.5 bg-slate-700 rounded text-slate-300">Cmd+Enter</kbd> to save.
          </p>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-700/50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? 'Saving...' : 'Save Rules'}
          </button>
        </div>
      </div>
    </div>
  );
}
