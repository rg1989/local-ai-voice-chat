"""Audio playback using sounddevice."""

import queue
import threading
from typing import Optional

import numpy as np
import sounddevice as sd

from ..config import settings


class AudioPlayback:
    """Plays audio through the speakers with streaming support."""

    def __init__(
        self,
        sample_rate: Optional[int] = None,
        channels: int = 1,
        dtype: str = "float32",
    ):
        """Initialize audio playback.

        Args:
            sample_rate: Audio sample rate in Hz (default from TTS settings)
            channels: Number of channels
            dtype: Audio data type
        """
        self.sample_rate = sample_rate or settings.tts.output_sample_rate
        self.channels = channels
        self.dtype = dtype

        self._stream: Optional[sd.OutputStream] = None
        self._audio_queue: queue.Queue[Optional[np.ndarray]] = queue.Queue()
        self._is_running = False
        self._is_playing = False
        self._lock = threading.Lock()
        self._play_thread: Optional[threading.Thread] = None

    def _audio_callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback for audio output stream."""
        if status:
            print(f"Audio playback status: {status}")

        try:
            data = self._audio_queue.get_nowait()
            if data is None:
                # Sentinel value - stop playback
                outdata.fill(0)
                raise sd.CallbackStop()

            # Handle size mismatch
            if len(data) < frames:
                outdata[:len(data), 0] = data
                outdata[len(data):] = 0
            else:
                outdata[:, 0] = data[:frames]

        except queue.Empty:
            outdata.fill(0)

    def start(self) -> None:
        """Start the playback stream."""
        with self._lock:
            if self._is_running:
                return

            self._is_running = True
            self._stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                callback=self._audio_callback,
            )
            self._stream.start()

    def stop(self) -> None:
        """Stop the playback stream."""
        with self._lock:
            if not self._is_running:
                return

            self._is_running = False
            self._audio_queue.put(None)  # Sentinel to stop callback

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

    def play(self, audio: np.ndarray, blocking: bool = True) -> None:
        """Play audio data.

        Args:
            audio: Audio data as numpy array
            blocking: If True, wait for playback to complete
        """
        if blocking:
            sd.play(audio, samplerate=self.sample_rate)
            sd.wait()
        else:
            sd.play(audio, samplerate=self.sample_rate)

    def play_stream(self, audio_chunk: np.ndarray) -> None:
        """Add audio chunk to streaming playback queue.

        Args:
            audio_chunk: Audio data to queue for playback
        """
        if not self._is_running:
            self.start()

        self._audio_queue.put(audio_chunk)

    def wait(self) -> None:
        """Wait for all queued audio to finish playing."""
        while not self._audio_queue.empty():
            sd.sleep(10)

    def clear(self) -> None:
        """Clear all queued audio."""
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

    @property
    def is_running(self) -> bool:
        """Check if playback stream is running."""
        return self._is_running

    def __enter__(self) -> "AudioPlayback":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()


def play_audio_file(filepath: str, sample_rate: Optional[int] = None) -> None:
    """Play an audio file.

    Args:
        filepath: Path to audio file
        sample_rate: Sample rate (auto-detected if None)
    """
    from scipy.io import wavfile

    sr, audio = wavfile.read(filepath)
    sample_rate = sample_rate or sr

    # Normalize to float32
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    elif audio.dtype == np.int32:
        audio = audio.astype(np.float32) / 2147483648.0

    sd.play(audio, samplerate=sample_rate)
    sd.wait()


def list_output_devices() -> list[dict]:
    """List available audio output devices.

    Returns:
        List of device info dictionaries
    """
    devices = sd.query_devices()
    output_devices = []

    for i, device in enumerate(devices):
        if device["max_output_channels"] > 0:
            output_devices.append(
                {
                    "index": i,
                    "name": device["name"],
                    "channels": device["max_output_channels"],
                    "sample_rate": device["default_samplerate"],
                }
            )

    return output_devices
