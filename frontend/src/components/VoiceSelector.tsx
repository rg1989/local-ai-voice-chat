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
      <label className="text-slate-400 text-sm">Voice:</label>
      <select
        value={selectedVoice}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
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
