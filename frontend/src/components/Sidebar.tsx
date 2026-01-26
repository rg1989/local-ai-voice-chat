import { ConversationSummary } from '../types';
import { ConversationItem } from './ConversationItem';

interface SidebarProps {
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  isLoading: boolean;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string, newTitle: string) => void;
  onOpenSettings: (id: string) => void;
  onOpenGlobalSettings: () => void;
  // Model/Voice selectors
  models: string[];
  selectedModel: string;
  onModelChange: (model: string) => void;
  voices: { id: string; name: string }[];
  selectedVoice: string;
  onVoiceChange: (voice: string) => void;
  isDisabled: boolean;
}

// Plus icon for new conversation
function PlusIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}

// Chat bubble icon for empty state
function ChatBubbleIcon() {
  return (
    <svg className="w-12 h-12 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
  );
}

// GitHub icon
function GitHubIcon() {
  return (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
    </svg>
  );
}

// LinkedIn icon
function LinkedInIcon() {
  return (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
    </svg>
  );
}

// Settings icon
function SettingsIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

export function Sidebar({
  conversations,
  activeConversationId,
  isLoading,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
  onOpenSettings,
  onOpenGlobalSettings,
  models,
  selectedModel,
  onModelChange,
  voices,
  selectedVoice,
  onVoiceChange,
  isDisabled,
}: SidebarProps) {
  return (
    <aside className="w-72 bg-[#1e2227] border-r border-slate-700/50 flex flex-col h-screen">
      {/* Header with new conversation button */}
      <div className="p-4 border-b border-slate-700/50">
        <button
          onClick={onNewConversation}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-medium transition-colors cursor-pointer"
        >
          <PlusIcon />
          <span>New Chat</span>
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : conversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
            <ChatBubbleIcon />
            <p className="mt-4 text-slate-400 text-sm">No conversations yet</p>
            <p className="mt-1 text-slate-500 text-xs">Start a new chat to begin</p>
          </div>
        ) : (
          <div className="py-2">
            {conversations.map((conversation) => (
              <ConversationItem
                key={conversation.id}
                conversation={conversation}
                isActive={conversation.id === activeConversationId}
                onSelect={() => onSelectConversation(conversation.id)}
                onDelete={() => onDeleteConversation(conversation.id)}
                onRename={(newTitle) => onRenameConversation(conversation.id, newTitle)}
                onOpenSettings={() => onOpenSettings(conversation.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer with Model/Voice selectors */}
      <div className="p-3 border-t border-slate-700/50 space-y-2">
        {/* Model selector */}
        {models.length > 0 && (
          <div className="flex flex-col gap-1">
            <label className="text-violet-400 text-xs font-medium uppercase tracking-wide px-1">Model</label>
            <select
              value={selectedModel}
              onChange={(e) => onModelChange(e.target.value)}
              disabled={isDisabled}
              className="w-full bg-[#2a2d32] border border-violet-500/30 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30 hover:border-violet-500/50 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors truncate"
            >
              {models.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Voice selector */}
        {voices.length > 0 && (
          <div className="flex flex-col gap-1">
            <label className="text-violet-400 text-xs font-medium uppercase tracking-wide px-1">Voice</label>
            <select
              value={selectedVoice}
              onChange={(e) => onVoiceChange(e.target.value)}
              disabled={isDisabled}
              className="w-full bg-[#2a2d32] border border-violet-500/30 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30 hover:border-violet-500/50 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors"
            >
              {voices.map((voice) => (
                <option key={voice.id} value={voice.id}>
                  {voice.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Settings button */}
        <button
          onClick={onOpenGlobalSettings}
          className="w-full flex items-center justify-center gap-2 px-2 py-1.5 text-violet-400 hover:text-violet-300 hover:bg-violet-500/10 rounded-lg transition-colors cursor-pointer border border-transparent hover:border-violet-500/30"
        >
          <SettingsIcon />
          <span className="text-xs">Settings</span>
        </button>
      </div>

      {/* Author footer */}
      <div className="px-3 py-2 border-t border-slate-700/50">
        <div className="flex items-center justify-center gap-3">
          <span className="text-xs neon-rainbow">by Roman Grinevich</span>
          <div className="flex items-center gap-2">
            <a
              href="https://github.com/rg1989"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-500 hover:text-white transition-colors"
              title="GitHub"
            >
              <GitHubIcon />
            </a>
            <a
              href="https://www.linkedin.com/in/roman-grinevich-03b13bab/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-500 hover:text-[#0A66C2] transition-colors"
              title="LinkedIn"
            >
              <LinkedInIcon />
            </a>
          </div>
        </div>
      </div>
    </aside>
  );
}
