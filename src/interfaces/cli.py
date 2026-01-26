"""Terminal-based conversation interface."""

import signal
import sys
import threading
import time
from typing import Optional

import numpy as np
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from ..audio.capture import AudioCapture
from ..audio.playback import AudioPlayback
from ..config import settings
from ..pipeline.llm import LLMClient
from ..pipeline.sentencizer import StreamingSentencizer
from ..pipeline.stt import SpeechToText
from ..pipeline.tool_parser import tool_parser
from ..pipeline.tts import TextToSpeech
from ..pipeline.vad import SpeechState, VoiceActivityDetector
from ..pipeline.wakeword import WakeWordDetector, WakeWordState


class VoiceChatCLI:
    """Interactive voice chat in the terminal."""

    def __init__(self, preload_models: bool = True):
        """Initialize the voice chat CLI.
        
        Args:
            preload_models: If True, load STT and TTS models at startup
        """
        self.console = Console()

        # Initialize components
        self.vad = VoiceActivityDetector()
        self.wakeword = WakeWordDetector()
        self.stt = SpeechToText()
        self.llm = LLMClient()
        self.tts = TextToSpeech()
        self.sentencizer = StreamingSentencizer()

        self.audio_capture = AudioCapture()
        self.audio_playback = AudioPlayback()

        # State
        self._running = False
        self._processing = False
        self._current_transcription = ""
        self._is_speaking_tts = False  # For echo cancellation
        
        # Register wake word callbacks
        self.wakeword.on_wake_detected(self._on_wake_detected)
        self.wakeword.on_timeout(self._on_wake_timeout)
        
        # Preload models for faster first response
        if preload_models:
            self._preload_models()

    def _preload_models(self) -> None:
        """Preload STT and TTS models for faster first response."""
        self.console.print("[dim]Loading models...[/dim]")
        
        with self.console.status("[bold blue]Loading Whisper STT model..."):
            self.stt._ensure_loaded()
        
        with self.console.status("[bold blue]Loading Kokoro TTS model..."):
            self.tts._ensure_loaded()
        
        self.console.print("[green]Models loaded![/green]")

    def _print_header(self) -> None:
        """Print welcome header."""
        self.console.print()
        self.console.print(
            Panel.fit(
                "[bold blue]Local Voice Chatbot[/bold blue]\n"
                "[dim]Speak to chat, Ctrl+C to exit[/dim]",
                border_style="blue",
            )
        )
        self.console.print()

    def _print_status(self, status: str, style: str = "dim") -> None:
        """Print a status message."""
        self.console.print(f"[{style}]{status}[/{style}]")

    def _on_wake_detected(self) -> None:
        """Called when wake word is detected."""
        model_name = self.wakeword.model_name
        display_name = WakeWordDetector.AVAILABLE_MODELS.get(model_name, model_name)
        self._print_status(f"✨ Wake word detected: {display_name}", "bold green")
    
    def _on_wake_timeout(self) -> None:
        """Called when wake word times out."""
        if self.wakeword.enabled:
            model_name = self.wakeword.model_name
            display_name = WakeWordDetector.AVAILABLE_MODELS.get(model_name, model_name)
            self._print_status(f"💤 Waiting for wake word: {display_name}...", "dim")

    def _on_speech_start(self) -> None:
        """Called when speech is detected."""
        self._print_status("🎤 Listening...", "green")
        # Reset wake word timeout while speaking
        if self.wakeword.enabled:
            self.wakeword.reset_timeout()

    def _on_speech_end(self, audio: np.ndarray) -> None:
        """Called when speech ends with the audio data."""
        if self._processing:
            return

        self._processing = True

        try:
            # Transcribe
            self._print_status("📝 Transcribing...", "yellow")
            result = self.stt.transcribe(audio, settings.audio.sample_rate)

            if not result.text.strip():
                self._print_status("(No speech detected)", "dim")
                return

            self._current_transcription = result.text
            self.console.print(f"\n[bold cyan]You:[/bold cyan] {result.text}")

            # Get LLM response with streaming
            self._print_status("🤔 Thinking...", "yellow")
            full_response = []
            self.sentencizer.reset()

            # Stream tokens and synthesize sentences
            self.console.print("[bold green]Assistant:[/bold green] ", end="")

            for token in self.llm.chat(result.text, stream=True):
                self.console.print(token, end="")
                full_response.append(token)

                # Check for complete sentence
                sentence = self.sentencizer.add_token(token)
                if sentence:
                    # Synthesize and play in background
                    self._speak_sentence(sentence)

            # Flush remaining text
            remaining = self.sentencizer.flush()
            if remaining:
                self._speak_sentence(remaining)

            self.console.print()  # Newline after response
            
            # Return to wake word listening mode if enabled
            if self.wakeword.enabled:
                self.wakeword.set_listening()
                model_name = self.wakeword.model_name
                display_name = WakeWordDetector.AVAILABLE_MODELS.get(model_name, model_name)
                self._print_status(f"💤 Waiting for wake word: {display_name}...", "dim")

        except Exception as e:
            self.console.print(f"\n[red]Error: {e}[/red]")

        finally:
            self._processing = False

    def _speak_sentence(self, sentence: str) -> None:
        """Synthesize and play a sentence."""
        try:
            # Skip text that contains tool call fragments (JSON patterns, tool_call tags)
            # This prevents reading partial tool call syntax like "args": {}
            tool_fragments = ['"tool"', '"args"', '<tool_call>', '</tool_call>', '{"tool']
            if any(fragment in sentence for fragment in tool_fragments):
                if tool_parser.has_tool_call(sentence):
                    # Full tool call - announce it
                    tool_calls = tool_parser.find_tool_calls(sentence)
                    if tool_calls:
                        tc = tool_calls[0]
                        sentence = f"Using tool: {tc.tool}"
                    else:
                        return  # Skip if we can't parse the tool call
                else:
                    # Partial fragment - skip entirely
                    return
            
            if not sentence.strip():
                return
            
            # Echo cancellation: mute wake word detection while speaking
            self.wakeword.set_speaking(True)
            self._is_speaking_tts = True
            
            try:
                audio_segment = self.tts.synthesize(sentence)
                if len(audio_segment.audio) > 0:
                    self.audio_playback.play(audio_segment.audio, blocking=True)
            finally:
                # Resume wake word detection after TTS
                self.wakeword.set_speaking(False)
                self._is_speaking_tts = False
        except Exception as e:
            self.console.print(f"\n[red]TTS Error: {e}[/red]")

    def _audio_callback(self, audio_chunk: np.ndarray) -> None:
        """Process incoming audio chunks."""
        if self._processing:
            return

        result = self.vad.process(audio_chunk)

        if result.state == SpeechState.SPEECH_START:
            self._on_speech_start()
        elif result.state == SpeechState.SPEECH_END:
            # Get accumulated speech audio
            speech_audio = np.concatenate(
                [audio_chunk]
                + [
                    c
                    for c in self.vad._current_speech
                    if isinstance(c, np.ndarray)
                ]
            )
            # Actually use the VAD's internal buffer
            self._on_speech_end(result.audio_chunk)

    def run(self) -> None:
        """Run the voice chat CLI."""
        self._print_header()

        # Register VAD callbacks
        self.vad.on_speech_start(self._on_speech_start)
        self.vad.on_speech_end(self._on_speech_end)

        # Setup signal handler
        def signal_handler(sig, frame):
            self.console.print("\n[yellow]Goodbye![/yellow]")
            self._running = False
            self.audio_capture.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        # Print ready status based on wake word mode
        if self.wakeword.enabled:
            model_name = self.wakeword.model_name
            display_name = WakeWordDetector.AVAILABLE_MODELS.get(model_name, model_name)
            self._print_status(f"Ready! Say '{display_name}' to activate...", "green")
        else:
            self._print_status("Ready! Start speaking...", "green")
        self._running = True

        try:
            # Start audio capture with VAD callback
            self.audio_capture.start(callback=self._process_audio)

            # Main loop - just keep running
            while self._running:
                time.sleep(0.1)

        except KeyboardInterrupt:
            pass
        finally:
            self.audio_capture.stop()
            self.llm.close()

    def _process_audio(self, audio_chunk: np.ndarray) -> None:
        """Process audio through wake word and VAD."""
        if self._processing:
            return

        # If wake word is enabled, check for wake word first
        if self.wakeword.enabled:
            ww_result = self.wakeword.process(audio_chunk)
            
            # Only process through VAD if wake word is active
            if ww_result.state != WakeWordState.ACTIVE:
                return  # Still waiting for wake word
        
        self.vad.process(audio_chunk)


class TextChatCLI:
    """Text-only chat interface (no microphone required)."""

    def __init__(self, use_tts: bool = True, preload_models: bool = True):
        """Initialize text chat CLI.

        Args:
            use_tts: Whether to speak responses
            preload_models: If True, preload TTS model at startup
        """
        self.console = Console()
        self.llm = LLMClient()
        self.use_tts = use_tts

        if use_tts:
            self.tts = TextToSpeech()
            self.audio_playback = AudioPlayback()
            self.sentencizer = StreamingSentencizer()
            
            # Preload TTS model
            if preload_models:
                with self.console.status("[bold blue]Loading Kokoro TTS model..."):
                    self.tts._ensure_loaded()
                self.console.print("[green]TTS model loaded![/green]")
        else:
            self.tts = None
            self.audio_playback = None
            self.sentencizer = None

    def run(self) -> None:
        """Run the text chat CLI."""
        self.console.print()
        self.console.print(
            Panel.fit(
                "[bold blue]Local Voice Chatbot (Text Mode)[/bold blue]\n"
                "[dim]Type your message, 'quit' to exit[/dim]",
                border_style="blue",
            )
        )
        self.console.print()

        try:
            while True:
                # Get user input
                try:
                    user_input = self.console.input("[bold cyan]You:[/bold cyan] ")
                except EOFError:
                    break

                if user_input.lower() in ("quit", "exit", "q"):
                    break

                if not user_input.strip():
                    continue

                # Get response with streaming
                self.console.print("[bold green]Assistant:[/bold green] ", end="")

                if self.use_tts and self.sentencizer:
                    self.sentencizer.reset()

                for token in self.llm.chat(user_input, stream=True):
                    self.console.print(token, end="")

                    # TTS for each sentence
                    if self.use_tts and self.sentencizer:
                        sentence = self.sentencizer.add_token(token)
                        if sentence:
                            self._speak(sentence)

                # Flush remaining
                if self.use_tts and self.sentencizer:
                    remaining = self.sentencizer.flush()
                    if remaining:
                        self._speak(remaining)

                self.console.print()

        except KeyboardInterrupt:
            pass
        finally:
            self.console.print("\n[yellow]Goodbye![/yellow]")
            self.llm.close()

    def _speak(self, text: str) -> None:
        """Speak text using TTS."""
        if self.tts and self.audio_playback:
            try:
                segment = self.tts.synthesize(text)
                if len(segment.audio) > 0:
                    self.audio_playback.play(segment.audio, blocking=True)
            except Exception as e:
                self.console.print(f"\n[dim red]TTS Error: {e}[/dim red]")


def run_cli(text_mode: bool = False, no_tts: bool = False) -> None:
    """Run the CLI interface.

    Args:
        text_mode: If True, use text input instead of voice
        no_tts: If True, disable TTS output
    """
    if text_mode:
        cli = TextChatCLI(use_tts=not no_tts)
    else:
        cli = VoiceChatCLI()

    cli.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Voice Chatbot CLI")
    parser.add_argument(
        "--text", "-t", action="store_true", help="Text input mode (no microphone)"
    )
    parser.add_argument(
        "--no-tts", action="store_true", help="Disable text-to-speech output"
    )

    args = parser.parse_args()
    run_cli(text_mode=args.text, no_tts=args.no_tts)
