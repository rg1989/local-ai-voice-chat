import { useState, useCallback, useEffect } from 'react';
import { ConversationSummary, ConversationSettings, Message } from '../types';

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
  renameConversation: (id: string, newTitle: string) => Promise<boolean>;
  refetchConversation: (id: string) => Promise<void>;
  getConversationSettings: (id: string) => Promise<ConversationSettings | null>;
  updateConversationSettings: (id: string, settings: Partial<ConversationSettings>) => Promise<boolean>;
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
          // Only update updated_at if there's a new message
          updated_at: lastMsg ? lastMsg.timestamp.toISOString() : conv.updated_at,
          last_message: lastMsg ? {
            role: lastMsg.role,
            preview: lastMsg.content.slice(0, 100) + (lastMsg.content.length > 100 ? '...' : ''),
            timestamp: lastMsg.timestamp.toISOString(),
          } : null,
        };
      }).sort((a, b) => {
        // Sort by last message timestamp (most recent first)
        // Conversations with no messages go to the bottom
        const aTime = a.last_message?.timestamp || a.created_at;
        const bTime = b.last_message?.timestamp || b.created_at;
        return new Date(bTime).getTime() - new Date(aTime).getTime();
      })
    );
  }, []);

  const renameConversation = useCallback(async (id: string, newTitle: string): Promise<boolean> => {
    try {
      setError(null);
      const response = await fetch(`/api/conversations/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle }),
      });
      
      if (response.ok) {
        setConversations((prev) => 
          prev.map((c) => c.id === id ? { ...c, title: newTitle } : c)
        );
        return true;
      }
      return false;
    } catch (err) {
      console.error('Failed to rename conversation:', err);
      setError('Failed to rename conversation');
      return false;
    }
  }, []);

  // Helper function to sort conversations by last message time
  const sortByLastMessage = (convs: ConversationSummary[]) => {
    return convs.sort((a, b) => {
      const aTime = a.last_message?.timestamp || a.created_at;
      const bTime = b.last_message?.timestamp || b.created_at;
      return new Date(bTime).getTime() - new Date(aTime).getTime();
    });
  };

  const refetchConversation = useCallback(async (id: string): Promise<void> => {
    try {
      const response = await fetch(`/api/conversations/${id}`);
      const data = await response.json();
      
      if (data.conversation) {
        setConversations((prev) => {
          // Check if conversation exists in the list
          const exists = prev.some((c) => c.id === id);
          if (!exists) {
            // Add the conversation if it doesn't exist
            const newConv: ConversationSummary = {
              id: data.conversation.id,
              title: data.conversation.title,
              created_at: data.conversation.created_at,
              updated_at: data.conversation.updated_at,
              message_count: data.conversation.messages?.length || 0,
              last_message: data.conversation.messages?.length > 0 ? {
                role: data.conversation.messages[data.conversation.messages.length - 1].role,
                preview: data.conversation.messages[data.conversation.messages.length - 1].content.slice(0, 100),
                timestamp: data.conversation.messages[data.conversation.messages.length - 1].timestamp,
              } : null,
            };
            return sortByLastMessage([newConv, ...prev]);
          }
          // Update existing conversation
          return sortByLastMessage(prev.map((c) => c.id === id ? {
            ...c,
            title: data.conversation.title,
            updated_at: data.conversation.updated_at,
            message_count: data.conversation.messages?.length || 0,
            last_message: data.conversation.messages?.length > 0 ? {
              role: data.conversation.messages[data.conversation.messages.length - 1].role,
              preview: data.conversation.messages[data.conversation.messages.length - 1].content.slice(0, 100),
              timestamp: data.conversation.messages[data.conversation.messages.length - 1].timestamp,
            } : null,
          } : c));
        });
      }
    } catch (err) {
      console.error('Failed to refetch conversation:', err);
    }
  }, []);

  const getConversationSettings = useCallback(async (id: string): Promise<ConversationSettings | null> => {
    try {
      const response = await fetch(`/api/conversations/${id}/settings`);
      if (response.ok) {
        const data = await response.json();
        return {
          custom_rules: data.custom_rules || '',
        };
      }
      return null;
    } catch (err) {
      console.error('Failed to get conversation settings:', err);
      return null;
    }
  }, []);

  const updateConversationSettings = useCallback(async (
    id: string, 
    settings: Partial<ConversationSettings>
  ): Promise<boolean> => {
    try {
      setError(null);
      const response = await fetch(`/api/conversations/${id}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });
      
      if (response.ok) {
        // Update local state with new custom_rules
        if (settings.custom_rules !== undefined) {
          setConversations((prev) => 
            prev.map((c) => c.id === id 
              ? { ...c, custom_rules: settings.custom_rules } 
              : c
            )
          );
        }
        return true;
      }
      return false;
    } catch (err) {
      console.error('Failed to update conversation settings:', err);
      setError('Failed to update settings');
      return false;
    }
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
    renameConversation,
    refetchConversation,
    getConversationSettings,
    updateConversationSettings,
  };
}
