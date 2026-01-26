import { AppState } from '../types';
import { VoiceSelector } from './VoiceSelector';
import { ModelSelector } from './ModelSelector';
import { InputBar } from './InputBar';

interface ControlBarProps {
  state: AppState;
  isListening: boolean;
  isDisabled: boolean;
  onToggleListening: () => void;
  onSendText: (text: string) => void;
  onClearChat: () => void;
  onStop: () => void;
  voices: { id: string; name: string }[];
  selectedVoice: string;
  onVoiceChange: (voice: string) => void;
  models: string[];
  selectedModel: string;
  onModelChange: (model: string) => void;
}

export function ControlBar({
  state,
  isListening,
  isDisabled,
  onToggleListening,
  onSendText,
  onClearChat,
  onStop,
  voices,
  selectedVoice,
  onVoiceChange,
  models,
  selectedModel,
  onModelChange,
}: ControlBarProps) {
  const isProcessing = [
    AppState.TRANSCRIBING,
    AppState.THINKING,
    AppState.SPEAKING,
  ].includes(state);

  const controlsDisabled = isProcessing || isDisabled;

  return (
    <div className="border-t border-slate-700/50 px-6 py-4 bg-[#1e2227]">
      <div className="max-w-3xl mx-auto space-y-4">
        {/* Text input row */}
        <div className="flex gap-3">
          <div className="flex-1">
            <InputBar onSend={onSendText} disabled={controlsDisabled} />
          </div>
          {isProcessing ? (
            <button
              onClick={onStop}
              className="px-6 py-3 font-medium rounded-xl bg-red-600 hover:bg-red-700 text-white transition-all flex items-center gap-2 cursor-pointer shadow-lg shadow-red-600/20"
            >
              <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
              Stop
            </button>
          ) : (
            <button
              onClick={onToggleListening}
              disabled={isDisabled}
              className={`px-6 py-3 font-medium rounded-xl transition-all cursor-pointer shadow-lg ${
                isListening
                  ? 'bg-red-600 hover:bg-red-700 text-white shadow-red-600/20'
                  : 'bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white shadow-emerald-500/20'
              } disabled:bg-slate-600 disabled:cursor-not-allowed disabled:shadow-none`}
            >
            {isListening ? (
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
                Stop Listening
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg>
                Start Listening
              </span>
            )}
            </button>
          )}
        </div>

        {/* Controls row */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-4 flex-wrap">
            <ModelSelector
              models={models}
              selectedModel={selectedModel}
              onChange={onModelChange}
              disabled={controlsDisabled}
            />
            <VoiceSelector
              voices={voices}
              selectedVoice={selectedVoice}
              onChange={onVoiceChange}
              disabled={controlsDisabled}
            />
          </div>
          <button
            onClick={onClearChat}
            className="px-4 py-2 text-sm text-slate-400 hover:text-white border border-slate-600/50 hover:border-slate-500 hover:bg-slate-700/50 rounded-lg transition-all cursor-pointer"
          >
            Clear Chat
          </button>
        </div>
      </div>
    </div>
  );
}
