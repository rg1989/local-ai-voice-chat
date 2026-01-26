interface VoiceSelectorProps {
  voices: { id: string; name: string }[];
  selectedVoice: string;
  onChange: (voice: string) => void;
  disabled: boolean;
}

export function VoiceSelector({
  voices,
  selectedVoice,
  onChange,
  disabled,
}: VoiceSelectorProps) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-violet-400 text-xs font-medium uppercase tracking-wide">Voice</label>
      <select
        value={selectedVoice}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="bg-[#2a2d32] border border-violet-500/30 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors hover:border-violet-500/50"
      >
        {voices.map((voice) => (
          <option key={voice.id} value={voice.id}>
            {voice.name}
          </option>
        ))}
      </select>
    </div>
  );
}
