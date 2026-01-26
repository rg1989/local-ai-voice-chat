import { AppState } from '../types';

interface StatusBarProps {
  state: AppState;
  onStop: () => void;
}

export function StatusBar({ state, onStop }: StatusBarProps) {
  const isProcessing = [
    AppState.TRANSCRIBING,
    AppState.THINKING,
    AppState.SPEAKING,
  ].includes(state);

  const statusConfig: Record<AppState, { text: string; indicatorClass: string }> = {
    [AppState.IDLE]: {
      text: 'Ready - Click "Start Listening"',
      indicatorClass: 'bg-slate-500',
    },
    [AppState.LISTENING]: {
      text: 'Listening... (speak now)',
      indicatorClass: 'bg-emerald-500 animate-pulse',
    },
    [AppState.TRANSCRIBING]: {
      text: 'Transcribing...',
      indicatorClass: 'bg-amber-500 animate-pulse',
    },
    [AppState.THINKING]: {
      text: 'Thinking...',
      indicatorClass: 'bg-amber-500 animate-pulse',
    },
    [AppState.SPEAKING]: {
      text: 'Speaking...',
      indicatorClass: 'bg-purple-500 animate-pulse',
    },
  };

  const { text, indicatorClass } = statusConfig[state];

  // Don't show status bar for IDLE (nothing happening) or LISTENING (full overlay is shown instead)
  if (state === AppState.IDLE || state === AppState.LISTENING) {
    return null;
  }

  return (
    <div className="flex items-center justify-center gap-3 px-5 py-2.5 bg-[#1e2227] border-b border-slate-700/50">
      <div className={`w-2.5 h-2.5 rounded-full ${indicatorClass}`} />
      <span className="text-slate-300 text-sm font-medium">{text}</span>
      {isProcessing && (
        <button
          onClick={onStop}
          className="ml-4 px-4 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-medium rounded-lg transition-colors cursor-pointer"
        >
          Stop
        </button>
      )}
    </div>
  );
}
