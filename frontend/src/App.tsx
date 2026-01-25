import { useState, useCallback, useEffect, useRef } from 'react';
import { Header } from './components/Header';
import { StatusBar } from './components/StatusBar';
import { ChatMessages } from './components/ChatMessages';
import { ControlBar } from './components/ControlBar';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioStream } from './hooks/useAudioStream';
import { AppState, Message, WSMessage } from './types';
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

function App() {
  const [state, setState] = useState<AppState>(AppState.IDLE);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingContent, setStreamingContent] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState('af_heart');
  const [voices, setVoices] = useState<{ id: string; name: string }[]>([]);

  const currentUserMessageRef = useRef<string>('');
  const isListeningRef = useRef(false);

  // Handle WebSocket messages
  const handleMessage = useCallback((message: WSMessage) => {
    switch (message.type) {
      case 'status':
        handleStatusUpdate(message.status);
        break;
      case 'transcription':
        // Add user message
        currentUserMessageRef.current = message.text;
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: 'user',
            content: message.text,
            timestamp: new Date(),
          },
        ]);
        break;
      case 'response_token':
        setStreamingContent((prev) => prev + message.token);
        break;
      case 'response_end':
        // Move streaming content to final message
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: 'assistant',
            content: streamingContent,
            timestamp: new Date(),
          },
        ]);
        setStreamingContent('');
        break;
      case 'audio':
        playAudio(message.audio, message.sample_rate);
        break;
    }
  }, [streamingContent]);

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
        if (streamingContent) {
          setMessages((prev) => [
            ...prev,
            {
              id: generateId(),
              role: 'assistant',
              content: streamingContent + ' [stopped]',
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
  }, [streamingContent]);

  const { isConnected, sendBinary, sendTextMessage, sendStop, sendClearHistory, sendSetVoice } =
    useWebSocket({
      onMessage: handleMessage,
    });

  const handleAudioChunk = useCallback(
    (data: ArrayBuffer) => {
      if (isListeningRef.current && state === AppState.LISTENING) {
        sendBinary(data);
      }
    },
    [sendBinary, state]
  );

  const { startListening, stopListening, playAudio, cleanup } = useAudioStream({
    onAudioChunk: handleAudioChunk,
  });

  // Fetch available voices
  useEffect(() => {
    fetch('/api/voices')
      .then((res) => res.json())
      .then((data) => {
        const voiceList = data.voices.map((v: string) => ({
          id: v,
          name: VOICE_MAP[v] || v,
        }));
        setVoices(voiceList);
      })
      .catch(console.error);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => cleanup();
  }, [cleanup]);

  const handleToggleListening = useCallback(async () => {
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
  }, [isListening, startListening, stopListening]);

  const handleSendText = useCallback(
    (text: string) => {
      if (isListening) {
        isListeningRef.current = false;
        setIsListening(false);
        stopListening();
      }
      sendTextMessage(text);
    },
    [isListening, stopListening, sendTextMessage]
  );

  const handleStop = useCallback(() => {
    sendStop();
  }, [sendStop]);

  const handleClearChat = useCallback(() => {
    sendClearHistory();
    setMessages([]);
    setStreamingContent('');
  }, [sendClearHistory]);

  const handleVoiceChange = useCallback(
    (voice: string) => {
      setSelectedVoice(voice);
      sendSetVoice(voice);
    },
    [sendSetVoice]
  );

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-white">
      <Header />

      {!isConnected && (
        <div className="bg-red-900/50 border-b border-red-800 px-4 py-2 text-center text-sm text-red-200">
          Disconnected from server. Attempting to reconnect...
        </div>
      )}

      <StatusBar state={state} onStop={handleStop} />

      <ChatMessages messages={messages} streamingContent={streamingContent} />

      <ControlBar
        state={state}
        isListening={isListening}
        onToggleListening={handleToggleListening}
        onSendText={handleSendText}
        onClearChat={handleClearChat}
        voices={voices}
        selectedVoice={selectedVoice}
        onVoiceChange={handleVoiceChange}
      />
    </div>
  );
}

export default App;
