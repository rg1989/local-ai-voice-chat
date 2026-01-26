import { useCallback, useEffect, useRef, useState } from 'react';
import { WSMessage } from '../types';

interface UseWebSocketOptions {
  onMessage: (message: WSMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
}

export function useWebSocket({ onMessage, onOpen, onClose, onError }: UseWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/chat`);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      onOpen?.();
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      onClose?.();

      // Attempt reconnection after 3 seconds
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      onError?.(error);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WSMessage;
        onMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    wsRef.current = ws;
  }, [onMessage, onOpen, onClose, onError]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const sendJson = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const sendBinary = useCallback((data: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  const sendTextMessage = useCallback((text: string) => {
    sendJson({ type: 'text', text });
  }, [sendJson]);

  const sendStop = useCallback(() => {
    sendJson({ type: 'stop' });
  }, [sendJson]);

  const sendClearHistory = useCallback(() => {
    sendJson({ type: 'clear_history' });
  }, [sendJson]);

  const sendSetVoice = useCallback((voice: string) => {
    sendJson({ type: 'set_voice', voice });
  }, [sendJson]);

  const sendSetModel = useCallback((model: string) => {
    sendJson({ type: 'set_model', model });
  }, [sendJson]);

  const sendSetConversation = useCallback((conversationId: string) => {
    sendJson({ type: 'set_conversation', conversation_id: conversationId });
  }, [sendJson]);

  const sendSetTtsEnabled = useCallback((enabled: boolean) => {
    sendJson({ type: 'set_tts_enabled', enabled });
  }, [sendJson]);

  const sendSetCustomRules = useCallback((rules: string) => {
    sendJson({ type: 'set_custom_rules', rules });
  }, [sendJson]);

  const sendGetTools = useCallback(() => {
    sendJson({ type: 'get_tools' });
  }, [sendJson]);

  const sendSetToolEnabled = useCallback((tool: string, enabled: boolean) => {
    sendJson({ type: 'set_tool_enabled', tool, enabled });
  }, [sendJson]);

  const sendSetGlobalRules = useCallback((rules: string) => {
    sendJson({ type: 'set_global_rules', rules });
  }, [sendJson]);

  const sendGetWakeWordSettings = useCallback(() => {
    sendJson({ type: 'get_wakeword_settings' });
  }, [sendJson]);

  const sendSetWakeWordSettings = useCallback((settings: {
    enabled?: boolean;
    model?: string;
    threshold?: number;
    timeoutSeconds?: number;
  }) => {
    sendJson({ type: 'set_wakeword_settings', ...settings });
  }, [sendJson]);

  // Memory functions
  const sendGetMemories = useCallback((query?: string) => {
    sendJson({ type: 'get_memories', query: query || '' });
  }, [sendJson]);

  const sendAddMemory = useCallback((content: string, tags: string[]) => {
    sendJson({ type: 'add_memory', content, tags });
  }, [sendJson]);

  const sendDeleteMemory = useCallback((memoryId: string) => {
    sendJson({ type: 'delete_memory', memory_id: memoryId });
  }, [sendJson]);

  const sendUpdateMemory = useCallback((memoryId: string, content: string, tags: string[]) => {
    sendJson({ type: 'update_memory', memory_id: memoryId, content, tags });
  }, [sendJson]);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    isConnected,
    sendJson,
    sendBinary,
    sendTextMessage,
    sendStop,
    sendClearHistory,
    sendSetVoice,
    sendSetModel,
    sendSetConversation,
    sendSetTtsEnabled,
    sendSetCustomRules,
    sendGetTools,
    sendSetToolEnabled,
    sendSetGlobalRules,
    sendGetWakeWordSettings,
    sendSetWakeWordSettings,
    sendGetMemories,
    sendAddMemory,
    sendDeleteMemory,
    sendUpdateMemory,
  };
}
