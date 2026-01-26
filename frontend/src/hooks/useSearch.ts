import { useState, useCallback, useRef, useEffect } from 'react';
import { SearchResult } from '../types';

interface UseSearchReturn {
  query: string;
  setQuery: (query: string) => void;
  results: SearchResult[];
  isSearching: boolean;
  clearSearch: () => void;
  hasSearched: boolean;
}

const DEBOUNCE_DELAY = 300;

export function useSearch(): UseSearchReturn {
  const [query, setQueryState] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  
  const debounceTimerRef = useRef<number | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const performSearch = useCallback(async (searchQuery: string) => {
    // Cancel any pending request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    if (!searchQuery.trim()) {
      setResults([]);
      setIsSearching(false);
      setHasSearched(false);
      return;
    }

    setIsSearching(true);
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(
        `/api/conversations/search?q=${encodeURIComponent(searchQuery.trim())}`,
        { signal: abortControllerRef.current.signal }
      );
      
      if (!response.ok) {
        throw new Error('Search failed');
      }

      const data = await response.json();
      setResults(data.results || []);
      setHasSearched(true);
    } catch (error) {
      // Ignore abort errors
      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }
      console.error('Search error:', error);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  }, []);

  const setQuery = useCallback((newQuery: string) => {
    setQueryState(newQuery);
    
    // Clear existing debounce timer
    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
    }

    // If empty, clear immediately
    if (!newQuery.trim()) {
      setResults([]);
      setIsSearching(false);
      setHasSearched(false);
      return;
    }

    // Set loading state immediately for feedback
    setIsSearching(true);

    // Debounce the actual search
    debounceTimerRef.current = window.setTimeout(() => {
      performSearch(newQuery);
    }, DEBOUNCE_DELAY);
  }, [performSearch]);

  const clearSearch = useCallback(() => {
    setQueryState('');
    setResults([]);
    setIsSearching(false);
    setHasSearched(false);
    
    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        window.clearTimeout(debounceTimerRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    query,
    setQuery,
    results,
    isSearching,
    clearSearch,
    hasSearched,
  };
}
