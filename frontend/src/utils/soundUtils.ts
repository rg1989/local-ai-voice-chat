/**
 * Sound utility module for audio feedback chimes.
 * Uses Web Audio API to synthesize sounds programmatically.
 */

// Sound option definitions
export interface SoundOption {
  id: string;
  name: string;
}

export const WAKE_SOUNDS: SoundOption[] = [
  { id: 'none', name: 'None' },
  { id: 'wake-chime', name: 'Chime' },
  { id: 'wake-bell', name: 'Bell' },
  { id: 'wake-ding', name: 'Ding' },
  { id: 'wake-soft', name: 'Soft' },
];

export const MESSAGE_SOUNDS: SoundOption[] = [
  { id: 'none', name: 'None' },
  { id: 'message-pop', name: 'Pop' },
  { id: 'message-click', name: 'Click' },
  { id: 'message-tone', name: 'Tone' },
  { id: 'message-whoosh', name: 'Whoosh' },
];

export const THINKING_SOUNDS: SoundOption[] = [
  { id: 'none', name: 'None' },
  { id: 'thinking-bubbles', name: 'Bubbles' },
  { id: 'thinking-drops', name: 'Drops' },
  { id: 'thinking-hum', name: 'Gentle Hum' },
  { id: 'thinking-soft', name: 'Soft Tones' },
];

// Default sound settings
export const DEFAULT_SOUND_SETTINGS = {
  enabled: true,
  wakeSound: 'wake-chime',
  messageSound: 'message-pop',
  thinkingSound: 'thinking-bubbles',
  volume: 0.3,
};

// Audio context singleton
let audioContext: AudioContext | null = null;

// Thinking sound state
let thinkingInterval: number | null = null;
let isThinkingPlaying = false;

/**
 * Get or create the audio context
 */
function getAudioContext(): AudioContext {
  if (!audioContext) {
    audioContext = new AudioContext();
  }
  // Resume if suspended (browser autoplay policy)
  if (audioContext.state === 'suspended') {
    audioContext.resume();
  }
  return audioContext;
}

/**
 * Play a wake sound
 */
export function playWakeSound(soundId: string, volume: number = 0.3): void {
  if (soundId === 'none') return;

  const ctx = getAudioContext();
  const now = ctx.currentTime;

  switch (soundId) {
    case 'wake-chime': {
      // Ascending two-note chime (C5 -> E5)
      const freq1 = 523.25; // C5
      const freq2 = 659.25; // E5

      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gain1 = ctx.createGain();
      const gain2 = ctx.createGain();

      osc1.type = 'sine';
      osc2.type = 'sine';
      osc1.frequency.value = freq1;
      osc2.frequency.value = freq2;

      // First note
      gain1.gain.setValueAtTime(0, now);
      gain1.gain.linearRampToValueAtTime(volume, now + 0.02);
      gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.25);

      // Second note (delayed)
      gain2.gain.setValueAtTime(0, now);
      gain2.gain.setValueAtTime(0, now + 0.1);
      gain2.gain.linearRampToValueAtTime(volume, now + 0.12);
      gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.4);

      osc1.connect(gain1).connect(ctx.destination);
      osc2.connect(gain2).connect(ctx.destination);

      osc1.start(now);
      osc2.start(now + 0.1);
      osc1.stop(now + 0.3);
      osc2.stop(now + 0.45);
      break;
    }

    case 'wake-bell': {
      // Single bell tone with harmonics
      const fundamental = 880; // A5
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gain = ctx.createGain();

      osc1.type = 'sine';
      osc2.type = 'sine';
      osc1.frequency.value = fundamental;
      osc2.frequency.value = fundamental * 2.4; // Bell-like overtone

      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(volume, now + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.5);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(ctx.destination);

      osc1.start(now);
      osc2.start(now);
      osc1.stop(now + 0.55);
      osc2.stop(now + 0.55);
      break;
    }

    case 'wake-ding': {
      // Quick high ding
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.value = 1200;

      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(volume, now + 0.005);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);

      osc.connect(gain).connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.2);
      break;
    }

    case 'wake-soft': {
      // Soft warm tone
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.exponentialRampToValueAtTime(550, now + 0.2);

      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(volume * 0.7, now + 0.05);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

      osc.connect(gain).connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.4);
      break;
    }
  }
}

/**
 * Play a message received sound
 */
export function playMessageSound(soundId: string, volume: number = 0.3): void {
  if (soundId === 'none') return;

  const ctx = getAudioContext();
  const now = ctx.currentTime;

  switch (soundId) {
    case 'message-pop': {
      // Bubble pop sound
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(400, now);
      osc.frequency.exponentialRampToValueAtTime(800, now + 0.05);
      osc.frequency.exponentialRampToValueAtTime(600, now + 0.1);

      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(volume, now + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);

      osc.connect(gain).connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.2);
      break;
    }

    case 'message-click': {
      // Soft click
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'square';
      osc.frequency.value = 1000;

      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(volume * 0.5, now + 0.002);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.03);

      osc.connect(gain).connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.05);
      break;
    }

    case 'message-tone': {
      // Short confirmation tone
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.value = 660;

      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(volume, now + 0.01);
      gain.gain.setValueAtTime(volume, now + 0.08);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);

      osc.connect(gain).connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.2);
      break;
    }

    case 'message-whoosh': {
      // Soft whoosh using filtered noise simulation
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(200, now);
      osc.frequency.exponentialRampToValueAtTime(800, now + 0.1);
      osc.frequency.exponentialRampToValueAtTime(400, now + 0.2);

      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(volume * 0.4, now + 0.05);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);

      osc.connect(gain).connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.3);
      break;
    }
  }
}

/**
 * Play a thinking sound pattern (three tones)
 */
function playThinkingPulse(soundId: string, volume: number): void {
  if (soundId === 'none') return;

  const ctx = getAudioContext();
  const now = ctx.currentTime;
  const gap = 0.18; // Base gap between tones

  switch (soundId) {
    case 'thinking-bubbles': {
      // Three soft ascending bubble tones
      const frequencies = [349, 440, 523]; // F4, A4, C5 - gentle ascending
      frequencies.forEach((freq, i) => {
        const startTime = now + i * (gap + 0.02);
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        // Gentle upward pitch bend for bubble effect
        osc.frequency.setValueAtTime(freq * 0.92, startTime);
        osc.frequency.exponentialRampToValueAtTime(freq, startTime + 0.04);

        // Softer envelope
        gain.gain.setValueAtTime(0, startTime);
        gain.gain.linearRampToValueAtTime(volume * 0.22, startTime + 0.025);
        gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.14);

        osc.connect(gain).connect(ctx.destination);
        osc.start(startTime);
        osc.stop(startTime + 0.16);
      });
      break;
    }

    case 'thinking-drops': {
      // Three very soft water drop sounds (descending, quiet)
      const frequencies = [440, 392, 349]; // A4, G4, F4 - gentle descending
      frequencies.forEach((freq, i) => {
        const startTime = now + i * (gap + 0.04); // More spacing for gentleness
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        // Very gentle downward pitch for drop effect
        osc.frequency.setValueAtTime(freq, startTime);
        osc.frequency.exponentialRampToValueAtTime(freq * 0.85, startTime + 0.15);

        // Very soft envelope
        gain.gain.setValueAtTime(0, startTime);
        gain.gain.linearRampToValueAtTime(volume * 0.2, startTime + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.18);

        osc.connect(gain).connect(ctx.destination);
        osc.start(startTime);
        osc.stop(startTime + 0.2);
      });
      break;
    }

    case 'thinking-hum': {
      // Three very gentle low hums (almost like breath)
      const frequencies = [220, 247, 262]; // A3, B3, C4 - very gentle rise
      frequencies.forEach((freq, i) => {
        const startTime = now + i * (gap + 0.06); // Even more spacing
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.value = freq;

        // Very soft, breathy envelope with slow attack and decay
        gain.gain.setValueAtTime(0, startTime);
        gain.gain.linearRampToValueAtTime(volume * 0.15, startTime + 0.06);
        gain.gain.linearRampToValueAtTime(volume * 0.12, startTime + 0.12);
        gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.22);

        osc.connect(gain).connect(ctx.destination);
        osc.start(startTime);
        osc.stop(startTime + 0.25);
      });
      break;
    }

    case 'thinking-soft': {
      // Three very soft mellow tones (whisper quiet)
      const frequencies = [294, 330, 370]; // D4, E4, F#4 - very gentle progression
      frequencies.forEach((freq, i) => {
        const startTime = now + i * (gap + 0.05); // More spacing for softness
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.value = freq;

        // Very soft envelope with slow attack and long decay
        gain.gain.setValueAtTime(0, startTime);
        gain.gain.linearRampToValueAtTime(volume * 0.15, startTime + 0.05);
        gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.2);

        osc.connect(gain).connect(ctx.destination);
        osc.start(startTime);
        osc.stop(startTime + 0.18);
      });
      break;
    }
  }
}

/**
 * Start the thinking sound loop
 */
export function startThinkingSound(soundId: string, volume: number = 0.3): void {
  if (soundId === 'none' || isThinkingPlaying) return;

  isThinkingPlaying = true;

  // Play first pattern immediately
  playThinkingPulse(soundId, volume);

  // Set up interval for recurring patterns
  // Each pattern is ~0.5s, so 1.2s interval gives nice breathing room
  const intervalMs = 1200;
  thinkingInterval = window.setInterval(() => {
    if (isThinkingPlaying) {
      playThinkingPulse(soundId, volume);
    }
  }, intervalMs);
}

/**
 * Stop the thinking sound loop
 */
export function stopThinkingSound(): void {
  isThinkingPlaying = false;
  if (thinkingInterval !== null) {
    clearInterval(thinkingInterval);
    thinkingInterval = null;
  }
}

/**
 * Preview a sound (for settings UI)
 */
export function previewSound(
  category: 'wake' | 'message' | 'thinking',
  soundId: string,
  volume: number = 0.3
): void {
  // Stop any playing thinking sound first
  stopThinkingSound();

  switch (category) {
    case 'wake':
      playWakeSound(soundId, volume);
      break;
    case 'message':
      playMessageSound(soundId, volume);
      break;
    case 'thinking':
      // Just play one pulse for preview
      playThinkingPulse(soundId, volume);
      break;
  }
}

/**
 * Initialize audio context on user interaction
 * Call this on first user interaction to enable audio
 */
export function initAudioContext(): void {
  getAudioContext();
}
