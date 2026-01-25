"""Text-to-Speech using Kokoro with MLX backend for Apple Silicon."""

from dataclasses import dataclass
from typing import AsyncIterator, Iterator, Optional

import numpy as np

from ..config import settings


@dataclass
class AudioSegment:
    """Audio segment from TTS."""

    audio: np.ndarray
    sample_rate: int
    text: str
    duration_seconds: float


class TextToSpeech:
    """Text-to-Speech using Kokoro optimized for Apple Silicon."""

    # Available Kokoro voices
    VOICES = {
        # American English
        "af_heart": "American Female - Heart (warm, friendly)",
        "af_bella": "American Female - Bella",
        "af_sarah": "American Female - Sarah",
        "af_nicole": "American Female - Nicole",
        "af_sky": "American Female - Sky",
        "am_adam": "American Male - Adam",
        "am_michael": "American Male - Michael",
        # British English
        "bf_emma": "British Female - Emma",
        "bf_isabella": "British Female - Isabella",
        "bm_george": "British Male - George",
        "bm_lewis": "British Male - Lewis",
    }

    def __init__(
        self,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        sample_rate: Optional[int] = None,
    ):
        """Initialize TTS.

        Args:
            voice: Voice name to use
            speed: Speech speed multiplier
            sample_rate: Output sample rate
        """
        self.voice = voice or settings.tts.voice
        self.speed = speed or settings.tts.speed
        self.sample_rate = sample_rate or settings.tts.output_sample_rate

        self._pipeline = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy load the model."""
        if self._loaded:
            return

        try:
            from kokoro import KPipeline

            # Initialize Kokoro pipeline
            # Use 'a' for American English, 'b' for British English
            lang_code = 'a' if self.voice.startswith('a') else 'b'
            self._pipeline = KPipeline(lang_code=lang_code)
            self._loaded = True
            print(f"Loaded Kokoro TTS with voice: {self.voice}")

        except ImportError as e:
            raise ImportError(
                "kokoro is required for TTS. Install with: pip install kokoro"
            ) from e

    def synthesize(self, text: str) -> AudioSegment:
        """Synthesize speech from text.

        Args:
            text: Text to synthesize

        Returns:
            AudioSegment with audio data
        """
        self._ensure_loaded()

        if not text.strip():
            return AudioSegment(
                audio=np.array([], dtype=np.float32),
                sample_rate=self.sample_rate,
                text=text,
                duration_seconds=0.0,
            )

        # Generate audio using Kokoro
        # The pipeline returns a generator of (graphemes, phonemes, audio) tuples
        audio_chunks = []

        for _, _, audio in self._pipeline(
            text,
            voice=self.voice,
            speed=self.speed,
        ):
            audio_chunks.append(audio)

        if not audio_chunks:
            return AudioSegment(
                audio=np.array([], dtype=np.float32),
                sample_rate=self.sample_rate,
                text=text,
                duration_seconds=0.0,
            )

        # Concatenate all audio chunks
        full_audio = np.concatenate(audio_chunks)

        # Calculate duration
        duration = len(full_audio) / self.sample_rate

        return AudioSegment(
            audio=full_audio,
            sample_rate=self.sample_rate,
            text=text,
            duration_seconds=duration,
        )

    async def synthesize_async(self, text: str) -> AudioSegment:
        """Synthesize speech asynchronously.

        Args:
            text: Text to synthesize

        Returns:
            AudioSegment with audio data
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.synthesize(text))

    def synthesize_stream(self, texts: Iterator[str]) -> Iterator[AudioSegment]:
        """Synthesize multiple text segments.

        Args:
            texts: Iterator of text segments

        Yields:
            AudioSegment for each text
        """
        for text in texts:
            if text.strip():
                yield self.synthesize(text)

    async def synthesize_stream_async(
        self, texts: AsyncIterator[str]
    ) -> AsyncIterator[AudioSegment]:
        """Synthesize multiple text segments asynchronously.

        Args:
            texts: Async iterator of text segments

        Yields:
            AudioSegment for each text
        """
        async for text in texts:
            if text.strip():
                yield await self.synthesize_async(text)

    def set_voice(self, voice: str) -> None:
        """Change the voice.

        Args:
            voice: New voice name
        """
        if voice not in self.VOICES:
            available = ", ".join(self.VOICES.keys())
            raise ValueError(f"Unknown voice: {voice}. Available: {available}")

        # Check if language changed
        old_lang = 'a' if self.voice.startswith('a') else 'b'
        new_lang = 'a' if voice.startswith('a') else 'b'

        self.voice = voice

        # Reload pipeline if language changed
        if old_lang != new_lang and self._loaded:
            self._loaded = False
            self._ensure_loaded()

    def set_speed(self, speed: float) -> None:
        """Change speech speed.

        Args:
            speed: Speed multiplier (0.5 = half speed, 2.0 = double speed)
        """
        self.speed = max(0.5, min(2.0, speed))

    @classmethod
    def list_voices(cls) -> dict[str, str]:
        """List available voices.

        Returns:
            Dict mapping voice ID to description
        """
        return cls.VOICES.copy()


class StreamingTTS:
    """Handles streaming TTS with sentence-by-sentence synthesis."""

    def __init__(self, tts: Optional[TextToSpeech] = None):
        """Initialize streaming TTS.

        Args:
            tts: TextToSpeech instance (creates new if None)
        """
        self.tts = tts or TextToSpeech()
        self._queue: list[AudioSegment] = []

    def add_sentence(self, sentence: str) -> Optional[AudioSegment]:
        """Add a sentence for synthesis.

        Args:
            sentence: Sentence to synthesize

        Returns:
            AudioSegment if synthesis completed, None if queued
        """
        if sentence.strip():
            segment = self.tts.synthesize(sentence)
            self._queue.append(segment)
            return segment
        return None

    async def add_sentence_async(self, sentence: str) -> Optional[AudioSegment]:
        """Add a sentence for async synthesis.

        Args:
            sentence: Sentence to synthesize

        Returns:
            AudioSegment if synthesis completed
        """
        if sentence.strip():
            segment = await self.tts.synthesize_async(sentence)
            self._queue.append(segment)
            return segment
        return None

    def get_all_audio(self) -> Optional[np.ndarray]:
        """Get all synthesized audio concatenated.

        Returns:
            Concatenated audio or None if empty
        """
        if not self._queue:
            return None

        audio_arrays = [seg.audio for seg in self._queue if len(seg.audio) > 0]
        if not audio_arrays:
            return None

        return np.concatenate(audio_arrays)

    def clear(self) -> None:
        """Clear the audio queue."""
        self._queue = []

    @property
    def total_duration(self) -> float:
        """Get total duration of queued audio."""
        return sum(seg.duration_seconds for seg in self._queue)
