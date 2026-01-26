import { SearchResult } from '../types';

interface SearchResultsListProps {
  results: SearchResult[];
  query: string;
  isSearching: boolean;
  hasSearched: boolean;
  activeConversationId: string | null;
  onSelectResult: (conversationId: string, messageIndex: number, messageId: string) => void;
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

// Search icon
function SearchIcon() {
  return (
    <svg className="w-12 h-12 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
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

// Highlight matching text in context
function HighlightedText({ text, query }: { text: string; query: string }) {
  if (!query.trim()) {
    return <span>{text}</span>;
  }

  // Escape special regex characters
  const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${escapedQuery})`, 'gi');
  const parts = text.split(regex);

  return (
    <span>
      {parts.map((part, index) => {
        if (part.toLowerCase() === query.toLowerCase()) {
          return (
            <mark 
              key={index} 
              className="bg-emerald-500/30 text-emerald-200 rounded px-0.5"
            >
              {part}
            </mark>
          );
        }
        return <span key={index}>{part}</span>;
      })}
    </span>
  );
}

export function SearchResultsList({
  results,
  query,
  isSearching,
  hasSearched,
  activeConversationId,
  onSelectResult,
}: SearchResultsListProps) {
  // Loading state
  if (isSearching && !hasSearched) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // No results state
  if (hasSearched && results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
        <SearchIcon />
        <p className="mt-4 text-slate-400 text-sm">No matches found</p>
        <p className="mt-1 text-slate-500 text-xs">Try a different search term</p>
      </div>
    );
  }

  // Results list
  return (
    <div className="py-2">
      {/* Results count header */}
      <div className="px-4 py-2 text-xs text-slate-500">
        {results.reduce((sum, r) => sum + r.total_matches, 0)} matches in {results.length} conversation{results.length !== 1 ? 's' : ''}
      </div>

      {results.map((result) => {
        const isActive = result.conversation_id === activeConversationId;
        const firstMatch = result.matches[0];
        
        return (
          <div
            key={result.conversation_id}
            className="mx-2 mb-1"
          >
            {/* Conversation header */}
            <div
              onClick={() => {
                if (firstMatch) {
                  onSelectResult(result.conversation_id, firstMatch.message_index, firstMatch.message_id);
                }
              }}
              className={`group px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200 ${
                isActive
                  ? 'bg-slate-700/60 border border-slate-600/50'
                  : 'hover:bg-slate-700/30 border border-transparent'
              }`}
            >
              <div className="flex items-start gap-3">
                {/* Avatar */}
                <div className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${
                  isActive 
                    ? 'bg-linear-to-br from-emerald-500 to-teal-600' 
                    : 'bg-slate-600'
                }`}>
                  <ChatIcon />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  {/* Title row with match count */}
                  <div className="flex items-center gap-2">
                    <h3 className={`text-sm font-medium truncate flex-1 ${
                      isActive ? 'text-white' : 'text-slate-200'
                    }`}>
                      <HighlightedText text={result.title} query={result.title_match ? query : ''} />
                    </h3>
                    <span className="shrink-0 px-1.5 py-0.5 text-xs font-medium bg-emerald-500/20 text-emerald-400 rounded">
                      {result.total_matches}
                    </span>
                  </div>

                  {/* First match preview */}
                  {firstMatch && (
                    <div className="mt-1.5">
                      <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-0.5">
                        <span className={firstMatch.role === 'user' ? 'text-violet-400' : 'text-emerald-400'}>
                          {firstMatch.role === 'user' ? 'You' : 'Assistant'}
                        </span>
                        <span>·</span>
                        <span>{formatRelativeTime(firstMatch.timestamp)}</span>
                      </div>
                      <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                        <HighlightedText text={firstMatch.context} query={query} />
                      </p>
                    </div>
                  )}

                  {/* More matches indicator */}
                  {result.total_matches > 1 && (
                    <p className="mt-1.5 text-xs text-slate-500">
                      + {result.total_matches - 1} more match{result.total_matches > 2 ? 'es' : ''}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Additional matches (expandable in future, showing first few for now) */}
            {result.matches.length > 1 && (
              <div className="ml-12 mt-1 space-y-1">
                {result.matches.slice(1, 3).map((match) => (
                  <div
                    key={match.message_id}
                    onClick={() => onSelectResult(result.conversation_id, match.message_index, match.message_id)}
                    className="px-3 py-2 rounded-lg hover:bg-slate-700/20 cursor-pointer transition-colors"
                  >
                    <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-0.5">
                      <span className={match.role === 'user' ? 'text-violet-400' : 'text-emerald-400'}>
                        {match.role === 'user' ? 'You' : 'Assistant'}
                      </span>
                      <span>·</span>
                      <span>{formatRelativeTime(match.timestamp)}</span>
                    </div>
                    <p className="text-xs text-slate-400 line-clamp-1">
                      <HighlightedText text={match.context} query={query} />
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
