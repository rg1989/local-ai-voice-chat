"""Voice Activity Detection using Silero VAD."""

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

import numpy as np
import torch

from ..config import settings


class SpeechState(Enum):
    """Current speech detection state."""

    SILENCE = "silence"
    SPEECH_START = "speech_start"
    SPEAKING = "speaking"
    SPEECH_END = "speech_end"


@dataclass
class VADResult:
    """Result from VAD processing."""

    state: SpeechState
    confidence: float
    audio_chunk: np.ndarray


class VoiceActivityDetector:
    """Detects voice activity using Silero VAD model."""

    # Minimum samples required by Silero VAD (512 samples at 16kHz = 32ms)
    MIN_SAMPLES = 512

    def __init__(
        self,
        threshold: Optional[float] = None,
        min_speech_duration_ms: Optional[int] = None,
        min_silence_duration_ms: Optional[int] = None,
        speech_pad_ms: Optional[int] = None,
        sample_rate: int = 16000,
    ):
        """Initialize VAD.

        Args:
            threshold: Speech detection threshold (0-1)
            min_speech_duration_ms: Minimum speech duration to trigger
            min_silence_duration_ms: Silence duration to end speech segment
            speech_pad_ms: Padding around speech segments
            sample_rate: Audio sample rate (must be 8000 or 16000)
        """
        self.threshold = threshold or settings.vad.threshold
        self.min_speech_duration_ms = (
            min_speech_duration_ms or settings.vad.min_speech_duration_ms
        )
        self.min_silence_duration_ms = (
            min_silence_duration_ms or settings.vad.min_silence_duration_ms
        )
        self.speech_pad_ms = speech_pad_ms or settings.vad.speech_pad_ms
        self.sample_rate = sample_rate

        # Load Silero VAD model
        self._model, self._utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        self._model.eval()

        # State tracking
        self._is_speaking = False
        self._speech_samples = 0
        self._silence_samples = 0
        self._speech_buffer: deque[np.ndarray] = deque(maxlen=50)  # Buffer for padding

        # Callbacks
        self._on_speech_start: Optional[Callable[[], None]] = None
        self._on_speech_end: Optional[Callable[[np.ndarray], None]] = None

        # Accumulated speech audio
        self._current_speech: list[np.ndarray] = []
        
        # Final speech audio after SPEECH_END (for retrieval)
        self._final_speech_audio: Optional[np.ndarray] = None
        
        # Buffer for accumulating small chunks
        self._chunk_buffer: list[np.ndarray] = []
        self._chunk_buffer_samples = 0

    def _samples_to_ms(self, samples: int) -> float:
        """Convert samples to milliseconds."""
        return (samples / self.sample_rate) * 1000

    def _ms_to_samples(self, ms: float) -> int:
        """Convert milliseconds to samples."""
        return int((ms / 1000) * self.sample_rate)

    def process(self, audio_chunk: np.ndarray) -> VADResult:
        """Process an audio chunk and detect speech.

        Args:
            audio_chunk: Audio data as numpy array (float32, -1 to 1)

        Returns:
            VADResult with state, confidence, and audio chunk
        """
        # Ensure correct dtype
        if audio_chunk.dtype != np.float32:
            audio_chunk = audio_chunk.astype(np.float32)

        # Buffer audio chunks
        self._chunk_buffer.append(audio_chunk)
        self._chunk_buffer_samples += len(audio_chunk)
        
        if self._chunk_buffer_samples < self.MIN_SAMPLES:
            # Not enough samples yet, return silence state
            return VADResult(state=SpeechState.SILENCE, confidence=0.0, audio_chunk=audio_chunk)
        
        # Concatenate buffered chunks
        all_audio = np.concatenate(self._chunk_buffer)
        
        # Process ALL available MIN_SAMPLES chunks to avoid backlog
        state = SpeechState.SILENCE
        speech_prob = 0.0
        processed_audio = []
        
        while len(all_audio) >= self.MIN_SAMPLES:
            # Take exactly MIN_SAMPLES (512) for VAD
            vad_audio = all_audio[:self.MIN_SAMPLES]
            all_audio = all_audio[self.MIN_SAMPLES:]
            processed_audio.append(vad_audio)
            
            # Convert to torch tensor - must be exactly 512 samples
            audio_tensor = torch.from_numpy(vad_audio)

            # Get speech probability
            with torch.no_grad():
                speech_prob = self._model(audio_tensor, self.sample_rate).item()
            
            # Add to buffer for padding
            self._speech_buffer.append(vad_audio)

            is_speech = speech_prob >= self.threshold

            if is_speech:
                self._silence_samples = 0
                self._speech_samples += len(vad_audio)
                self._current_speech.append(vad_audio)

                if not self._is_speaking:
                    # Check if we've accumulated enough speech
                    if self._samples_to_ms(self._speech_samples) >= self.min_speech_duration_ms:
                        self._is_speaking = True
                        state = SpeechState.SPEECH_START

                        # Add padding from buffer
                        pad_samples = self._ms_to_samples(self.speech_pad_ms)
                        buffer_list = list(self._speech_buffer)
                        if len(buffer_list) > 1:
                            pre_speech = np.concatenate(buffer_list[:-1])[-pad_samples:]
                            self._current_speech.insert(0, pre_speech)

                        if self._on_speech_start:
                            self._on_speech_start()
                else:
                    state = SpeechState.SPEAKING

            else:
                self._silence_samples += len(vad_audio)

                if self._is_speaking:
                    # Still in speech segment, accumulate
                    self._current_speech.append(vad_audio)
                    state = SpeechState.SPEAKING

                    # Check if silence is long enough to end speech
                    if self._samples_to_ms(self._silence_samples) >= self.min_silence_duration_ms:
                        self._is_speaking = False
                        state = SpeechState.SPEECH_END

                        # Get accumulated speech audio and store for retrieval
                        speech_audio = np.concatenate(self._current_speech)
                        self._final_speech_audio = speech_audio

                        if self._on_speech_end:
                            self._on_speech_end(speech_audio)

                        # Reset current speech buffer
                        self._current_speech = []
                        self._speech_samples = 0
                        
                        # Break early on speech end to process it
                        break
                else:
                    # Not speaking, reset speech counter
                    self._speech_samples = 0
                    self._current_speech = []
        
        # Update buffer with remaining samples
        if len(all_audio) > 0:
            self._chunk_buffer = [all_audio]
            self._chunk_buffer_samples = len(all_audio)
        else:
            self._chunk_buffer = []
            self._chunk_buffer_samples = 0

        # Return the combined processed audio
        combined_audio = np.concatenate(processed_audio) if processed_audio else audio_chunk
        return VADResult(state=state, confidence=speech_prob, audio_chunk=combined_audio)

    def get_speech_audio(self) -> Optional[np.ndarray]:
        """Get accumulated speech audio if speech ended.

        Returns:
            Concatenated speech audio or None
        """
        # Return the final speech audio that was stored when SPEECH_END was detected
        if self._final_speech_audio is not None:
            audio = self._final_speech_audio
            self._final_speech_audio = None
            return audio
        return None

    def reset(self) -> None:
        """Reset VAD state."""
        self._is_speaking = False
        self._speech_samples = 0
        self._silence_samples = 0
        self._current_speech = []
        self._final_speech_audio = None
        self._speech_buffer.clear()
        self._chunk_buffer = []
        self._chunk_buffer_samples = 0
        self._model.reset_states()

    def on_speech_start(self, callback: Callable[[], None]) -> None:
        """Register callback for speech start event.

        Args:
            callback: Function to call when speech starts
        """
        self._on_speech_start = callback

    def on_speech_end(self, callback: Callable[[np.ndarray], None]) -> None:
        """Register callback for speech end event.

        Args:
            callback: Function to call with speech audio when speech ends
        """
        self._on_speech_end = callback

    @property
    def is_speaking(self) -> bool:
        """Check if currently detecting speech."""
        return self._is_speaking
