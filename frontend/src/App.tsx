import { useState, useCallback, useEffect, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatHeader } from './components/ChatHeader';
import { StatusBar } from './components/StatusBar';
import { ChatMessages } from './components/ChatMessages';
import { ControlBar } from './components/ControlBar';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioStream } from './hooks/useAudioStream';
import { useConversations } from './hooks/useConversations';
import { AppState, Message, WSMessage, ConversationSummary } from './types';
import { generateId } from './utils/audioUtils';

// Voice mapping for display
const VOICE_MAP: Record<string, string> = {
  af_heart: 'Heart (American Female)',
  af_bella: 'Bella (American Female)',
  af_nicole: 'Nicole (American Female)',
  af_sarah: 'Sarah (American Female)',
  af_sky: 'Sky (American Female)',
  am_adam: 'Adam (American Male)',
  am_michael: 'Michael (American Male)',
  bf_emma: 'Emma (British Female)',
  bf_isabella: 'Isabella (British Female)',
  bm_george: 'George (British Male)',
  bm_lewis: 'Lewis (British Male)',
};

interface OllamaStatus {
  available: boolean;
  models: string[];
  currentModel: string;
  error?: string;
}

function App() {
  const [state, setState] = useState<AppState>(AppState.IDLE);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingContent, setStreamingContent] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState('af_heart');
  const [voices, setVoices] = useState<{ id: string; name: string }[]>([]);
  
  // Ollama/Model state
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus>({
    available: true,
    models: [],
    currentModel: '',
  });
  const [selectedModel, setSelectedModel] = useState('');
  
  // Toast notification state
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Conversation management
  const {
    conversations,
    activeConversationId,
    isLoading: isLoadingConversations,
    createConversation,
    selectConversation,
    deleteConversation,
    updateConversationMessages,
  } = useConversations();

  const currentUserMessageRef = useRef<string>('');
  const isListeningRef = useRef(false);
  const streamingContentRef = useRef('');
  const hasInitializedConversation = useRef(false);

  // Keep ref in sync with state for use in callbacks
  useEffect(() => {
    streamingContentRef.current = streamingContent;
  }, [streamingContent]);

  // Handle WebSocket messages
  const handleMessage = useCallback((message: WSMessage) => {
    switch (message.type) {
      case 'status':
        handleStatusUpdate(message.status);
        break;
      case 'transcription':
        // Add user message
        currentUserMessageRef.current = message.text;
        setMessages((prev) => {
          const newMessages = [
            ...prev,
            {
              id: generateId(),
              role: 'user' as const,
              content: message.text,
              timestamp: new Date(),
            },
          ];
          return newMessages;
        });
        break;
      case 'response_token':
        setStreamingContent((prev) => prev + message.token);
        break;
      case 'response_end':
        // Move streaming content to final message
        setMessages((prev) => {
          const newMessages = [
            ...prev,
            {
              id: generateId(),
              role: 'assistant' as const,
              content: streamingContentRef.current,
              timestamp: new Date(),
            },
          ];
          return newMessages;
        });
        setStreamingContent('');
        break;
      case 'audio':
        playAudio(message.audio, message.sample_rate);
        break;
    }
  }, []);

  const handleStatusUpdate = useCallback((status: string) => {
    switch (status) {
      case 'ready':
      case 'listening':
        if (isListeningRef.current) {
          setState(AppState.LISTENING);
        } else {
          setState(AppState.IDLE);
        }
        break;
      case 'transcribing':
        setState(AppState.TRANSCRIBING);
        break;
      case 'thinking':
        setState(AppState.THINKING);
        break;
      case 'speaking':
        setState(AppState.SPEAKING);
        break;
      case 'stopped':
        // Clear streaming content on stop
        if (streamingContentRef.current) {
          setMessages((prev) => [
            ...prev,
            {
              id: generateId(),
              role: 'assistant',
              content: streamingContentRef.current + ' [stopped]',
              timestamp: new Date(),
            },
          ]);
          setStreamingContent('');
        }
        break;
      case 'history_cleared':
        setMessages([]);
        setStreamingContent('');
        break;
    }
  }, []);

  const { isConnected, sendBinary, sendTextMessage, sendStop, sendClearHistory, sendSetVoice, sendSetModel, sendSetConversation } =
    useWebSocket({
      onMessage: handleMessage,
    });

  const handleAudioChunk = useCallback(
    (data: ArrayBuffer) => {
      if (isListeningRef.current) {
        sendBinary(data);
      }
    },
    [sendBinary]
  );

  const { startListening, stopListening, playAudio, clearAudioQueue, cleanup } = useAudioStream({
    onAudioChunk: handleAudioChunk,
  });

  // Update conversation messages when they change
  useEffect(() => {
    if (activeConversationId && messages.length > 0) {
      updateConversationMessages(activeConversationId, messages);
    }
  }, [messages, activeConversationId, updateConversationMessages]);

  // Initialize: Select or create a conversation when app loads
  useEffect(() => {
    if (!isLoadingConversations && !hasInitializedConversation.current) {
      hasInitializedConversation.current = true;
      
      if (conversations.length > 0) {
        // Select the most recent conversation
        handleSelectConversation(conversations[0].id);
      } else {
        // Create a new conversation
        handleNewConversation();
      }
    }
  }, [isLoadingConversations, conversations]);

  // Fetch available models and check Ollama status
  useEffect(() => {
    fetch('/api/models')
      .then((res) => res.json())
      .then((data) => {
        if (data.available && data.models.length > 0) {
          setOllamaStatus({
            available: true,
            models: data.models,
            currentModel: data.current || data.models[0],
          });
          setSelectedModel(data.current || data.models[0]);
        } else {
          setOllamaStatus({
            available: false,
            models: [],
            currentModel: '',
            error: data.error || 'No models available. Run: ollama pull qwen3:8b',
          });
        }
      })
      .catch((err) => {
        console.error('Failed to fetch models:', err);
        setOllamaStatus({
          available: false,
          models: [],
          currentModel: '',
          error: 'Failed to connect to backend. Is the server running?',
        });
      });
  }, []);

  // Fetch available voices
  useEffect(() => {
    fetch('/api/voices')
      .then((res) => res.json())
      .then((data) => {
        if (data.voices && Array.isArray(data.voices)) {
          const voiceList = data.voices.map((v: string) => ({
            id: v,
            name: VOICE_MAP[v] || v,
          }));
          setVoices(voiceList);
        }
      })
      .catch((err) => console.error('Failed to fetch voices:', err));
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => cleanup();
  }, [cleanup]);

  const handleSelectConversation = useCallback(async (id: string) => {
    const loadedMessages = await selectConversation(id);
    setMessages(loadedMessages);
    setStreamingContent('');
    
    // Notify backend about conversation switch
    if (isConnected) {
      sendSetConversation(id);
    }
  }, [selectConversation, isConnected, sendSetConversation]);

  const handleNewConversation = useCallback(async () => {
    const newId = await createConversation();
    if (newId) {
      setMessages([]);
      setStreamingContent('');
      
      // Notify backend about new conversation
      if (isConnected) {
        sendSetConversation(newId);
        sendClearHistory();
      }
    }
  }, [createConversation, isConnected, sendSetConversation, sendClearHistory]);

  const handleDeleteConversation = useCallback(async (id: string) => {
    const success = await deleteConversation(id);
    if (success && id === activeConversationId) {
      // If we deleted the active conversation, create a new one or select another
      if (conversations.length > 1) {
        const nextConv = conversations.find(c => c.id !== id);
        if (nextConv) {
          handleSelectConversation(nextConv.id);
        }
      } else {
        handleNewConversation();
      }
    }
  }, [deleteConversation, activeConversationId, conversations, handleSelectConversation, handleNewConversation]);

  const handleToggleListening = useCallback(async () => {
    if (!ollamaStatus.available) return;
    
    if (isListening) {
      isListeningRef.current = false;
      setIsListening(false);
      stopListening();
      setState(AppState.IDLE);
    } else {
      const success = await startListening();
      if (success) {
        isListeningRef.current = true;
        setIsListening(true);
        setState(AppState.LISTENING);
      } else {
        alert(
          'Failed to access microphone. Please ensure you are using localhost and have granted microphone permissions.'
        );
      }
    }
  }, [isListening, startListening, stopListening, ollamaStatus.available]);

  const handleSendText = useCallback(
    (text: string) => {
      if (!ollamaStatus.available) return;
      
      if (isListening) {
        isListeningRef.current = false;
        setIsListening(false);
        stopListening();
      }
      sendTextMessage(text);
    },
    [isListening, stopListening, sendTextMessage, ollamaStatus.available]
  );

  const handleStop = useCallback(() => {
    sendStop();
    clearAudioQueue();
  }, [sendStop, clearAudioQueue]);

  const handleClearChat = useCallback(() => {
    sendClearHistory();
    setMessages([]);
    setStreamingContent('');
  }, [sendClearHistory]);

  const handleVoiceChange = useCallback(
    (voice: string) => {
      setSelectedVoice(voice);
      sendSetVoice(voice);
      const voiceName = VOICE_MAP[voice] || voice;
      setToast({ message: `Voice changed to ${voiceName}`, type: 'success' });
      setTimeout(() => setToast(null), 3000);
    },
    [sendSetVoice]
  );

  const handleModelChange = useCallback(
    (model: string) => {
      setSelectedModel(model);
      sendSetModel(model);
      setToast({ message: `Model changed to ${model}`, type: 'success' });
      setTimeout(() => setToast(null), 3000);
    },
    [sendSetModel]
  );

  const isDisabled = !ollamaStatus.available;

  // Get current conversation summary
  const currentConversation: ConversationSummary | null = conversations.find(
    (c) => c.id === activeConversationId
  ) || null;

  return (
    <div className="flex h-screen bg-[#15181c] text-white">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        isLoading={isLoadingConversations}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
      />

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col min-w-0">
        <ChatHeader 
          conversation={currentConversation}
          isConnected={isConnected}
        />

        {/* Ollama error banner */}
        {!ollamaStatus.available && (
          <div className="bg-amber-900/50 border-b border-amber-700 px-4 py-3 text-center">
            <p className="text-amber-200 text-sm font-medium">
              Ollama is not available
            </p>
            <p className="text-amber-300/80 text-xs mt-1">
              {ollamaStatus.error || 'Run: ollama serve && ollama pull qwen3:8b'}
            </p>
          </div>
        )}

        {/* Connection error banner */}
        {!isConnected && ollamaStatus.available && (
          <div className="bg-red-900/50 border-b border-red-800 px-4 py-2 text-center text-sm text-red-200">
            Disconnected from server. Attempting to reconnect...
          </div>
        )}

        {/* Toast notification */}
        {toast && (
          <div 
            className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg transition-all duration-300 flex items-center gap-2 ${
              toast.type === 'success' 
                ? 'bg-emerald-600 text-white' 
                : 'bg-red-600 text-white'
            }`}
          >
            {toast.type === 'success' ? (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            )}
            <span className="text-sm font-medium">{toast.message}</span>
            <button 
              onClick={() => setToast(null)} 
              className="ml-2 text-white/80 hover:text-white cursor-pointer"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        <StatusBar state={state} onStop={handleStop} />

        <ChatMessages 
          messages={messages} 
          streamingContent={streamingContent}
          isListening={isListening}
          onToggleListening={handleToggleListening}
          isDisabled={isDisabled}
        />

        <ControlBar
          state={state}
          isListening={isListening}
          isDisabled={isDisabled}
          onToggleListening={handleToggleListening}
          onSendText={handleSendText}
          onClearChat={handleClearChat}
          onStop={handleStop}
          voices={voices}
          selectedVoice={selectedVoice}
          onVoiceChange={handleVoiceChange}
          models={ollamaStatus.models}
          selectedModel={selectedModel}
          onModelChange={handleModelChange}
        />
      </main>
    </div>
  );
}

export default App;
