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

  return (
    <div className="flex items-center justify-center gap-3 px-5 py-3 bg-slate-800/50 rounded-xl mx-4 mt-4">
      <div className={`w-3 h-3 rounded-full ${indicatorClass}`} />
      <span className="text-slate-300 text-sm">{text}</span>
      {isProcessing && (
        <button
          onClick={onStop}
          className="ml-4 px-4 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          Stop
        </button>
      )}
    </div>
  );
}
