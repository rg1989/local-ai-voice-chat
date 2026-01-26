import { useState, useEffect, useRef } from 'react';
import { ToolInfo } from '../types';

interface GlobalSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  tools: ToolInfo[];
  onToolToggle: (toolName: string, enabled: boolean) => void;
  globalRules: string;
  onSaveGlobalRules: (rules: string) => void;
}

// Close icon
function CloseIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

// Toggle switch component
function Toggle({ 
  enabled, 
  onChange,
  disabled = false 
}: { 
  enabled: boolean; 
  onChange: (enabled: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!enabled)}
      disabled={disabled}
      className={`
        relative inline-flex h-6 w-11 items-center rounded-full transition-colors
        ${enabled ? 'bg-emerald-600' : 'bg-slate-600'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
      `}
    >
      <span
        className={`
          inline-block h-4 w-4 transform rounded-full bg-white transition-transform
          ${enabled ? 'translate-x-6' : 'translate-x-1'}
        `}
      />
    </button>
  );
}

// Tool item component
function ToolItem({
  tool,
  onToggle,
}: {
  tool: ToolInfo;
  onToggle: (enabled: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-slate-700/50 last:border-b-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">{tool.name}</span>
          {tool.requires_confirmation && (
            <span className="px-1.5 py-0.5 text-xs bg-amber-500/20 text-amber-400 rounded">
              requires confirmation
            </span>
          )}
        </div>
        <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">{tool.description}</p>
      </div>
      <Toggle enabled={tool.enabled} onChange={onToggle} />
    </div>
  );
}

export function GlobalSettingsModal({
  isOpen,
  onClose,
  tools,
  onToolToggle,
  globalRules,
  onSaveGlobalRules,
}: GlobalSettingsModalProps) {
  const [rules, setRules] = useState(globalRules);
  const [isSaving, setIsSaving] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Update local state when modal opens or globalRules changes
  useEffect(() => {
    if (isOpen) {
      setRules(globalRules);
    }
  }, [isOpen, globalRules]);

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

  const handleSaveRules = async () => {
    setIsSaving(true);
    try {
      onSaveGlobalRules(rules);
    } finally {
      setIsSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Cmd/Ctrl + Enter to save
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSaveRules();
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
      <div className="relative bg-slate-800 rounded-2xl shadow-2xl w-full max-w-lg mx-4 border border-slate-700/50 max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700/50 shrink-0">
          <div>
            <h2 className="text-lg font-semibold text-white">Global Settings</h2>
            <p className="text-sm text-slate-400 mt-0.5">
              Configure tools and global rules
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Content - scrollable */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
          {/* Tools Section */}
          <div>
            <h3 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              Available Tools
            </h3>
            <div className="bg-slate-900/50 rounded-xl border border-slate-700/50 px-4">
              {tools.length === 0 ? (
                <p className="py-4 text-sm text-slate-500 text-center">No tools available</p>
              ) : (
                tools.map((tool) => (
                  <ToolItem
                    key={tool.name}
                    tool={tool}
                    onToggle={(enabled) => onToolToggle(tool.name, enabled)}
                  />
                ))
              )}
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Disabled tools will not be available to the AI assistant.
            </p>
          </div>

          {/* Global Rules Section */}
          <div>
            <h3 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Global Rules
            </h3>
            <textarea
              ref={textareaRef}
              value={rules}
              onChange={(e) => setRules(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Add global instructions that apply to all chats...

Examples:
• Always be concise in your responses
• You are a helpful coding assistant
• Respond in a friendly tone
• Prefer TypeScript over JavaScript"
              className="w-full h-36 px-4 py-3 bg-slate-900/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/25 resize-none"
            />
            <p className="text-xs text-slate-500 mt-2">
              These rules apply to all conversations. Chat-specific rules take priority.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-700/50 shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
          >
            Close
          </button>
          <button
            onClick={handleSaveRules}
            disabled={isSaving || rules === globalRules}
            className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? 'Saving...' : 'Save Rules'}
          </button>
        </div>
      </div>
    </div>
  );
}
