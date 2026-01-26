"""Wake word detection using OpenWakeWord."""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

import numpy as np

from ..config import settings


class WakeWordState(Enum):
    """Current wake word detection state."""

    LISTENING = "listening"  # Waiting for wake word
    ACTIVE = "active"  # Wake word detected, forwarding to VAD
    DISABLED = "disabled"  # Wake word detection is off


@dataclass
class WakeWordResult:
    """Result from wake word processing."""

    state: WakeWordState
    detected: bool
    confidence: float
    model_name: str


class WakeWordDetector:
    """Detects wake words using OpenWakeWord."""

    # Available pre-trained models
    AVAILABLE_MODELS = {
        "hey_jarvis": "Hey Jarvis",
        "alexa": "Alexa",
        "hey_mycroft": "Hey Mycroft",
        "hey_rhasspy": "Hey Rhasspy",
    }

    def __init__(
        self,
        enabled: Optional[bool] = None,
        model: Optional[str] = None,
        threshold: Optional[float] = None,
        timeout_seconds: Optional[int] = None,
        debounce_ms: Optional[int] = None,
        sample_rate: int = 16000,
    ):
        """Initialize wake word detector.

        Args:
            enabled: Whether wake word detection is enabled
            model: Wake word model name (e.g., "hey_jarvis")
            threshold: Detection confidence threshold (0-1)
            timeout_seconds: Seconds to stay active after wake word
            debounce_ms: Milliseconds before allowing re-trigger
            sample_rate: Audio sample rate (must be 16000 for OpenWakeWord)
        """
        self.enabled = enabled if enabled is not None else settings.wakeword.enabled
        self.model_name = model or settings.wakeword.model
        self.threshold = threshold if threshold is not None else settings.wakeword.threshold
        self.timeout_seconds = timeout_seconds or settings.wakeword.timeout_seconds
        self.debounce_ms = debounce_ms or settings.wakeword.debounce_ms
        self.sample_rate = sample_rate

        # State tracking
        self._state = WakeWordState.DISABLED if not self.enabled else WakeWordState.LISTENING
        self._last_detection_time: float = 0
        self._active_start_time: float = 0
        self._is_speaking = False  # For echo cancellation
        self._is_processing = False  # For preventing timeout during AI response

        # Callbacks
        self._on_wake_detected: Optional[Callable[[], None]] = None
        self._on_timeout: Optional[Callable[[], None]] = None

        # OpenWakeWord model (lazy loaded)
        self._oww_model = None
        self._models_downloaded = False
        self._loading = False
        self._load_error: Optional[str] = None
        self._prediction_key: Optional[str] = None  # Cached key for prediction matching
        self._debug_counter = 0

    def _ensure_loaded(self) -> bool:
        """Ensure OpenWakeWord model is loaded.
        
        Returns:
            True if model is loaded, False if still loading or failed
        """
        if self._oww_model is not None:
            return True
        
        if self._loading:
            return False  # Still loading in background

        try:
            import openwakeword
            from openwakeword.model import Model

            # Download models if needed (one-time)
            if not self._models_downloaded:
                print("[WAKEWORD] Downloading models...")
                openwakeword.utils.download_models()
                self._models_downloaded = True
                print("[WAKEWORD] Models downloaded")

            # Initialize the model
            # OpenWakeWord expects model names without version suffixes for built-in models
            print(f"[WAKEWORD] Loading model: {self.model_name}")
            try:
                self._oww_model = Model(
                    wakeword_models=[self.model_name],
                    inference_framework="onnx",  # Use ONNX for cross-platform compatibility
                )
            except Exception as model_error:
                # Try loading all available models if specific model fails
                print(f"[WAKEWORD] Specific model failed: {model_error}, loading default models")
                self._oww_model = Model(inference_framework="onnx")
            
            # Log what models were actually loaded
            if hasattr(self._oww_model, 'models'):
                print(f"[WAKEWORD] Loaded models: {list(self._oww_model.models.keys())}")
            print(f"[WAKEWORD] Model loaded successfully")
            return True
        except ImportError:
            print("[WAKEWORD] OpenWakeWord is not installed")
            return False
        except Exception as e:
            print(f"[WAKEWORD] Failed to load model: {e}")
            return False

    def process(self, audio_chunk: np.ndarray) -> WakeWordResult:
        """Process an audio chunk for wake word detection.

        Args:
            audio_chunk: Audio data as numpy array (float32 or int16, 16kHz)

        Returns:
            WakeWordResult with state and detection info
        """
        # If disabled, always return disabled state
        if not self.enabled:
            return WakeWordResult(
                state=WakeWordState.DISABLED,
                detected=False,
                confidence=0.0,
                model_name=self.model_name,
            )

        # If speaking (echo cancellation), skip detection
        if self._is_speaking:
            return WakeWordResult(
                state=self._state,
                detected=False,
                confidence=0.0,
                model_name=self.model_name,
            )

        # Check for timeout if active (but not while processing AI response)
        if self._state == WakeWordState.ACTIVE and not self._is_processing:
            elapsed = time.time() - self._active_start_time
            if elapsed >= self.timeout_seconds:
                self._state = WakeWordState.LISTENING
                if self._on_timeout:
                    self._on_timeout()

        # If already active, return current state
        if self._state == WakeWordState.ACTIVE:
            return WakeWordResult(
                state=WakeWordState.ACTIVE,
                detected=False,
                confidence=0.0,
                model_name=self.model_name,
            )

        # Ensure model is loaded - if not ready, return listening state
        if not self._ensure_loaded():
            return WakeWordResult(
                state=WakeWordState.LISTENING,
                detected=False,
                confidence=0.0,
                model_name=self.model_name,
            )

        # Convert audio to int16 if needed (OpenWakeWord expects int16)
        if audio_chunk.dtype == np.float32:
            # Convert from float32 [-1, 1] to int16 [-32768, 32767]
            audio_int16 = (audio_chunk * 32767).astype(np.int16)
        elif audio_chunk.dtype == np.int16:
            audio_int16 = audio_chunk
        else:
            audio_int16 = audio_chunk.astype(np.int16)

        # Get predictions from OpenWakeWord
        predictions = self._oww_model.predict(audio_int16)

        # Check if wake word detected
        detected = False
        confidence = 0.0

        # Debug: log predictions periodically (every ~2 seconds worth of audio at 4096 samples/chunk)
        self._debug_counter += 1
        if self._debug_counter % 30 == 0:  # Log every ~30 chunks (~7.5 seconds)
            print(f"[WAKEWORD DEBUG] Model: {self.model_name}, Predictions: {predictions}, Threshold: {self.threshold}")

        # If we already found the matching key, use it directly
        if self._prediction_key and self._prediction_key in predictions:
            confidence = predictions[self._prediction_key]
            if confidence > 0.2:  # Log when there's notable activation
                print(f"[WAKEWORD] {self._prediction_key}: {confidence:.3f} (threshold: {self.threshold})")
        else:
            # Find the matching prediction key
            # OpenWakeWord returns keys like "hey_jarvis" or sometimes with version suffixes
            model_name_normalized = self.model_name.lower().replace('-', '_')
            
            for model_key in predictions.keys():
                key_normalized = model_key.lower().replace('-', '_')
                
                # Exact match
                if key_normalized == model_name_normalized:
                    self._prediction_key = model_key
                    confidence = predictions[model_key]
                    print(f"[WAKEWORD] Found exact match: {model_key}")
                    break
                # Key contains our model name
                elif model_name_normalized in key_normalized:
                    self._prediction_key = model_key
                    confidence = predictions[model_key]
                    print(f"[WAKEWORD] Found partial match: {model_key} contains {model_name_normalized}")
                    break
                # Our model name contains the key
                elif key_normalized in model_name_normalized:
                    self._prediction_key = model_key
                    confidence = predictions[model_key]
                    print(f"[WAKEWORD] Found partial match: {model_name_normalized} contains {key_normalized}")
                    break
            else:
                # Fallback: use the first prediction and log warning
                if predictions:
                    first_key = list(predictions.keys())[0]
                    self._prediction_key = first_key
                    confidence = predictions[first_key]
                    print(f"[WAKEWORD] WARNING: No match for '{self.model_name}', using '{first_key}'")

        # Check threshold and debounce
        current_time = time.time()
        time_since_last = (current_time - self._last_detection_time) * 1000  # ms

        if confidence >= self.threshold and time_since_last >= self.debounce_ms:
            detected = True
            self._last_detection_time = current_time
            self._active_start_time = current_time
            self._state = WakeWordState.ACTIVE

            if self._on_wake_detected:
                self._on_wake_detected()

        return WakeWordResult(
            state=self._state,
            detected=detected,
            confidence=confidence,
            model_name=self.model_name,
        )

    def set_active(self) -> None:
        """Manually set state to active (e.g., when speech starts)."""
        if self.enabled:
            self._state = WakeWordState.ACTIVE
            self._active_start_time = time.time()

    def set_listening(self) -> None:
        """Return to listening state."""
        if self.enabled:
            self._state = WakeWordState.LISTENING

    def reset_timeout(self) -> None:
        """Reset the active timeout (e.g., when user is still speaking)."""
        self._active_start_time = time.time()

    def set_speaking(self, is_speaking: bool) -> None:
        """Set speaking state for echo cancellation.

        Args:
            is_speaking: True if TTS is currently playing
        """
        self._is_speaking = is_speaking

    def set_processing(self, is_processing: bool) -> None:
        """Set processing state - prevents timeout during AI response.

        Args:
            is_processing: True when transcribing, thinking, or speaking
        """
        self._is_processing = is_processing
        if is_processing:
            self.reset_timeout()  # Keep timeout fresh

    def update_settings(
        self,
        enabled: Optional[bool] = None,
        model: Optional[str] = None,
        threshold: Optional[float] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        """Update wake word settings dynamically.

        Args:
            enabled: Enable/disable wake word detection
            model: New model name (requires reload)
            threshold: New detection threshold
            timeout_seconds: New timeout value
        """
        if enabled is not None:
            self.enabled = enabled
            if enabled:
                self._state = WakeWordState.LISTENING
            else:
                self._state = WakeWordState.DISABLED

        if threshold is not None:
            self.threshold = threshold

        if timeout_seconds is not None:
            self.timeout_seconds = timeout_seconds

        if model is not None and model != self.model_name:
            self.model_name = model
            self._oww_model = None  # Force reload on next process
            self._prediction_key = None  # Reset cached key

    def on_wake_detected(self, callback: Callable[[], None]) -> None:
        """Register callback for wake word detection.

        Args:
            callback: Function to call when wake word is detected
        """
        self._on_wake_detected = callback

    def on_timeout(self, callback: Callable[[], None]) -> None:
        """Register callback for timeout (return to listening).

        Args:
            callback: Function to call when timeout occurs
        """
        self._on_timeout = callback

    @property
    def state(self) -> WakeWordState:
        """Get current wake word state."""
        return self._state

    @property
    def is_active(self) -> bool:
        """Check if currently in active mode (forwarding to VAD)."""
        return self._state == WakeWordState.ACTIVE

    @property
    def is_listening(self) -> bool:
        """Check if currently listening for wake word."""
        return self._state == WakeWordState.LISTENING

    def reset(self) -> None:
        """Reset detector state."""
        self._state = WakeWordState.DISABLED if not self.enabled else WakeWordState.LISTENING
        self._last_detection_time = 0
        self._active_start_time = 0
        self._is_speaking = False
        self._is_processing = False
        self._prediction_key = None
        self._debug_counter = 0
        if self._oww_model is not None:
            self._oww_model.reset()

    def get_settings(self) -> dict:
        """Get current settings as a dictionary."""
        return {
            "enabled": self.enabled,
            "model": self.model_name,
            "threshold": self.threshold,
            "timeoutSeconds": self.timeout_seconds,
            "ready": self.is_ready,
        }

    @classmethod
    def get_available_models(cls) -> dict[str, str]:
        """Get available pre-trained wake word models.

        Returns:
            Dict mapping model name to display name
        """
        return cls.AVAILABLE_MODELS.copy()

    def preload_model(self) -> None:
        """Pre-load the wake word model synchronously.
        
        Call this when settings are updated to ensure model is ready.
        """
        if self.enabled and self._oww_model is None:
            self._ensure_loaded()

    @property
    def is_ready(self) -> bool:
        """Check if wake word detector is ready to process audio."""
        if not self.enabled:
            return True  # Always "ready" when disabled
        return self._oww_model is not None
