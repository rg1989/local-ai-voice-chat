import { ConversationSummary } from '../types';

interface ConversationItemProps {
  conversation: ConversationSummary;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

// Format relative time
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Trash icon
function TrashIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  );
}

// Chat icon for conversation
function ChatIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
  );
}

export function ConversationItem({
  conversation,
  isActive,
  onSelect,
  onDelete,
}: ConversationItemProps) {
  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Delete this conversation?')) {
      onDelete();
    }
  };

  return (
    <div
      onClick={onSelect}
      className={`group mx-2 px-3 py-3 rounded-xl cursor-pointer transition-all duration-200 ${
        isActive
          ? 'bg-slate-700/60 border border-slate-600/50'
          : 'hover:bg-slate-700/30 border border-transparent'
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
          isActive 
            ? 'bg-gradient-to-br from-emerald-500 to-teal-600' 
            : 'bg-slate-600'
        }`}>
          <ChatIcon />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h3 className={`text-sm font-medium truncate ${
              isActive ? 'text-white' : 'text-slate-200'
            }`}>
              {conversation.title || 'New Conversation'}
            </h3>
            <span className="text-xs text-slate-500 flex-shrink-0">
              {formatRelativeTime(conversation.updated_at)}
            </span>
          </div>
          
          {conversation.last_message ? (
            <p className="text-xs text-slate-400 truncate mt-1">
              {conversation.last_message.role === 'user' ? 'You: ' : 'AI: '}
              {conversation.last_message.preview}
            </p>
          ) : (
            <p className="text-xs text-slate-500 italic mt-1">No messages yet</p>
          )}
        </div>

        {/* Delete button */}
        <button
          onClick={handleDelete}
          className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all cursor-pointer"
        >
          <TrashIcon />
        </button>
      </div>
    </div>
  );
}
