import { AppState } from '../types';
import { VoiceSelector } from './VoiceSelector';
import { InputBar } from './InputBar';

interface ControlBarProps {
  state: AppState;
  isListening: boolean;
  onToggleListening: () => void;
  onSendText: (text: string) => void;
  onClearChat: () => void;
  voices: { id: string; name: string }[];
  selectedVoice: string;
  onVoiceChange: (voice: string) => void;
}

export function ControlBar({
  state,
  isListening,
  onToggleListening,
  onSendText,
  onClearChat,
  voices,
  selectedVoice,
  onVoiceChange,
}: ControlBarProps) {
  const isProcessing = [
    AppState.TRANSCRIBING,
    AppState.THINKING,
    AppState.SPEAKING,
  ].includes(state);

  return (
    <div className="border-t border-slate-700 px-4 py-4 bg-slate-900">
      <div className="max-w-4xl mx-auto space-y-4">
        {/* Text input row */}
        <div className="flex gap-3">
          <div className="flex-1">
            <InputBar onSend={onSendText} disabled={isProcessing} />
          </div>
          <button
            onClick={onToggleListening}
            disabled={isProcessing}
            className={`px-6 py-3 font-medium rounded-xl transition-all ${
              isListening
                ? 'bg-red-600 hover:bg-red-700 text-white'
                : 'bg-emerald-600 hover:bg-emerald-700 text-white'
            } disabled:bg-slate-600 disabled:cursor-not-allowed`}
          >
            {isListening ? (
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
                Stop
              </span>
            ) : (
              'Start Listening'
            )}
          </button>
        </div>

        {/* Controls row */}
        <div className="flex items-center justify-between">
          <VoiceSelector
            voices={voices}
            selectedVoice={selectedVoice}
            onChange={onVoiceChange}
            disabled={isProcessing}
          />
          <button
            onClick={onClearChat}
            className="px-4 py-2 text-sm text-slate-400 hover:text-white border border-slate-600 hover:border-slate-500 rounded-lg transition-colors"
          >
            Clear Chat
          </button>
        </div>
      </div>
    </div>
  );
}
