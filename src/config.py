"""Configuration settings for the voice chatbot."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AudioSettings(BaseSettings):
    """Audio capture and playback settings."""

    model_config = SettingsConfigDict(env_prefix="AUDIO_")

    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    channels: int = Field(default=1, description="Number of audio channels (1=mono)")
    chunk_duration_ms: int = Field(default=64, description="Audio chunk duration in milliseconds (min 32ms for VAD)")
    dtype: str = Field(default="float32", description="Audio data type")

    @property
    def chunk_size(self) -> int:
        """Calculate chunk size in samples."""
        return int(self.sample_rate * self.chunk_duration_ms / 1000)


class VADSettings(BaseSettings):
    """Voice Activity Detection settings."""

    model_config = SettingsConfigDict(env_prefix="VAD_")

    threshold: float = Field(default=0.5, description="Speech detection threshold (0-1)")
    min_speech_duration_ms: int = Field(
        default=250, description="Minimum speech duration to trigger"
    )
    min_silence_duration_ms: int = Field(
        default=500, description="Silence duration to end speech segment"
    )
    speech_pad_ms: int = Field(default=30, description="Padding around speech segments")


class STTSettings(BaseSettings):
    """Speech-to-Text settings (MLX Whisper - optimized for Apple Silicon).
    
    Note: MLX Whisper uses greedy decoding only (beam search not yet implemented).
    This is already the fastest decoding method.
    """

    model_config = SettingsConfigDict(env_prefix="STT_")

    model_name: str = Field(
        default="mlx-community/whisper-large-v3-turbo",
        description="MLX Whisper model (mlx-community/whisper-tiny, small, large-v3, large-v3-turbo)",
    )
    language: str = Field(default="en", description="Language code for transcription")
    condition_on_previous_text: bool = Field(
        default=False,
        description="Condition on previous text (False=faster for single utterances)",
    )


class ToolSettings(BaseSettings):
    """Tool execution settings."""

    model_config = SettingsConfigDict(env_prefix="TOOLS_")

    enabled: bool = Field(default=True, description="Enable tool use capabilities")
    require_confirmation: bool = Field(
        default=False, description="Require confirmation for dangerous tools"
    )
    fetch_timeout: float = Field(default=30.0, description="Timeout for URL fetches")
    command_timeout: float = Field(default=30.0, description="Timeout for command execution")
    max_content_length: int = Field(
        default=8000, description="Max characters to include from fetched content"
    )


class LLMSettings(BaseSettings):
    """Large Language Model settings."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    base_url: str = Field(
        default="http://localhost:11434", description="Ollama API base URL"
    )
    model_name: str = Field(default="qwen3:8b", description="LLM model name in Ollama")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    max_tokens: int = Field(default=512, description="Maximum tokens to generate")
    system_prompt: str = Field(
        default=(
            "You are a helpful, friendly assistant. Keep responses clear and well-structured. "
            "When asked to create diagrams, flowcharts, or visualizations, use mermaid syntax "
            "in a ```mermaid code block. When presenting tabular data, use markdown tables. "
            "Use code blocks with language tags for code examples. Use bold, italic, and lists "
            "for clarity when appropriate. Be concise but thorough."
        ),
        description="System prompt for the assistant",
    )


class TTSSettings(BaseSettings):
    """Text-to-Speech settings."""

    model_config = SettingsConfigDict(env_prefix="TTS_")

    voice: str = Field(default="af_heart", description="Kokoro voice to use")
    speed: float = Field(default=1.1, description="Speech speed multiplier (1.1 for snappier responses)")
    output_sample_rate: int = Field(default=24000, description="Output audio sample rate")


class WakeWordSettings(BaseSettings):
    """Wake word detection settings."""

    model_config = SettingsConfigDict(env_prefix="WAKEWORD_")

    enabled: bool = Field(default=False, description="Enable wake word detection (off by default)")
    model: str = Field(default="hey_jarvis", description="Wake word model name")
    threshold: float = Field(default=0.5, description="Detection confidence threshold (0-1)")
    timeout_seconds: int = Field(default=10, description="Seconds to stay active after wake word")
    debounce_ms: int = Field(default=1000, description="Milliseconds to wait before allowing re-trigger")


class WebSettings(BaseSettings):
    """Web interface settings."""

    model_config = SettingsConfigDict(env_prefix="WEB_")

    host: str = Field(default="0.0.0.0", description="Web server host")
    port: int = Field(default=8000, description="Web server port")


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Nested settings
    audio: AudioSettings = Field(default_factory=AudioSettings)
    vad: VADSettings = Field(default_factory=VADSettings)
    stt: STTSettings = Field(default_factory=STTSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    wakeword: WakeWordSettings = Field(default_factory=WakeWordSettings)

    # Paths
    models_dir: Path = Field(
        default=Path.home() / ".cache" / "voice-chatbot" / "models",
        description="Directory for cached models",
    )

    # Debug settings
    debug: bool = Field(default=False, description="Enable debug logging")
    log_audio: bool = Field(default=False, description="Log audio to files for debugging")

    def ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.models_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
