import { ConversationSummary, MemoryUsage, AppState } from '../types';
import { MemoryIndicator } from './MemoryIndicator';

interface WakeWordStatus {
  state: 'listening' | 'active' | 'disabled';
  displayName: string;
}

interface ChatHeaderProps {
  conversation: ConversationSummary | null;
  isConnected: boolean;
  ttsEnabled: boolean;
  onTtsToggle: () => void;
  memoryUsage: MemoryUsage | null;
  wakeWordEnabled?: boolean;
  wakeWordStatus?: WakeWordStatus | null;
  onDisableWakeWord?: () => void;
  appState?: AppState;
}

// Chat bubble icon (matches sidebar)
function ChatBubbleIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
  );
}

// Speaker on icon
function SpeakerOnIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
    </svg>
  );
}

// Speaker off/muted icon
function SpeakerOffIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
    </svg>
  );
}

// Microphone icon for wake word
function MicrophoneIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
    </svg>
  );
}

// Close/X icon
function CloseIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

export function ChatHeader({ 
  conversation, 
  isConnected, 
  ttsEnabled, 
  onTtsToggle, 
  memoryUsage,
  wakeWordEnabled = false,
  wakeWordStatus = null,
  onDisableWakeWord,
  appState,
}: ChatHeaderProps) {
  // Determine what text to show for wake word indicator based on app state
  const getWakeWordText = () => {
    if (wakeWordStatus?.state !== 'active') {
      return wakeWordStatus?.displayName || 'Wake Word';
    }
    // Wake word is active - show status based on app state
    switch (appState) {
      case AppState.TRANSCRIBING:
        return 'Transcribing...';
      case AppState.THINKING:
        return 'Thinking...';
      case AppState.SPEAKING:
        return 'Speaking...';
      default:
        return 'Listening...';
    }
  };

  // Determine if we're in a processing state (not actively listening for input)
  const isProcessing = appState === AppState.TRANSCRIBING || 
                       appState === AppState.THINKING || 
                       appState === AppState.SPEAKING;
  return (
    <header className="bg-[#1e2227] border-b border-slate-700/50 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Chat Icon */}
          <div className="w-11 h-11 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <ChatBubbleIcon />
          </div>
          
          <div>
            <h1 className="text-lg font-semibold text-white">
              {conversation?.title || 'New Conversation'}
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-red-500'}`} />
              <span className="text-xs text-slate-400">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Wake Word Indicator */}
          {wakeWordEnabled && (
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${
              wakeWordStatus?.state === 'active' 
                ? isProcessing 
                  ? 'bg-amber-600/20 text-amber-400'  // Processing state - amber
                  : 'bg-emerald-600/20 text-emerald-400'  // Active/listening - green
                : 'bg-violet-600/20 text-violet-400'  // Waiting for wake word - violet
            }`}>
              {/* Pulsing indicator */}
              <span className="relative flex h-2 w-2">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  wakeWordStatus?.state === 'active' 
                    ? isProcessing ? 'bg-amber-400' : 'bg-emerald-400' 
                    : 'bg-violet-400'
                }`}></span>
                <span className={`relative inline-flex rounded-full h-2 w-2 ${
                  wakeWordStatus?.state === 'active' 
                    ? isProcessing ? 'bg-amber-500' : 'bg-emerald-500' 
                    : 'bg-violet-500'
                }`}></span>
              </span>
              
              {/* Microphone icon */}
              <MicrophoneIcon />
              
              {/* Wake word status text */}
              <span className="text-xs font-medium">
                {getWakeWordText()}
              </span>
              
              {/* Disable button */}
              {onDisableWakeWord && (
                <button
                  onClick={onDisableWakeWord}
                  className="ml-1 p-0.5 hover:bg-white/10 rounded transition-colors cursor-pointer"
                  title="Disable wake word"
                >
                  <CloseIcon />
                </button>
              )}
            </div>
          )}

          {/* Memory Usage Indicator */}
          <MemoryIndicator memory={memoryUsage} />

          {/* TTS Toggle Button */}
          <button
            onClick={onTtsToggle}
            className={`p-2 rounded-lg transition-all cursor-pointer ${
              ttsEnabled
                ? 'bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30'
                : 'bg-violet-600/20 text-violet-400 hover:bg-violet-600/30'
            }`}
            title={ttsEnabled ? 'Voice responses enabled' : 'Voice responses disabled'}
          >
            {ttsEnabled ? <SpeakerOnIcon /> : <SpeakerOffIcon />}
          </button>
        </div>
      </div>
    </header>
  );
}
