import { MemoryUsage } from '../types';

interface MemoryIndicatorProps {
  memory: MemoryUsage | null;
}

export function MemoryIndicator({ memory }: MemoryIndicatorProps) {
  if (!memory) return null;

  const getBarColor = (percentage: number) => {
    if (percentage < 50) return 'bg-emerald-500';
    if (percentage < 80) return 'bg-amber-500';
    return 'bg-red-500';
  };

  const getTextColor = (percentage: number) => {
    if (percentage < 50) return 'text-emerald-400';
    if (percentage < 80) return 'text-amber-400';
    return 'text-red-400';
  };

  return (
    <div 
      className="flex items-center gap-2"
      title={`Context: ${memory.used_tokens.toLocaleString()} / ${memory.max_tokens.toLocaleString()} tokens${memory.is_near_limit ? '\n⚠️ Near limit - AI may forget earlier messages' : ''}`}
    >
      <span className="text-xs text-slate-400">Context</span>
      <div className="w-16 h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${getBarColor(memory.percentage)} transition-all duration-300`}
          style={{ width: `${Math.min(100, memory.percentage)}%` }}
        />
      </div>
      <span className={`text-xs font-medium ${getTextColor(memory.percentage)}`}>
        {memory.percentage}%
      </span>
      {memory.is_near_limit && (
        <span className="text-amber-400 text-xs" title="Context nearly full">⚠️</span>
      )}
    </div>
  );
}
