import { useState, useEffect, useRef } from 'react';
import { MemoryEntry, ConversationSummary } from '../types';
import { ConfirmModal } from './ConfirmModal';

interface MemoryExplorerModalProps {
  isOpen: boolean;
  onClose: () => void;
  memories: MemoryEntry[];
  conversations: ConversationSummary[];
  onAddMemory: (content: string, tags: string[]) => void;
  onDeleteMemory: (memoryId: string) => void;
  onUpdateMemory: (memoryId: string, content: string, tags: string[]) => void;
  onRefresh: () => void;
}

// Icons
function CloseIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function BrainIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  );
}

function EditIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  );
}

// Tag colors for visual distinction
const TAG_COLORS = [
  'bg-violet-500/20 text-violet-300 border-violet-500/30',
  'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  'bg-amber-500/20 text-amber-300 border-amber-500/30',
  'bg-pink-500/20 text-pink-300 border-pink-500/30',
  'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  'bg-blue-500/20 text-blue-300 border-blue-500/30',
];

function getTagColor(tag: string): string {
  // Use consistent color based on tag string
  const hash = tag.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return TAG_COLORS[hash % TAG_COLORS.length];
}

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  
  if (diffDays === 0) {
    return 'Today';
  } else if (diffDays === 1) {
    return 'Yesterday';
  } else if (diffDays < 7) {
    return `${diffDays} days ago`;
  } else {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
}

// Memory card component
function MemoryCard({
  memory,
  conversationTitle,
  onEdit,
  onDelete,
}: {
  memory: MemoryEntry;
  conversationTitle?: string;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="group bg-slate-900/50 border border-slate-700/50 rounded-xl p-4 hover:border-violet-500/30 transition-all">
      {/* Content */}
      <p className="text-sm text-white leading-relaxed mb-3">{memory.content}</p>
      
      {/* Tags */}
      {memory.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {memory.tags.map((tag, idx) => (
            <span
              key={idx}
              className={`px-2 py-0.5 text-xs rounded-full border ${getTagColor(tag)}`}
            >
              {tag}
            </span>
          ))}
        </div>
      )}
      
      {/* Footer */}
      <div className="flex items-center justify-between">
        <div className="text-xs text-slate-500">
          <span>{formatDate(memory.created_at)}</span>
          {conversationTitle && (
            <>
              <span className="mx-1.5">•</span>
              <span className="text-slate-400">from "{conversationTitle.slice(0, 25)}{conversationTitle.length > 25 ? '...' : ''}"</span>
            </>
          )}
        </div>
        
        {/* Actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={onEdit}
            className="p-1.5 text-slate-400 hover:text-violet-400 hover:bg-violet-500/10 rounded-lg transition-colors cursor-pointer"
            title="Edit memory"
          >
            <EditIcon />
          </button>
          <button
            onClick={onDelete}
            className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors cursor-pointer"
            title="Delete memory"
          >
            <TrashIcon />
          </button>
        </div>
      </div>
    </div>
  );
}

// Add/Edit memory form
function MemoryForm({
  initialContent,
  initialTags,
  onSave,
  onCancel,
  isEditing,
}: {
  initialContent?: string;
  initialTags?: string[];
  onSave: (content: string, tags: string[]) => void;
  onCancel: () => void;
  isEditing?: boolean;
}) {
  const [content, setContent] = useState(initialContent || '');
  const [tagsInput, setTagsInput] = useState(initialTags?.join(', ') || '');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;
    
    const tags = tagsInput
      .split(',')
      .map(t => t.trim().toLowerCase())
      .filter(t => t.length > 0);
    
    onSave(content.trim(), tags);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-slate-900/50 border border-violet-500/30 rounded-xl p-4 mb-4">
      <textarea
        ref={inputRef}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="What would you like to remember?"
        className="w-full h-20 px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 resize-none"
      />
      
      <input
        type="text"
        value={tagsInput}
        onChange={(e) => setTagsInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Tags (comma-separated, e.g., personal, preferences)"
        className="w-full mt-2 px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-violet-500"
      />
      
      <div className="flex items-center justify-end gap-2 mt-3">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-sm text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors cursor-pointer"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={!content.trim()}
          className="px-3 py-1.5 text-sm font-medium text-white bg-violet-600 hover:bg-violet-500 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
        >
          {isEditing ? 'Update Memory' : 'Save Memory'}
        </button>
      </div>
    </form>
  );
}

export function MemoryExplorerModal({
  isOpen,
  onClose,
  memories,
  conversations,
  onAddMemory,
  onDeleteMemory,
  onUpdateMemory,
  onRefresh,
}: MemoryExplorerModalProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [isAdding, setIsAdding] = useState(false);
  const [editingMemoryId, setEditingMemoryId] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        if (isAdding) {
          setIsAdding(false);
        } else if (editingMemoryId) {
          setEditingMemoryId(null);
        } else {
          onClose();
        }
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose, isAdding, editingMemoryId]);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setSearchQuery('');
      setIsAdding(false);
      setEditingMemoryId(null);
      onRefresh();
    }
  }, [isOpen, onRefresh]);

  // Filter memories by search query
  const filteredMemories = memories.filter(memory => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      memory.content.toLowerCase().includes(query) ||
      memory.tags.some(tag => tag.toLowerCase().includes(query))
    );
  });

  // Get conversation title for a memory
  const getConversationTitle = (conversationId: string | null): string | undefined => {
    if (!conversationId) return undefined;
    return conversations.find(c => c.id === conversationId)?.title;
  };

  const handleAddMemory = (content: string, tags: string[]) => {
    onAddMemory(content, tags);
    setIsAdding(false);
  };

  const handleUpdateMemory = (content: string, tags: string[]) => {
    if (editingMemoryId) {
      onUpdateMemory(editingMemoryId, content, tags);
      setEditingMemoryId(null);
    }
  };

  const handleDeleteConfirm = () => {
    if (deleteConfirmId) {
      onDeleteMemory(deleteConfirmId);
      setDeleteConfirmId(null);
    }
  };

  const editingMemory = editingMemoryId ? memories.find(m => m.id === editingMemoryId) : null;

  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        {/* Backdrop */}
        <div 
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        />
        
        {/* Modal */}
        <div className="relative bg-slate-800 rounded-2xl shadow-2xl w-full max-w-2xl mx-4 border border-slate-700/50 max-h-[85vh] flex flex-col animate-fade-in">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-violet-500/20 shrink-0">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-violet-500/10 rounded-xl text-violet-400">
                <BrainIcon />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Memory Explorer</h2>
                <p className="text-sm text-slate-400">
                  {memories.length} memor{memories.length === 1 ? 'y' : 'ies'} stored
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={onRefresh}
                className="p-2 text-slate-400 hover:text-violet-400 hover:bg-violet-500/10 rounded-lg transition-colors cursor-pointer"
                title="Refresh memories"
              >
                <RefreshIcon />
              </button>
              <button
                onClick={onClose}
                className="p-2 text-slate-400 hover:text-violet-400 hover:bg-violet-500/10 rounded-lg transition-colors cursor-pointer"
              >
                <CloseIcon />
              </button>
            </div>
          </div>

          {/* Search and Add */}
          <div className="px-6 py-4 border-b border-slate-700/50 shrink-0">
            <div className="flex items-center gap-3">
              {/* Search */}
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search memories..."
                  className="w-full pl-10 pr-4 py-2 bg-slate-900/50 border border-slate-700/50 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-violet-500/50"
                />
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">
                  <SearchIcon />
                </div>
              </div>
              
              {/* Add Button */}
              <button
                onClick={() => setIsAdding(true)}
                disabled={isAdding}
                className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                <PlusIcon />
                Add Memory
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {/* Add Form */}
            {isAdding && (
              <MemoryForm
                onSave={handleAddMemory}
                onCancel={() => setIsAdding(false)}
              />
            )}

            {/* Edit Form */}
            {editingMemory && (
              <MemoryForm
                initialContent={editingMemory.content}
                initialTags={editingMemory.tags}
                onSave={handleUpdateMemory}
                onCancel={() => setEditingMemoryId(null)}
                isEditing
              />
            )}

            {/* Memory List */}
            {filteredMemories.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="p-4 bg-slate-900/50 rounded-full mb-4">
                  <BrainIcon />
                </div>
                {memories.length === 0 ? (
                  <>
                    <h3 className="text-white font-medium mb-2">No memories yet</h3>
                    <p className="text-sm text-slate-400 max-w-sm">
                      Ask the AI to remember something, or click "Add Memory" to manually add information that will be available across all your conversations.
                    </p>
                  </>
                ) : (
                  <>
                    <h3 className="text-white font-medium mb-2">No matches found</h3>
                    <p className="text-sm text-slate-400">
                      Try a different search term
                    </p>
                  </>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                {filteredMemories.map((memory) => (
                  <MemoryCard
                    key={memory.id}
                    memory={memory}
                    conversationTitle={getConversationTitle(memory.source_conversation_id)}
                    onEdit={() => setEditingMemoryId(memory.id)}
                    onDelete={() => setDeleteConfirmId(memory.id)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-violet-500/20 shrink-0">
            <p className="text-xs text-slate-500 text-center">
              Memories are shared across all conversations. Ask the AI to "remember" something to add it here automatically.
            </p>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={deleteConfirmId !== null}
        onClose={() => setDeleteConfirmId(null)}
        onConfirm={handleDeleteConfirm}
        title="Delete Memory"
        message="Are you sure you want to delete this memory? This action cannot be undone."
        confirmText="Delete"
        variant="danger"
      />
    </>
  );
}
