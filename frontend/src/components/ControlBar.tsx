import { AppState } from '../types';
import { InputBar } from './InputBar';

interface ControlBarProps {
  state: AppState;
  isListening: boolean;
  isDisabled: boolean;
  onToggleListening: () => void;
  onSendText: (text: string) => void;
  onStop: () => void;
}

export function ControlBar({
  state,
  isListening,
  isDisabled,
  onToggleListening,
  onSendText,
  onStop,
}: ControlBarProps) {
  const isProcessing = [
    AppState.TRANSCRIBING,
    AppState.THINKING,
    AppState.SPEAKING,
  ].includes(state);

  const controlsDisabled = isProcessing || isDisabled;

  return (
    <div className="border-t border-slate-700/50 px-6 py-3 bg-[#1e2227]">
      <div className="max-w-3xl mx-auto">
        {/* Text input row - compact aligned controls */}
        <div className="flex gap-2 items-end">
          <div className="flex-1">
            <InputBar onSend={onSendText} disabled={controlsDisabled} />
          </div>
          {isProcessing ? (
            <button
              onClick={onStop}
              className="h-9 px-4 text-sm font-medium rounded-lg bg-red-600 hover:bg-red-700 text-white transition-all flex items-center gap-1.5 cursor-pointer shrink-0"
            >
              <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
              Stop
            </button>
          ) : (
            <button
              onClick={onToggleListening}
              disabled={isDisabled}
              className={`h-9 px-4 text-sm font-medium rounded-lg transition-all cursor-pointer shrink-0 ${
                isListening
                  ? 'bg-red-600 hover:bg-red-700 text-white'
                  : 'bg-emerald-600 hover:bg-emerald-700 text-white'
              } disabled:bg-slate-600 disabled:cursor-not-allowed disabled:text-slate-400`}
            >
              {isListening ? (
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
                  Stop
                </span>
              ) : (
                <span className="flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                  </svg>
                  Record
                </span>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
