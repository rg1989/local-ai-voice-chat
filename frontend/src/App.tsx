import { useState, useCallback, useEffect, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatHeader } from './components/ChatHeader';
import { ChatMessages } from './components/ChatMessages';
import { ControlBar } from './components/ControlBar';
import { ChatSettingsModal } from './components/ChatSettingsModal';
import { GlobalSettingsModal } from './components/GlobalSettingsModal';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioStream } from './hooks/useAudioStream';
import { useConversations } from './hooks/useConversations';
import { AppState, Message, WSMessage, ConversationSummary, MemoryUsage, ToolInfo } from './types';
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
  const [ttsEnabled, setTtsEnabled] = useState(() => {
    const saved = localStorage.getItem('ttsEnabled');
    return saved !== null ? saved === 'true' : true; // Default to enabled
  });
  
  // Ollama/Model state
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus>({
    available: true,
    models: [],
    currentModel: '',
  });
  const [selectedModel, setSelectedModel] = useState('');
  
  // Toast notification state
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  
  // Memory usage tracking (context window)
  const [memoryUsage, setMemoryUsage] = useState<MemoryUsage | null>(null);

  // Conversation management
  const {
    conversations,
    activeConversationId,
    isLoading: isLoadingConversations,
    createConversation,
    selectConversation,
    deleteConversation,
    updateConversationMessages,
    renameConversation,
    refetchConversation,
    getConversationSettings,
    updateConversationSettings,
  } = useConversations();

  // Settings modal state (per-conversation)
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [settingsConversationId, setSettingsConversationId] = useState<string | null>(null);
  const [settingsCurrentRules, setSettingsCurrentRules] = useState('');

  // Global settings modal state
  const [globalSettingsOpen, setGlobalSettingsOpen] = useState(false);
  const [availableTools, setAvailableTools] = useState<ToolInfo[]>([]);
  const [globalRules, setGlobalRules] = useState(() => {
    return localStorage.getItem('globalRules') || '';
  });

  const currentUserMessageRef = useRef<string>('');
  const isListeningRef = useRef(false);
  const streamingContentRef = useRef('');
  const hasInitializedConversation = useRef(false);
  const previousMessageCountRef = useRef(0);

  // Keep ref in sync with state for use in callbacks
  useEffect(() => {
    streamingContentRef.current = streamingContent;
  }, [streamingContent]);

  // Handle WebSocket messages
  const handleMessage = useCallback((message: WSMessage) => {
    switch (message.type) {
      case 'status':
        handleStatusUpdate(message.status);
        // Update memory usage if included in status message
        if (message.memory) {
          console.log('[Memory] Received:', message.memory);
          setMemoryUsage(message.memory);
        }
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
      case 'tools_list':
        setAvailableTools(message.tools);
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

  const { isConnected, sendBinary, sendTextMessage, sendStop, sendClearHistory, sendSetVoice, sendSetModel, sendSetConversation, sendSetTtsEnabled, sendSetCustomRules, sendGetTools, sendSetToolEnabled, sendSetGlobalRules } =
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

  // Stop listening when transcription starts (recording phase is over)
  // This closes the recording overlay automatically
  useEffect(() => {
    if (state === AppState.TRANSCRIBING && isListeningRef.current) {
      isListeningRef.current = false;
      setIsListening(false);
      stopListening();
    }
  }, [state, stopListening]);

  // Update conversation messages when they change
  useEffect(() => {
    if (activeConversationId && messages.length > 0) {
      updateConversationMessages(activeConversationId, messages);
      
      // If this is the first message (transition from 0 to 1+), 
      // refetch conversation to get auto-generated title
      if (previousMessageCountRef.current === 0 && messages.length > 0) {
        // Small delay to ensure backend has processed the message
        setTimeout(() => {
          refetchConversation(activeConversationId);
        }, 500);
      }
    }
    previousMessageCountRef.current = messages.length;
  }, [messages, activeConversationId, updateConversationMessages, refetchConversation]);

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
          // Check localStorage for saved model preference
          const savedModel = localStorage.getItem('selectedModel');
          const modelToUse = savedModel && data.models.includes(savedModel) 
            ? savedModel 
            : (data.current || data.models[0]);
          
          setOllamaStatus({
            available: true,
            models: data.models,
            currentModel: modelToUse,
          });
          setSelectedModel(modelToUse);
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
          
          // Check localStorage for saved voice preference
          const savedVoice = localStorage.getItem('selectedVoice');
          if (savedVoice && data.voices.includes(savedVoice)) {
            setSelectedVoice(savedVoice);
          }
        }
      })
      .catch((err) => console.error('Failed to fetch voices:', err));
  }, []);

  // Track if we've synced preferences for this connection
  const hasSyncedPrefsRef = useRef(false);
  
  // Reset sync flag when disconnected
  useEffect(() => {
    if (!isConnected) {
      hasSyncedPrefsRef.current = false;
    }
  }, [isConnected]);
  
  // Send saved preferences to backend when connected
  useEffect(() => {
    if (isConnected && selectedModel && selectedVoice && !hasSyncedPrefsRef.current) {
      hasSyncedPrefsRef.current = true;
      
      // Small delay to ensure WebSocket is fully ready to send messages
      const timeoutId = setTimeout(() => {
        // Send saved preferences to backend
        sendSetModel(selectedModel);
        sendSetVoice(selectedVoice);
        sendSetTtsEnabled(ttsEnabled);
        
        // Request available tools
        sendGetTools();
        
        // Send global rules if set
        if (globalRules) {
          sendSetGlobalRules(globalRules);
        }
        
        // Restore tool enabled states from localStorage
        const savedToolStates = localStorage.getItem('toolStates');
        if (savedToolStates) {
          try {
            const toolStates = JSON.parse(savedToolStates) as Record<string, boolean>;
            Object.entries(toolStates).forEach(([tool, enabled]) => {
              sendSetToolEnabled(tool, enabled);
            });
          } catch (e) {
            console.error('Failed to parse saved tool states:', e);
          }
        }
        
        // IMPORTANT: Also set the active conversation so messages are saved
        if (activeConversationId) {
          sendSetConversation(activeConversationId);
        }
      }, 100);
      
      return () => clearTimeout(timeoutId);
    }
  }, [isConnected, selectedModel, selectedVoice, ttsEnabled, globalRules, activeConversationId, sendSetModel, sendSetVoice, sendSetTtsEnabled, sendSetConversation, sendGetTools, sendSetGlobalRules, sendSetToolEnabled]);

  // Cleanup on unmount
  useEffect(() => {
    return () => cleanup();
  }, [cleanup]);

  const handleSelectConversation = useCallback(async (id: string) => {
    const loadedMessages = await selectConversation(id);
    setMessages(loadedMessages);
    setStreamingContent('');
    setMemoryUsage(null);  // Reset memory indicator immediately
    
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
      setMemoryUsage(null);  // Reset memory indicator
      
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

  const handleRenameConversation = useCallback(async (id: string, newTitle: string) => {
    await renameConversation(id, newTitle);
  }, [renameConversation]);

  const handleOpenSettings = useCallback(async (id: string) => {
    setSettingsConversationId(id);
    // Load current rules
    const settings = await getConversationSettings(id);
    setSettingsCurrentRules(settings?.custom_rules || '');
    setSettingsModalOpen(true);
  }, [getConversationSettings]);

  const handleCloseSettings = useCallback(() => {
    setSettingsModalOpen(false);
    setSettingsConversationId(null);
    setSettingsCurrentRules('');
  }, []);

  const handleSaveSettings = useCallback(async (rules: string) => {
    if (!settingsConversationId) return;
    
    const success = await updateConversationSettings(settingsConversationId, {
      custom_rules: rules,
    });
    
    if (success) {
      setToast({ message: 'Chat rules saved', type: 'success' });
      setTimeout(() => setToast(null), 3000);
      
      // If this is the active conversation, also update via WebSocket
      // so the backend session picks up the new rules immediately
      if (settingsConversationId === activeConversationId && isConnected) {
        sendSetCustomRules(rules);
      }
    } else {
      setToast({ message: 'Failed to save rules', type: 'error' });
      setTimeout(() => setToast(null), 3000);
    }
  }, [settingsConversationId, updateConversationSettings, activeConversationId, isConnected, sendSetCustomRules]);

  // Global settings handlers
  const handleOpenGlobalSettings = useCallback(() => {
    // Request fresh tools list when opening modal
    if (isConnected) {
      sendGetTools();
    }
    setGlobalSettingsOpen(true);
  }, [isConnected, sendGetTools]);

  const handleCloseGlobalSettings = useCallback(() => {
    setGlobalSettingsOpen(false);
  }, []);

  const handleToolToggle = useCallback((toolName: string, enabled: boolean) => {
    // Update local state immediately for responsive UI
    setAvailableTools(prev => 
      prev.map(tool => 
        tool.name === toolName ? { ...tool, enabled } : tool
      )
    );
    
    // Send to backend
    if (isConnected) {
      sendSetToolEnabled(toolName, enabled);
    }
    
    // Persist to localStorage
    const savedToolStates = localStorage.getItem('toolStates');
    let toolStates: Record<string, boolean> = {};
    if (savedToolStates) {
      try {
        toolStates = JSON.parse(savedToolStates);
      } catch (e) {
        console.error('Failed to parse saved tool states:', e);
      }
    }
    toolStates[toolName] = enabled;
    localStorage.setItem('toolStates', JSON.stringify(toolStates));
    
    setToast({ 
      message: `Tool "${toolName}" ${enabled ? 'enabled' : 'disabled'}`, 
      type: 'success' 
    });
    setTimeout(() => setToast(null), 3000);
  }, [isConnected, sendSetToolEnabled]);

  const handleSaveGlobalRules = useCallback((rules: string) => {
    setGlobalRules(rules);
    localStorage.setItem('globalRules', rules);
    
    if (isConnected) {
      sendSetGlobalRules(rules);
    }
    
    setToast({ message: 'Global rules saved', type: 'success' });
    setTimeout(() => setToast(null), 3000);
  }, [isConnected, sendSetGlobalRules]);

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
    // Stop backend processing
    sendStop();
    clearAudioQueue();
    
    // Also stop recording if active
    if (isListening) {
      isListeningRef.current = false;
      setIsListening(false);
      stopListening();
    }
    
    // Reset to idle state
    setState(AppState.IDLE);
  }, [sendStop, clearAudioQueue, isListening, stopListening]);

  const handleClearChat = useCallback(() => {
    sendClearHistory();
    setMessages([]);
    setStreamingContent('');
    setMemoryUsage(null);  // Reset memory indicator
  }, [sendClearHistory]);

  const handleVoiceChange = useCallback(
    (voice: string) => {
      setSelectedVoice(voice);
      sendSetVoice(voice);
      // Persist voice selection to localStorage
      localStorage.setItem('selectedVoice', voice);
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
      // Persist model selection to localStorage
      localStorage.setItem('selectedModel', model);
      setToast({ message: `Model changed to ${model}`, type: 'success' });
      setTimeout(() => setToast(null), 3000);
    },
    [sendSetModel]
  );

  const handleTtsToggle = useCallback(() => {
    const newValue = !ttsEnabled;
    setTtsEnabled(newValue);
    sendSetTtsEnabled(newValue);
    localStorage.setItem('ttsEnabled', String(newValue));
    setToast({ 
      message: newValue ? 'Voice responses enabled' : 'Voice responses disabled', 
      type: 'success' 
    });
    setTimeout(() => setToast(null), 3000);
  }, [ttsEnabled, sendSetTtsEnabled]);

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
        onRenameConversation={handleRenameConversation}
        onOpenSettings={handleOpenSettings}
        onOpenGlobalSettings={handleOpenGlobalSettings}
        models={ollamaStatus.models}
        selectedModel={selectedModel}
        onModelChange={handleModelChange}
        voices={voices}
        selectedVoice={selectedVoice}
        onVoiceChange={handleVoiceChange}
        isDisabled={isDisabled}
      />

      {/* Chat Settings Modal */}
      <ChatSettingsModal
        isOpen={settingsModalOpen}
        onClose={handleCloseSettings}
        conversationId={settingsConversationId || ''}
        currentRules={settingsCurrentRules}
        onSave={handleSaveSettings}
      />

      {/* Global Settings Modal */}
      <GlobalSettingsModal
        isOpen={globalSettingsOpen}
        onClose={handleCloseGlobalSettings}
        tools={availableTools}
        onToolToggle={handleToolToggle}
        globalRules={globalRules}
        onSaveGlobalRules={handleSaveGlobalRules}
      />

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col min-w-0">
        <ChatHeader 
          conversation={currentConversation}
          isConnected={isConnected}
          ttsEnabled={ttsEnabled}
          onTtsToggle={handleTtsToggle}
          memoryUsage={memoryUsage}
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
            className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-3 rounded-lg shadow-lg transition-all duration-300 flex items-center gap-2 ${
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

        <ChatMessages 
          messages={messages} 
          streamingContent={streamingContent}
          isListening={isListening}
          onToggleListening={handleToggleListening}
          onClearChat={handleClearChat}
          isDisabled={isDisabled}
          state={state}
        />

        <ControlBar
          state={state}
          isListening={isListening}
          isDisabled={isDisabled}
          onToggleListening={handleToggleListening}
          onSendText={handleSendText}
          onStop={handleStop}
        />
      </main>
    </div>
  );
}

export default App;
