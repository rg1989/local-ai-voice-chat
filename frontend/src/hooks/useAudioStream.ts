import { useCallback, useRef } from 'react';

interface UseAudioStreamOptions {
  onAudioChunk: (data: ArrayBuffer) => void;
}

interface QueuedAudio {
  base64Audio: string;
  sampleRate: number;
}

export function useAudioStream({ onAudioChunk }: UseAudioStreamOptions) {
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const playbackContextRef = useRef<AudioContext | null>(null);
  
  // Audio playback queue
  const audioQueueRef = useRef<QueuedAudio[]>([]);
  const isPlayingRef = useRef(false);

  const startListening = useCallback(async () => {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      mediaStreamRef.current = stream;

      // Create audio context at 16kHz
      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);

      // Use ScriptProcessorNode for audio processing
      // Buffer size of 4096 gives us ~256ms chunks at 16kHz
      const scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
      scriptProcessorRef.current = scriptProcessor;

      scriptProcessor.onaudioprocess = (event) => {
        const inputData = event.inputBuffer.getChannelData(0);

        // Convert Float32 to Int16 PCM
        const pcmData = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        onAudioChunk(pcmData.buffer);
      };

      source.connect(scriptProcessor);
      scriptProcessor.connect(audioContext.destination);

      return true;
    } catch (error) {
      console.error('Failed to start audio stream:', error);
      return false;
    }
  }, [onAudioChunk]);

  const stopListening = useCallback(() => {
    if (scriptProcessorRef.current) {
      scriptProcessorRef.current.disconnect();
      scriptProcessorRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
  }, []);

  // Internal function to play a single audio segment
  const playAudioSegment = useCallback(async (base64Audio: string, sampleRate: number): Promise<void> => {
    try {
      // Create or reuse playback context
      if (!playbackContextRef.current || playbackContextRef.current.state === 'closed') {
        playbackContextRef.current = new AudioContext({ sampleRate });
      }

      const context = playbackContextRef.current;

      // Decode base64 to ArrayBuffer
      const binaryString = atob(base64Audio);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // Convert Int16 to Float32
      const int16Array = new Int16Array(bytes.buffer);
      const float32Array = new Float32Array(int16Array.length);
      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768;
      }

      // Create audio buffer
      const audioBuffer = context.createBuffer(1, float32Array.length, sampleRate);
      audioBuffer.getChannelData(0).set(float32Array);

      // Play the audio
      const source = context.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(context.destination);
      source.start();

      // Return a promise that resolves when playback ends
      return new Promise<void>((resolve) => {
        source.onended = () => resolve();
      });
    } catch (error) {
      console.error('Failed to play audio:', error);
    }
  }, []);

  // Process the audio queue sequentially
  const processAudioQueue = useCallback(async () => {
    if (isPlayingRef.current) return;
    
    isPlayingRef.current = true;
    
    while (audioQueueRef.current.length > 0) {
      const segment = audioQueueRef.current.shift();
      if (segment) {
        await playAudioSegment(segment.base64Audio, segment.sampleRate);
      }
    }
    
    isPlayingRef.current = false;
  }, [playAudioSegment]);

  // Public function to queue audio for playback
  const playAudio = useCallback((base64Audio: string, sampleRate: number) => {
    audioQueueRef.current.push({ base64Audio, sampleRate });
    processAudioQueue();
  }, [processAudioQueue]);

  // Clear the audio queue (used when stopping)
  const clearAudioQueue = useCallback(() => {
    audioQueueRef.current = [];
    // Close and recreate context to stop any currently playing audio
    if (playbackContextRef.current && playbackContextRef.current.state !== 'closed') {
      playbackContextRef.current.close();
      playbackContextRef.current = null;
    }
    isPlayingRef.current = false;
  }, []);

  const cleanup = useCallback(() => {
    stopListening();
    clearAudioQueue();
  }, [stopListening, clearAudioQueue]);

  return {
    startListening,
    stopListening,
    playAudio,
    clearAudioQueue,
    cleanup,
  };
}
