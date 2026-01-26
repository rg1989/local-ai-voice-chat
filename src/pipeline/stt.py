"""Speech-to-Text using MLX Whisper (optimized for Apple Silicon)."""

from dataclasses import dataclass
from typing import AsyncIterator, Optional
import tempfile
import os

import numpy as np
from scipy.io import wavfile

from ..config import settings


@dataclass
class TranscriptionResult:
    """Result from speech transcription."""

    text: str
    language: str
    confidence: float
    duration_seconds: float


class SpeechToText:
    """Transcribes speech using MLX Whisper (optimized for Apple Silicon).
    
    MLX Whisper is ~2x faster than faster-whisper on Apple Silicon Macs.
    """

    # Available models on Hugging Face (mlx-community)
    MODELS = {
        "mlx-community/whisper-tiny": "Fastest, least accurate (~74MB)",
        "mlx-community/whisper-base": "Fast, decent accuracy (~140MB)",
        "mlx-community/whisper-small": "Good balance (~460MB)",
        "mlx-community/whisper-medium": "High accuracy (~1.5GB)",
        "mlx-community/whisper-large-v3": "Best accuracy (~3GB)",
        "mlx-community/whisper-large-v3-turbo": "Fast and accurate, recommended (~1.5GB)",
    }

    def __init__(
        self,
        model_name: Optional[str] = None,
        language: Optional[str] = None,
    ):
        """Initialize STT.

        Args:
            model_name: MLX Whisper model path or HuggingFace repo
            language: Language code for transcription
        """
        self.model_name = model_name or settings.stt.model_name
        self.language = language or settings.stt.language
        self.condition_on_previous_text = settings.stt.condition_on_previous_text

        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Verify mlx_whisper is available (model loads on first use)."""
        if self._loaded:
            return

        try:
            import mlx_whisper
            self._mlx_whisper = mlx_whisper
            self._loaded = True
            print(f"MLX Whisper ready with model: {self.model_name}")
        except ImportError as e:
            raise ImportError(
                "mlx-whisper is required for STT. Install with: pip install mlx-whisper"
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

        # MLX Whisper requires audio file path, so write to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            # Convert to 16-bit PCM for wav file
            audio_int16 = (audio * 32767).astype(np.int16)
            wavfile.write(temp_path, 16000, audio_int16)

        try:
            # Transcribe using MLX Whisper
            # Note: beam_size is not supported in mlx-whisper (greedy decoding only)
            result = self._mlx_whisper.transcribe(
                temp_path,
                path_or_hf_repo=self.model_name,
                language=self.language,
                condition_on_previous_text=self.condition_on_previous_text,
            )

            text = result.get("text", "").strip()
            language = result.get("language", self.language)

            return TranscriptionResult(
                text=text,
                language=language,
                confidence=1.0,  # MLX Whisper doesn't provide confidence
                duration_seconds=duration,
            )
        finally:
            # Clean up temp file
            os.unlink(temp_path)

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
