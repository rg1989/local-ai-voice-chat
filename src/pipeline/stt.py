"""Speech-to-Text with cross-platform support.

Uses MLX Whisper on macOS (Apple Silicon) and faster-whisper on Linux.
"""

from dataclasses import dataclass
from typing import AsyncIterator, Optional
import tempfile
import os
import sys

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


# Detect platform for backend selection
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform == "linux"


class SpeechToText:
    """Transcribes speech using the best available backend.
    
    - macOS: MLX Whisper (optimized for Apple Silicon, ~2x faster)
    - Linux: faster-whisper (CTranslate2 backend, works with CPU/CUDA)
    """

    # Available models - maps to appropriate backend models
    MODELS_MLX = {
        "mlx-community/whisper-tiny": "Fastest, least accurate (~74MB)",
        "mlx-community/whisper-base": "Fast, decent accuracy (~140MB)",
        "mlx-community/whisper-small": "Good balance (~460MB)",
        "mlx-community/whisper-medium": "High accuracy (~1.5GB)",
        "mlx-community/whisper-large-v3": "Best accuracy (~3GB)",
        "mlx-community/whisper-large-v3-turbo": "Fast and accurate, recommended (~1.5GB)",
    }
    
    MODELS_FASTER_WHISPER = {
        "tiny": "Fastest, least accurate (~74MB)",
        "base": "Fast, decent accuracy (~140MB)",
        "small": "Good balance (~460MB)",
        "medium": "High accuracy (~1.5GB)",
        "large-v3": "Best accuracy (~3GB)",
        "large-v3-turbo": "Fast and accurate, recommended (~1.5GB)",
    }

    def __init__(
        self,
        model_name: Optional[str] = None,
        language: Optional[str] = None,
    ):
        """Initialize STT.

        Args:
            model_name: Model name (auto-converted for platform)
            language: Language code for transcription
        """
        self.model_name = model_name or settings.stt.model_name
        self.language = language or settings.stt.language
        self.condition_on_previous_text = settings.stt.condition_on_previous_text

        self._backend = None  # 'mlx' or 'faster_whisper'
        self._model = None
        self._mlx_whisper = None
        self._loaded = False

    def _get_model_for_backend(self) -> str:
        """Convert model name for the current backend."""
        if self._backend == "mlx":
            # Already MLX format or convert
            if self.model_name.startswith("mlx-community/"):
                return self.model_name
            # Convert short name to MLX format
            return f"mlx-community/whisper-{self.model_name}"
        else:
            # faster-whisper uses short names
            if self.model_name.startswith("mlx-community/whisper-"):
                return self.model_name.replace("mlx-community/whisper-", "")
            return self.model_name

    def _ensure_loaded(self) -> None:
        """Load the appropriate backend for the platform."""
        if self._loaded:
            return

        # Try MLX Whisper first (macOS)
        if IS_MACOS:
            try:
                import mlx_whisper
                self._mlx_whisper = mlx_whisper
                self._backend = "mlx"
                self._loaded = True
                print(f"[STT] Using MLX Whisper with model: {self._get_model_for_backend()}")
                return
            except ImportError:
                print("[STT] MLX Whisper not available, trying faster-whisper...")

        # Try faster-whisper (Linux or fallback)
        try:
            from faster_whisper import WhisperModel
            model_name = self._get_model_for_backend()
            
            # Determine compute type based on available hardware
            import torch
            if torch.cuda.is_available():
                device = "cuda"
                compute_type = "float16"
                print(f"[STT] Using faster-whisper with CUDA acceleration")
            else:
                device = "cpu"
                compute_type = "int8"
                print(f"[STT] Using faster-whisper with CPU (int8)")
            
            self._model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
            )
            self._backend = "faster_whisper"
            self._loaded = True
            print(f"[STT] Loaded faster-whisper model: {model_name}")
            return
        except ImportError:
            pass

        # No backend available
        if IS_MACOS:
            raise ImportError(
                "No STT backend available. Install mlx-whisper: pip install mlx-whisper"
            )
        else:
            raise ImportError(
                "No STT backend available. Install faster-whisper: pip install faster-whisper"
            )

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

        if self._backend == "mlx":
            return self._transcribe_mlx(audio, duration)
        else:
            return self._transcribe_faster_whisper(audio, duration)

    def _transcribe_mlx(self, audio: np.ndarray, duration: float) -> TranscriptionResult:
        """Transcribe using MLX Whisper."""
        # MLX Whisper requires audio file path, so write to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            # Convert to 16-bit PCM for wav file
            audio_int16 = (audio * 32767).astype(np.int16)
            wavfile.write(temp_path, 16000, audio_int16)

        try:
            result = self._mlx_whisper.transcribe(
                temp_path,
                path_or_hf_repo=self._get_model_for_backend(),
                language=self.language,
                condition_on_previous_text=self.condition_on_previous_text,
            )

            text = result.get("text", "").strip()
            language = result.get("language", self.language)

            return TranscriptionResult(
                text=text,
                language=language,
                confidence=1.0,
                duration_seconds=duration,
            )
        finally:
            os.unlink(temp_path)

    def _transcribe_faster_whisper(self, audio: np.ndarray, duration: float) -> TranscriptionResult:
        """Transcribe using faster-whisper."""
        segments, info = self._model.transcribe(
            audio,
            language=self.language,
            condition_on_previous_text=self.condition_on_previous_text,
            vad_filter=True,  # Use VAD to filter silence
        )

        # Collect all segments
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text)

        text = "".join(text_parts).strip()

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
