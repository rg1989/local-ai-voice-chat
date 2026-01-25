"""Audio capture from microphone using sounddevice."""

import queue
import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

from ..config import settings


class AudioCapture:
    """Captures audio from the microphone in real-time."""

    def __init__(
        self,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        chunk_size: Optional[int] = None,
        dtype: Optional[str] = None,
    ):
        """Initialize audio capture.

        Args:
            sample_rate: Audio sample rate in Hz (default from settings)
            channels: Number of channels (default from settings)
            chunk_size: Samples per chunk (default from settings)
            dtype: Audio data type (default from settings)
        """
        self.sample_rate = sample_rate or settings.audio.sample_rate
        self.channels = channels or settings.audio.channels
        self.chunk_size = chunk_size or settings.audio.chunk_size
        self.dtype = dtype or settings.audio.dtype

        self._stream: Optional[sd.InputStream] = None
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._is_running = False
        self._callback: Optional[Callable[[np.ndarray], None]] = None
        self._lock = threading.Lock()

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback for audio stream."""
        if status:
            print(f"Audio capture status: {status}")

        # Copy the audio data
        audio_chunk = indata.copy().flatten()

        # Put in queue for blocking reads
        self._audio_queue.put(audio_chunk)

        # Call callback if registered
        if self._callback is not None:
            self._callback(audio_chunk)

    def start(self, callback: Optional[Callable[[np.ndarray], None]] = None) -> None:
        """Start capturing audio.

        Args:
            callback: Optional callback function called with each audio chunk
        """
        with self._lock:
            if self._is_running:
                return

            self._callback = callback
            self._is_running = True

            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=self.chunk_size,
                callback=self._audio_callback,
            )
            self._stream.start()

    def stop(self) -> None:
        """Stop capturing audio."""
        with self._lock:
            if not self._is_running:
                return

            self._is_running = False
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None

            # Clear the queue
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break

    def read(self, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        """Read the next audio chunk (blocking).

        Args:
            timeout: Maximum time to wait for audio (None = wait forever)

        Returns:
            Audio chunk as numpy array, or None if timeout
        """
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def read_all(self) -> list[np.ndarray]:
        """Read all available audio chunks (non-blocking).

        Returns:
            List of audio chunks
        """
        chunks = []
        while True:
            try:
                chunks.append(self._audio_queue.get_nowait())
            except queue.Empty:
                break
        return chunks

    @property
    def is_running(self) -> bool:
        """Check if capture is running."""
        return self._is_running

    def __enter__(self) -> "AudioCapture":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()


def list_input_devices() -> list[dict]:
    """List available audio input devices.

    Returns:
        List of device info dictionaries
    """
    devices = sd.query_devices()
    input_devices = []

    for i, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            input_devices.append(
                {
                    "index": i,
                    "name": device["name"],
                    "channels": device["max_input_channels"],
                    "sample_rate": device["default_samplerate"],
                }
            )

    return input_devices
