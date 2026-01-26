interface ModelSelectorProps {
  models: string[];
  selectedModel: string;
  onChange: (model: string) => void;
  disabled: boolean;
}

export function ModelSelector({
  models,
  selectedModel,
  onChange,
  disabled,
}: ModelSelectorProps) {
  if (models.length === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-2">
      <label className="text-violet-400 text-xs font-medium uppercase tracking-wide">Model</label>
      <select
        value={selectedModel}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="bg-[#2a2d32] border border-violet-500/30 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors hover:border-violet-500/50"
      >
        {models.map((model) => (
          <option key={model} value={model}>
            {model}
          </option>
        ))}
      </select>
    </div>
  );
}
