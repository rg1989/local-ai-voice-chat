import { useState, useCallback, useEffect } from 'react';
import { ConversationSummary, Message } from '../types';

interface UseConversationsReturn {
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  isLoading: boolean;
  error: string | null;
  fetchConversations: () => Promise<void>;
  createConversation: () => Promise<string | null>;
  selectConversation: (id: string) => Promise<Message[]>;
  deleteConversation: (id: string) => Promise<boolean>;
  updateConversationMessages: (id: string, messages: Message[]) => void;
}

export function useConversations(): UseConversationsReturn {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConversations = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await fetch('/api/conversations');
      const data = await response.json();
      
      if (data.conversations) {
        setConversations(data.conversations);
      }
    } catch (err) {
      console.error('Failed to fetch conversations:', err);
      setError('Failed to load conversations');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createConversation = useCallback(async (): Promise<string | null> => {
    try {
      setError(null);
      const response = await fetch('/api/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Conversation' }),
      });
      const data = await response.json();
      
      if (data.conversation) {
        const newConv: ConversationSummary = {
          id: data.conversation.id,
          title: data.conversation.title,
          created_at: data.conversation.created_at,
          updated_at: data.conversation.updated_at,
          message_count: 0,
          last_message: null,
        };
        setConversations((prev) => [newConv, ...prev]);
        setActiveConversationId(data.conversation.id);
        return data.conversation.id;
      }
      return null;
    } catch (err) {
      console.error('Failed to create conversation:', err);
      setError('Failed to create conversation');
      return null;
    }
  }, []);

  const selectConversation = useCallback(async (id: string): Promise<Message[]> => {
    try {
      setError(null);
      setActiveConversationId(id);
      
      const response = await fetch(`/api/conversations/${id}`);
      const data = await response.json();
      
      if (data.conversation && data.conversation.messages) {
        // Convert stored messages to frontend Message format
        return data.conversation.messages.map((msg: { id: string; role: string; content: string; timestamp: string }) => ({
          id: msg.id,
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          timestamp: new Date(msg.timestamp),
        }));
      }
      return [];
    } catch (err) {
      console.error('Failed to load conversation:', err);
      setError('Failed to load conversation');
      return [];
    }
  }, []);

  const deleteConversation = useCallback(async (id: string): Promise<boolean> => {
    try {
      setError(null);
      const response = await fetch(`/api/conversations/${id}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        setConversations((prev) => prev.filter((c) => c.id !== id));
        
        // If deleting active conversation, select another one
        if (activeConversationId === id) {
          const remaining = conversations.filter((c) => c.id !== id);
          if (remaining.length > 0) {
            setActiveConversationId(remaining[0].id);
          } else {
            setActiveConversationId(null);
          }
        }
        return true;
      }
      return false;
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      setError('Failed to delete conversation');
      return false;
    }
  }, [activeConversationId, conversations]);

  const updateConversationMessages = useCallback((id: string, messages: Message[]) => {
    setConversations((prev) => 
      prev.map((conv) => {
        if (conv.id !== id) return conv;
        
        const lastMsg = messages.length > 0 ? messages[messages.length - 1] : null;
        return {
          ...conv,
          message_count: messages.length,
          updated_at: new Date().toISOString(),
          last_message: lastMsg ? {
            role: lastMsg.role,
            preview: lastMsg.content.slice(0, 100) + (lastMsg.content.length > 100 ? '...' : ''),
            timestamp: lastMsg.timestamp.toISOString(),
          } : null,
        };
      }).sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    );
  }, []);

  // Initial load
  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  return {
    conversations,
    activeConversationId,
    isLoading,
    error,
    fetchConversations,
    createConversation,
    selectConversation,
    deleteConversation,
    updateConversationMessages,
  };
}
