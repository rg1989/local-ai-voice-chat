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

export function Sidebar({
  conversations,
  activeConversationId,
  isLoading,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
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
            <label className="text-slate-500 text-xs font-medium uppercase tracking-wide px-1">Model</label>
            <select
              value={selectedModel}
              onChange={(e) => onModelChange(e.target.value)}
              disabled={isDisabled}
              className="w-full bg-[#2a2d32] border border-slate-600/50 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500/50 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors truncate"
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
            <label className="text-slate-500 text-xs font-medium uppercase tracking-wide px-1">Voice</label>
            <select
              value={selectedVoice}
              onChange={(e) => onVoiceChange(e.target.value)}
              disabled={isDisabled}
              className="w-full bg-[#2a2d32] border border-slate-600/50 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500/50 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors"
            >
              {voices.map((voice) => (
                <option key={voice.id} value={voice.id}>
                  {voice.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
    </aside>
  );
}
