"""Speech-to-Text using Faster Whisper (CTranslate2 backend)."""

from dataclasses import dataclass
from typing import AsyncIterator, Optional

import numpy as np

from ..config import settings


@dataclass
class TranscriptionResult:
    """Result from speech transcription."""

    text: str
    language: str
    confidence: float
    duration_seconds: float


class SpeechToText:
    """Transcribes speech using Faster Whisper (CTranslate2 backend)."""

    # Available model sizes (speed vs accuracy tradeoff)
    MODELS = {
        "tiny": "Fastest, least accurate",
        "base": "Fast, decent accuracy",
        "small": "Good balance",
        "medium": "High accuracy",
        "large-v3": "Best accuracy",
        "large-v3-turbo": "Fast and accurate, recommended",
    }

    def __init__(
        self,
        model_name: Optional[str] = None,
        language: Optional[str] = None,
    ):
        """Initialize STT.

        Args:
            model_name: Whisper model size (tiny, base, small, medium, large-v3, large-v3-turbo)
            language: Language code for transcription
        """
        self.model_name = model_name or settings.stt.model_name
        self.language = language or settings.stt.language

        self._model = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy load the model."""
        if self._loaded:
            return

        try:
            from faster_whisper import WhisperModel

            print(f"Loading Faster Whisper model: {self.model_name}...")
            # Use auto device detection - will use Metal on Mac
            self._model = WhisperModel(
                self.model_name,
                device="auto",
                compute_type="auto",
            )
            self._loaded = True
            print(f"Faster Whisper model loaded: {self.model_name}")
        except ImportError as e:
            raise ImportError(
                "faster-whisper is required for STT. Install with: pip install faster-whisper"
            ) from e

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
    ) -> TranscriptionResult:
        """Transcribe audio to text.

        Args:
            audio: Audio data as numpy array (float32, mono)
            sample_rate: Sample rate of audio

        Returns:
            TranscriptionResult with transcribed text
        """
        self._ensure_loaded()

        # Ensure correct dtype
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Resample if needed (Whisper expects 16kHz)
        if sample_rate != 16000:
            from scipy import signal

            samples = int(len(audio) * 16000 / sample_rate)
            audio = signal.resample(audio, samples)

        # Calculate duration
        duration = len(audio) / 16000

        # Transcribe using Faster Whisper
        segments, info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
            vad_filter=True,  # Filter out non-speech
        )

        # Collect all segment texts
        text_parts = [segment.text for segment in segments]
        text = " ".join(text_parts).strip()

        return TranscriptionResult(
            text=text,
            language=info.language,
            confidence=info.language_probability,
            duration_seconds=duration,
        )

    async def transcribe_async(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
    ) -> TranscriptionResult:
        """Transcribe audio asynchronously.

        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate of audio

        Returns:
            TranscriptionResult with transcribed text
        """
        import asyncio

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.transcribe(audio, sample_rate)
        )

    async def transcribe_stream(
        self,
        audio_chunks: AsyncIterator[np.ndarray],
        sample_rate: int = 16000,
        chunk_duration_s: float = 5.0,
    ) -> AsyncIterator[str]:
        """Stream transcription for real-time processing.

        Buffers audio and transcribes in chunks for lower latency.

        Args:
            audio_chunks: Async iterator of audio chunks
            sample_rate: Sample rate of audio
            chunk_duration_s: Duration of audio to buffer before transcribing

        Yields:
            Transcribed text segments
        """
        self._ensure_loaded()

        buffer = []
        buffer_samples = 0
        target_samples = int(chunk_duration_s * sample_rate)

        async for chunk in audio_chunks:
            buffer.append(chunk)
            buffer_samples += len(chunk)

            if buffer_samples >= target_samples:
                # Concatenate and transcribe
                audio = np.concatenate(buffer)
                result = await self.transcribe_async(audio, sample_rate)

                if result.text:
                    yield result.text

                # Reset buffer
                buffer = []
                buffer_samples = 0

        # Process remaining audio
        if buffer:
            audio = np.concatenate(buffer)
            if len(audio) > sample_rate * 0.5:  # At least 0.5 seconds
                result = await self.transcribe_async(audio, sample_rate)
                if result.text:
                    yield result.text


class StreamingTranscriber:
    """Handles streaming transcription with buffering and VAD integration."""

    def __init__(
        self,
        stt: Optional[SpeechToText] = None,
        sample_rate: int = 16000,
    ):
        """Initialize streaming transcriber.

        Args:
            stt: SpeechToText instance (creates new if None)
            sample_rate: Audio sample rate
        """
        self.stt = stt or SpeechToText()
        self.sample_rate = sample_rate
        self._buffer: list[np.ndarray] = []

    def add_audio(self, audio_chunk: np.ndarray) -> None:
        """Add audio chunk to buffer.

        Args:
            audio_chunk: Audio data
        """
        self._buffer.append(audio_chunk)

    def transcribe_buffer(self) -> Optional[TranscriptionResult]:
        """Transcribe and clear the buffer.

        Returns:
            TranscriptionResult or None if buffer is empty
        """
        if not self._buffer:
            return None

        audio = np.concatenate(self._buffer)
        self._buffer = []

        if len(audio) < self.sample_rate * 0.3:  # Min 0.3 seconds
            return None

        return self.stt.transcribe(audio, self.sample_rate)

    def clear(self) -> None:
        """Clear the audio buffer."""
        self._buffer = []

    @property
    def buffer_duration(self) -> float:
        """Get current buffer duration in seconds."""
        if not self._buffer:
            return 0.0
        total_samples = sum(len(chunk) for chunk in self._buffer)
        return total_samples / self.sample_rate
