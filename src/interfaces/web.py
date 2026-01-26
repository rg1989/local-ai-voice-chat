"""FastAPI web interface with WebSocket audio streaming."""

import asyncio
import base64
import json
import re
import time
from pathlib import Path
from typing import Optional

import numpy as np


def is_speakable(text: str) -> bool:
    """Check if text is primarily Latin characters (speakable by TTS).
    
    Kokoro TTS doesn't support non-Latin scripts well - it reads Hebrew, Arabic,
    Chinese etc. characters as their Unicode names (e.g., "Hebrew Shin" instead of "ש").
    
    This function detects if text is speakable by checking if it's predominantly Latin.
    
    Args:
        text: The text to check
        
    Returns:
        True if the text is primarily Latin and can be spoken by TTS
    """
    # Remove common punctuation, spaces, and numbers
    clean = re.sub(r'[\s\d!"#$%&\'()*+,\-./:;<=>?@\[\\\]^_`{|}~]', '', text)
    if not clean:
        return False  # Only punctuation/whitespace, skip TTS
    
    # Count Latin characters (Basic Latin + Latin Extended-A/B + Latin Extended Additional)
    # Covers: a-z, A-Z, and accented characters like é, ñ, ü, etc.
    latin_count = sum(1 for c in clean if (
        '\u0000' <= c <= '\u024F' or  # Basic Latin through Latin Extended-B
        '\u1E00' <= c <= '\u1EFF'      # Latin Extended Additional
    ))
    
    # If more than 50% is Latin, it's speakable
    return latin_count / len(clean) > 0.5
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles

from ..config import settings
from ..pipeline.llm import LLMClient
from ..pipeline.tools import tool_registry
from ..pipeline.tool_parser import tool_parser
from ..storage.conversations import ConversationStorage, InteractionLog
from ..pipeline.sentencizer import StreamingSentencizer
from ..pipeline.stt import SpeechToText
from ..pipeline.tts import TextToSpeech
from ..pipeline.vad import SpeechState, VoiceActivityDetector
from ..pipeline.wakeword import WakeWordDetector, WakeWordState

# Create FastAPI app
app = FastAPI(
    title="Local Voice Chatbot",
    description="A fully local voice assistant",
    version="0.1.0",
)


@app.on_event("startup")
async def startup_event():
    """Preload and warm up models on server startup."""
    print("\n" + "=" * 60)
    print("  Model Warmup - Preparing for fast first response")
    print("=" * 60)
    
    total_start = time.time()
    
    # Run STT and TTS warmups in thread pool (synchronous operations)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, VoiceChatSession.preload_models)
    
    # Warm up Ollama LLM (async operation)
    await VoiceChatSession.warmup_llm()
    
    total_time = time.time() - total_start
    print("=" * 60)
    print(f"  All models warmed up! Total time: {total_time:.1f}s")
    print("=" * 60 + "\n")


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_json(self, websocket: WebSocket, data: dict) -> bool:
        """Send JSON data to websocket. Returns False if connection is closed."""
        try:
            await websocket.send_json(data)
            return True
        except RuntimeError as e:
            if "close" in str(e).lower() or "disconnect" in str(e).lower():
                return False
            raise

    async def broadcast_json(self, data: dict) -> None:
        for connection in self.active_connections:
            await connection.send_json(data)


manager = ConnectionManager()

# Global conversation storage
conversation_storage = ConversationStorage()


class VoiceChatSession:
    """Handles a single voice chat session."""

    # Shared preloaded models (loaded once per process)
    _shared_stt: Optional[SpeechToText] = None
    _shared_tts: Optional[TextToSpeech] = None

    @classmethod
    def preload_models(cls) -> None:
        """Preload and warm up STT and TTS models for faster first response.
        
        This runs actual inference to ensure models are fully loaded and
        compiled (especially important for MLX which compiles on first use).
        """
        import time as _time
        
        # Warm up STT (MLX Whisper)
        if cls._shared_stt is None:
            print("  [1/3] Warming up Whisper STT...", end=" ", flush=True)
            start = _time.time()
            cls._shared_stt = SpeechToText()
            cls._shared_stt._ensure_loaded()
            
            # Run actual inference with dummy audio to compile MLX graphs
            # Generate 0.5s of silence at 16kHz
            dummy_audio = np.zeros(8000, dtype=np.float32)
            try:
                cls._shared_stt.transcribe(dummy_audio, sample_rate=16000)
            except Exception as e:
                print(f"(warmup transcription failed: {e})", end=" ")
            
            elapsed = _time.time() - start
            print(f"done ({elapsed:.1f}s)")
        
        # Warm up TTS (Kokoro)
        if cls._shared_tts is None:
            print("  [2/3] Warming up Kokoro TTS...", end=" ", flush=True)
            start = _time.time()
            
            # Suppress PyTorch warnings during Kokoro initialization
            # (LSTM dropout warning, weight_norm deprecation warning)
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning, module="torch")
                warnings.filterwarnings("ignore", category=FutureWarning, module="torch")
                
                cls._shared_tts = TextToSpeech()
                cls._shared_tts._ensure_loaded()
                
                # Run actual inference to warm up the pipeline
                try:
                    cls._shared_tts.synthesize("Hello")
                except Exception as e:
                    print(f"(warmup synthesis failed: {e})", end=" ")
            
            elapsed = _time.time() - start
            print(f"done ({elapsed:.1f}s)")

    @classmethod
    async def warmup_llm(cls) -> None:
        """Warm up Ollama LLM by sending a minimal request.
        
        This ensures the model is loaded into GPU VRAM before the first
        real user query, eliminating the slow first response.
        """
        import time as _time
        
        print("  [3/3] Warming up Ollama LLM...", end=" ", flush=True)
        start = _time.time()
        
        llm = LLMClient()
        try:
            # Send a minimal generate request to load model into VRAM
            response = await llm._async_client.post(
                f"{llm.base_url}/api/generate",
                json={
                    "model": llm.model_name,
                    "prompt": "Hi",
                    "stream": False,
                    "options": {"num_predict": 1}  # Generate just 1 token
                },
                timeout=120.0  # Model loading can take time
            )
            response.raise_for_status()
            elapsed = _time.time() - start
            print(f"done ({elapsed:.1f}s)")
        except Exception as e:
            elapsed = _time.time() - start
            print(f"failed ({elapsed:.1f}s) - {e}")
            print("    Note: First query may be slow if Ollama model isn't loaded")
        finally:
            await llm.aclose()

    def __init__(self, websocket: WebSocket, conversation_id: Optional[str] = None):
        self.websocket = websocket
        self.vad = VoiceActivityDetector()
        self.wakeword = WakeWordDetector()
        
        # Use shared preloaded models if available
        if VoiceChatSession._shared_stt is not None:
            self.stt = VoiceChatSession._shared_stt
        else:
            self.stt = SpeechToText()
        
        if VoiceChatSession._shared_tts is not None:
            self.tts = VoiceChatSession._shared_tts
        else:
            self.tts = TextToSpeech()
            
        self.llm = LLMClient()
        self.sentencizer = StreamingSentencizer()

        self._audio_buffer: list[np.ndarray] = []
        self._is_speaking = False
        self._cancel_requested = False
        self._processing_task: Optional[asyncio.Task] = None
        
        # TTS toggle (default enabled)
        self._tts_enabled = True
        
        # Conversation persistence
        self.conversation_id = conversation_id
        self._load_conversation_history()
        
        # Register wake word callbacks
        self.wakeword.on_wake_detected(self._on_wake_detected)
        self.wakeword.on_timeout(self._on_wake_timeout)
    
    def _on_wake_detected(self) -> None:
        """Called when wake word is detected."""
        # We'll send the status update asynchronously
        asyncio.create_task(self._send_wake_status("active"))
    
    def _on_wake_timeout(self) -> None:
        """Called when wake word times out."""
        asyncio.create_task(self._send_wake_status("listening"))
    
    async def _send_wake_status(self, state: str) -> None:
        """Send wake word status to client."""
        model_name = self.wakeword.model_name
        display_name = WakeWordDetector.AVAILABLE_MODELS.get(model_name, model_name)
        print(f"[WAKEWORD] Sending wake_status: state={state}, model={model_name}")
        try:
            success = await manager.send_json(
                self.websocket,
                {
                    "type": "wake_status",
                    "state": state,
                    "model": model_name,
                    "displayName": display_name,
                }
            )
            if success:
                print(f"[WAKEWORD] Successfully sent wake_status: {state}")
            else:
                print(f"[WAKEWORD] WARNING: Failed to send wake_status (connection closed)")
        except Exception as e:
            print(f"[WAKEWORD] ERROR sending wake_status: {e}")

    def _load_conversation_history(self) -> None:
        """Load conversation history from storage into LLM context."""
        if self.conversation_id:
            conversation = conversation_storage.load(self.conversation_id)
            if conversation:
                # Load existing messages into LLM history
                for msg in conversation.messages:
                    if msg.role == "user":
                        self.llm.history.add_user_message(msg.content)
                    elif msg.role == "assistant":
                        self.llm.history.add_assistant_message(msg.content)
                
                # Load conversation summary if present (compressed history)
                if conversation.summary:
                    self.llm.history.summary = conversation.summary
                    print(f"[CONTEXT] Loaded summary ({len(conversation.summary)} chars) for conversation {self.conversation_id[:8]}...")
                
                # Load custom rules for this conversation
                self.llm.set_custom_rules(conversation.custom_rules)
                
                # Update token estimate based on loaded history
                self.llm.update_token_estimate_from_history()
        else:
            # New conversation - reset token count, custom rules, and summary
            self.llm._last_prompt_tokens = 0
            self.llm.set_custom_rules("")
            self.llm.history.summary = ""

    def set_conversation(self, conversation_id: str) -> None:
        """Switch to a different conversation."""
        self.conversation_id = conversation_id
        self.llm.clear_history()  # This also clears the summary
        self.llm.set_custom_rules("")  # Reset before loading
        self._load_conversation_history()

    def set_custom_rules(self, rules: str) -> None:
        """Set custom rules for the current conversation."""
        self.llm.set_custom_rules(rules)
        # Also save to storage if conversation exists
        if self.conversation_id:
            conversation_storage.update_custom_rules(self.conversation_id, rules)

    def _save_message(self, role: str, content: str) -> None:
        """Save a message to the current conversation."""
        if self.conversation_id and content.strip():
            conversation_storage.add_message(self.conversation_id, role, content)

    def _save_summary_to_storage(self) -> None:
        """Save the current LLM history summary to conversation storage."""
        if self.conversation_id and self.llm.history.summary:
            conversation_storage.update_summary(self.conversation_id, self.llm.history.summary)
            print(f"[CONTEXT] Saved summary to storage for conversation {self.conversation_id[:8]}...")

    def _save_interaction_log(self, log: InteractionLog) -> None:
        """Save an interaction log to the current conversation."""
        if self.conversation_id:
            conversation_storage.add_interaction_log(self.conversation_id, log)
            print(f"[LOG] Saved interaction log: {log.id[:8]}... (input: '{log.llm_user_message[:50]}...')")

    def _format_tool_call_message(self, content: str) -> str:
        """Format a tool call message for clean display.
        
        If the content contains a tool call, returns a clean "Using tool: name(args)" format.
        Otherwise returns the original content.
        """
        if tool_parser.has_tool_call(content):
            tool_calls = tool_parser.find_tool_calls(content)
            if tool_calls:
                tc = tool_calls[0]
                if tc.args:
                    args_str = ", ".join(f"{k}: {v}" for k, v in tc.args.items())
                    return f"Using tool: {tc.tool}({args_str})"
                else:
                    return f"Using tool: {tc.tool}()"
        return content

    async def send_status(self, status: str, data: Optional[dict] = None, include_memory: bool = False) -> None:
        """Send status update to client.
        
        Args:
            status: Status string (e.g., "listening", "thinking")
            data: Optional additional data
            include_memory: If True, include memory usage stats
        """
        message = {"type": "status", "status": status}
        if data:
            message["data"] = data
        if include_memory:
            memory = self.llm.get_memory_usage()
            print(f"[DEBUG] Memory usage: {memory}")
            message["memory"] = memory
        await manager.send_json(self.websocket, message)

    async def send_transcription(self, text: str) -> None:
        """Send transcription to client."""
        await manager.send_json(
            self.websocket, {"type": "transcription", "text": text}
        )

    async def send_response_token(self, token: str) -> None:
        """Send LLM response token to client."""
        await manager.send_json(
            self.websocket, {"type": "response_token", "token": token}
        )

    async def send_response_end(self) -> None:
        """Signal end of response."""
        await manager.send_json(self.websocket, {"type": "response_end"})

    async def send_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        """Send audio data to client."""
        # Convert to base64 for transmission
        audio_bytes = (audio * 32767).astype(np.int16).tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        await manager.send_json(
            self.websocket,
            {
                "type": "audio",
                "audio": audio_b64,
                "sample_rate": sample_rate,
            },
        )

    async def process_audio_chunk(self, audio_data: bytes) -> None:
        """Process incoming audio chunk."""
        # Skip if a processing task is running (transcription/LLM)
        if self._processing_task and not self._processing_task.done():
            return
            
        # Convert bytes to numpy array (assuming 16-bit PCM)
        audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # If wake word is enabled, check for wake word first
        if self.wakeword.enabled:
            # Debug: log that we're processing audio for wake word (only occasionally)
            if not hasattr(self, '_ww_process_count'):
                self._ww_process_count = 0
            self._ww_process_count += 1
            if self._ww_process_count % 100 == 1:
                print(f"[WAKEWORD] Processing audio chunk #{self._ww_process_count}, audio shape: {audio.shape}, enabled: {self.wakeword.enabled}, ready: {self.wakeword.is_ready}")
            
            ww_result = self.wakeword.process(audio)
            
            # The wakeword callback (_on_wake_detected) handles sending the status
            # and the _detection_lock_until prevents multiple detections
            
            # Only process through VAD if wake word is active (or just detected)
            if ww_result.state != WakeWordState.ACTIVE:
                return  # Still waiting for wake word
        
        # Process through VAD
        result = self.vad.process(audio)

        if result.state == SpeechState.SPEECH_START:
            self._is_speaking = True
            await self.send_status("listening")
            # Reset wake word timeout while speaking
            if self.wakeword.enabled:
                self.wakeword.reset_timeout()

        elif result.state == SpeechState.SPEAKING:
            # Continuously reset timeout while user is speaking
            # This prevents timeout during long sentences
            if self.wakeword.enabled:
                self.wakeword.reset_timeout()

        elif result.state == SpeechState.SPEECH_END:
            self._is_speaking = False
            # Run processing in background task so we can receive stop messages
            self._processing_task = asyncio.create_task(self.process_speech_end())

    async def process_speech_end(self) -> None:
        """Process end of speech segment."""
        # Prevent wake word timeout during processing
        if self.wakeword.enabled:
            self.wakeword.set_processing(True)
        
        # Create interaction log
        interaction_start = time.time()
        log = InteractionLog.create(input_type="voice")
        
        try:
            # Get accumulated speech from VAD
            speech_audio = self.vad.get_speech_audio()
            
            # Reset VAD for next utterance
            self.vad.reset()
            
            if speech_audio is None or len(speech_audio) < settings.audio.sample_rate * 0.5:
                print(f"[DEBUG] Audio too short or empty, returning to listening")
                await self.send_status("listening")
                return

            # Log audio details
            log.audio_samples = len(speech_audio)
            log.audio_duration_ms = int((len(speech_audio) / settings.audio.sample_rate) * 1000)
            
            print(f"[DEBUG] Starting transcription of {len(speech_audio)} samples...")
            
            # Transcribe
            await self.send_status("transcribing")
            transcription_start = time.time()
            result = await self.stt.transcribe_async(speech_audio, settings.audio.sample_rate)
            log.transcription_duration_ms = int((time.time() - transcription_start) * 1000)
            log.transcription_text = result.text
            
            print(f"[DEBUG] Transcription complete: '{result.text}'")

            # Check for cancellation after transcription
            if self._cancel_requested:
                self._cancel_requested = False
                log.add_error("Cancelled after transcription")
                print("[DEBUG] Cancelled after transcription")
                await self.send_status("listening")
                return

            if not result.text.strip():
                log.add_error("Empty transcription")
                print("[DEBUG] Empty transcription, returning to listening")
                await self.send_status("listening")
                return

            await self.send_transcription(result.text)
            transcribed_text = result.text  # Store for use in LLM call
            
            # Save user message to conversation
            self._save_message("user", transcribed_text)

            # Check for cancellation before LLM
            if self._cancel_requested:
                self._cancel_requested = False
                log.add_error("Cancelled before LLM")
                print("[DEBUG] Cancelled before LLM")
                await self.send_status("listening")
                return

            # Log LLM details BEFORE the call
            log.llm_model = self.llm.model_name
            log.llm_system_prompt = self.llm.system_prompt
            log.llm_history = [{"role": m.role, "content": m.content} for m in self.llm.history.messages]
            log.llm_user_message = transcribed_text
            log.tts_enabled = self._tts_enabled
            log.tts_voice = self.tts.voice
            
            # Check if context compression is needed before LLM call
            compressed = await self.llm.compress_if_needed(threshold_percent=70)
            if compressed:
                # Save the updated summary to storage
                self._save_summary_to_storage()
            
            # Get LLM response
            print(f"[DEBUG] Starting LLM call with model: {self.llm.model_name}")
            print(f"[DEBUG] User message being sent to LLM: '{transcribed_text}'")
            print(f"[DEBUG] History messages count: {len(self.llm.history.messages)}")
            if self.llm.history.messages:
                for i, msg in enumerate(self.llm.history.messages[-4:]):  # Show last 4 messages
                    print(f"[DEBUG]   History[{i}] {msg.role}: {msg.content[:100]}...")
            await self.send_status("thinking")

            self.sentencizer.reset()
            full_response = []
            cancelled = False
            llm_start = time.time()

            # Stream response
            async for token in await self.llm.chat_async(transcribed_text, stream=True):
                # Check for cancellation
                if self._cancel_requested:
                    self._cancel_requested = False
                    cancelled = True
                    break
                    
                await self.send_response_token(token)
                full_response.append(token)

                # Check for complete sentence
                sentence = self.sentencizer.add_token(token)
                if sentence:
                    if self._cancel_requested:
                        self._cancel_requested = False
                        cancelled = True
                        break
                    await self.synthesize_and_send(sentence)
            
            log.llm_response_duration_ms = int((time.time() - llm_start) * 1000)
            log.llm_response_text = "".join(full_response)
            log.llm_prompt_tokens = self.llm._last_prompt_tokens

            if cancelled:
                log.add_error("Cancelled during LLM streaming")
                print("[DEBUG] Cancelled during LLM streaming")
                await self.send_status("stopped")
                await self.send_status("listening")
                # Save the partial log
                log.total_duration_ms = int((time.time() - interaction_start) * 1000)
                self._save_interaction_log(log)
                return

            # Flush remaining
            remaining = self.sentencizer.flush()
            if remaining and not self._cancel_requested:
                await self.synthesize_and_send(remaining)

            # Check for and execute tool calls
            full_response_text = "".join(full_response)
            tool_results = await self._execute_tools_if_present(full_response_text, log)
            
            if tool_results and not self._cancel_requested:
                # End the first message (which contains the tool call)
                await self.send_response_end()
                
                # Save the tool call message with clean formatting
                clean_message = self._format_tool_call_message(full_response_text)
                self._save_message("assistant", clean_message)
                
                # Get follow-up response with tool results (as a new message)
                follow_up = await self._get_tool_followup_response(tool_results)
                if follow_up:
                    # End the follow-up message
                    await self.send_response_end()
                    # Save the follow-up message
                    self._save_message("assistant", follow_up)
            else:
                await self.send_response_end()
                # Save assistant message to conversation
                self._save_message("assistant", full_response_text)
            
            print(f"[DEBUG] Response complete: {len(full_response)} tokens")
            
            # Finalize and save log
            log.total_duration_ms = int((time.time() - interaction_start) * 1000)
            self._save_interaction_log(log)
            
            # If wake word is enabled, return to listening for wake word FIRST
            # (before sending status, to avoid race condition with overlay)
            if self.wakeword.enabled:
                print(f"[DEBUG] Wake word enabled, resetting to listening state")
                self.wakeword.set_processing(False)  # Allow timeout again
                self.wakeword.set_listening()
                await self._send_wake_status("listening")
                print(f"[DEBUG] Wake status 'listening' sent")
            
            # Send "listening" with memory usage to resume audio streaming
            await self.send_status("listening", include_memory=True)
            print(f"[DEBUG] Status 'listening' sent")
            
        except asyncio.CancelledError:
            log.add_error("Task was cancelled")
            log.total_duration_ms = int((time.time() - interaction_start) * 1000)
            self._save_interaction_log(log)
            if self.wakeword.enabled:
                self.wakeword.set_processing(False)
            print("[DEBUG] Task was cancelled")
            return
        except Exception as e:
            log.add_error(f"Processing error: {str(e)}")
            log.total_duration_ms = int((time.time() - interaction_start) * 1000)
            if self.wakeword.enabled:
                self.wakeword.set_processing(False)
            self._save_interaction_log(log)
            print(f"[ERROR] Processing error: {e}")
            import traceback
            traceback.print_exc()
            await manager.send_json(
                self.websocket,
                {"type": "error", "message": f"Error: {str(e)}"}
            )
            await self.send_status("listening")

    async def synthesize_and_send(self, text: str) -> None:
        """Synthesize text and send audio to client."""
        if not self._tts_enabled:
            print(f"[DEBUG] TTS disabled, skipping synthesis for: {text[:50]}...")
            return  # Skip TTS when disabled
        
        # Skip text that contains tool call fragments (JSON patterns, tool_call tags)
        # This prevents reading partial tool call syntax like "args": {}
        tool_fragments = ['"tool"', '"args"', '<tool_call>', '</tool_call>', '{"tool']
        if any(fragment in text for fragment in tool_fragments):
            if tool_parser.has_tool_call(text):
                # Full tool call - announce it
                tool_calls = tool_parser.find_tool_calls(text)
                if tool_calls:
                    tc = tool_calls[0]
                    text = f"Using tool: {tc.tool}"
                else:
                    return  # Skip if we can't parse the tool call
            else:
                # Partial fragment - skip entirely
                return
        
        if not text.strip():
            return
        
        # Skip non-Latin text (Hebrew, Arabic, Chinese, etc.) - TTS can't pronounce it
        # Kokoro TTS reads these as Unicode character names like "Hebrew Shin" instead of the word
        if not is_speakable(text):
            print(f"[DEBUG] Non-Latin text detected, skipping TTS: {text[:50]}...")
            return
        
        await self.send_status("speaking")
        
        # Echo cancellation: mute wake word detection while speaking
        self.wakeword.set_speaking(True)
        
        try:
            segment = await self.tts.synthesize_async(text)
            if len(segment.audio) > 0:
                await self.send_audio(segment.audio, segment.sample_rate)
                
                # Wait for audio to finish playing on frontend before resuming wake word
                # Add buffer time for audio transmission and playback latency
                playback_delay = segment.duration_seconds + 0.5  # audio duration + 500ms buffer
                await asyncio.sleep(playback_delay)
        finally:
            # Resume wake word detection after TTS playback completes
            self.wakeword.set_speaking(False)

    async def process_text_message(self, text: str) -> None:
        """Process a text message (for text-only mode)."""
        # Prevent wake word timeout during processing
        if self.wakeword.enabled:
            self.wakeword.set_processing(True)
        
        # Create interaction log
        interaction_start = time.time()
        log = InteractionLog.create(input_type="text")
        log.llm_user_message = text
        
        try:
            await self.send_transcription(text)
            
            # Save user message to conversation
            self._save_message("user", text)
            
            # Check if context compression is needed before LLM call
            compressed = await self.llm.compress_if_needed(threshold_percent=70)
            if compressed:
                # Save the updated summary to storage
                self._save_summary_to_storage()
            
            # Log LLM details BEFORE the call
            log.llm_model = self.llm.model_name
            log.llm_system_prompt = self.llm.system_prompt
            log.llm_history = [{"role": m.role, "content": m.content} for m in self.llm.history.messages]
            log.tts_enabled = self._tts_enabled
            log.tts_voice = self.tts.voice
            
            await self.send_status("thinking")

            self.sentencizer.reset()
            cancelled = False
            full_response = []
            llm_start = time.time()

            # Stream response
            async for token in await self.llm.chat_async(text, stream=True):
                # Check for cancellation
                if self._cancel_requested:
                    self._cancel_requested = False
                    cancelled = True
                    break
                    
                await self.send_response_token(token)
                full_response.append(token)

                sentence = self.sentencizer.add_token(token)
                if sentence:
                    if self._cancel_requested:
                        self._cancel_requested = False
                        cancelled = True
                        break
                    await self.synthesize_and_send(sentence)

            log.llm_response_duration_ms = int((time.time() - llm_start) * 1000)
            log.llm_response_text = "".join(full_response)
            log.llm_prompt_tokens = self.llm._last_prompt_tokens

            if cancelled:
                log.add_error("Cancelled during LLM streaming")
                log.total_duration_ms = int((time.time() - interaction_start) * 1000)
                self._save_interaction_log(log)
                return

            remaining = self.sentencizer.flush()
            if remaining and not self._cancel_requested:
                await self.synthesize_and_send(remaining)

            # Check for and execute tool calls
            full_response_text = "".join(full_response)
            tool_results = await self._execute_tools_if_present(full_response_text, log)
            
            if tool_results and not self._cancel_requested:
                # End the first message (which contains the tool call)
                await self.send_response_end()
                
                # Save the tool call message with clean formatting
                clean_message = self._format_tool_call_message(full_response_text)
                self._save_message("assistant", clean_message)
                
                # Get follow-up response with tool results (as a new message)
                follow_up = await self._get_tool_followup_response(tool_results)
                if follow_up:
                    # End the follow-up message
                    await self.send_response_end()
                    # Save the follow-up message
                    self._save_message("assistant", follow_up)
            else:
                await self.send_response_end()
                # Save assistant message to conversation
                self._save_message("assistant", full_response_text)
            
            # Finalize and save log
            log.total_duration_ms = int((time.time() - interaction_start) * 1000)
            self._save_interaction_log(log)
            
            # If wake word is enabled, return to listening for wake word FIRST
            # (before sending status, to avoid race condition with overlay)
            if self.wakeword.enabled:
                self.wakeword.set_processing(False)  # Allow timeout again
                self.wakeword.set_listening()
                await self._send_wake_status("listening")
            
            # Send "listening" with memory usage to resume audio streaming
            await self.send_status("listening", include_memory=True)

        except asyncio.CancelledError:
            log.add_error("Task was cancelled")
            log.total_duration_ms = int((time.time() - interaction_start) * 1000)
            self._save_interaction_log(log)
            if self.wakeword.enabled:
                self.wakeword.set_processing(False)
            return
        except Exception as e:
            log.add_error(f"LLM error: {str(e)}")
            log.total_duration_ms = int((time.time() - interaction_start) * 1000)
            self._save_interaction_log(log)
            if self.wakeword.enabled:
                self.wakeword.set_processing(False)
            print(f"LLM error: {e}")
            await manager.send_json(
                self.websocket,
                {"type": "error", "message": f"LLM error: {str(e)}"}
            )
            await self.send_status("listening", include_memory=True)
    
    async def _execute_tools_if_present(self, response_text: str, log: Optional[InteractionLog] = None) -> str | None:
        """Check for and execute tool calls in the response.
        
        Args:
            response_text: The LLM response text to check for tool calls
            log: Optional interaction log to record tool calls
        
        Returns:
            Tool results string if tools were executed, None otherwise
        """
        if not self.llm.tools_enabled:
            return None
        
        tool_calls = tool_parser.find_tool_calls(response_text)
        if not tool_calls:
            return None
        
        results = []
        for call in tool_calls:
            print(f"[TOOL] Executing: {call.tool} with args: {call.args}")
            await self.send_status("executing_tool", {"tool": call.tool})
            
            tool_start = time.time()
            result = await tool_registry.execute(call.tool, call.args)
            tool_duration_ms = int((time.time() - tool_start) * 1000)
            
            if result.success:
                results.append(f"[Tool: {call.tool}]\n{result.output}")
                print(f"[TOOL] Success: {result.output[:200]}...")
                if log:
                    log.add_tool_call(call.tool, call.args, result.output, tool_duration_ms, success=True)
            else:
                results.append(f"[Tool: {call.tool}] Error: {result.error}")
                print(f"[TOOL] Error: {result.error}")
                if log:
                    log.add_tool_call(call.tool, call.args, result.error or "", tool_duration_ms, success=False)
        
        return "\n\n".join(results)
    
    async def _get_tool_followup_response(self, tool_results: str) -> str | None:
        """Get a follow-up response from the LLM after tool execution.
        
        Args:
            tool_results: The results from tool execution
            
        Returns:
            The follow-up response text
        """
        await self.send_status("thinking")
        
        # Create a message with tool results - be very explicit about using them
        tool_message = f"TOOL RESULT (this is the REAL, ACCURATE data - you MUST use it exactly):\n\n{tool_results}\n\nRespond to the user using ONLY the information above. Do NOT use your training data. Do NOT guess. Just state the facts from the tool result. Do not output another tool call."
        
        self.sentencizer.reset()
        full_response = []
        
        # Stream the follow-up response
        async for token in await self.llm.chat_async(tool_message, stream=True):
            if self._cancel_requested:
                self._cancel_requested = False
                return None
                
            await self.send_response_token(token)
            full_response.append(token)
            
            sentence = self.sentencizer.add_token(token)
            if sentence:
                if self._cancel_requested:
                    self._cancel_requested = False
                    return None
                await self.synthesize_and_send(sentence)
        
        remaining = self.sentencizer.flush()
        if remaining and not self._cancel_requested:
            await self.synthesize_and_send(remaining)
        
        return "".join(full_response)

    def request_cancel(self) -> None:
        """Request cancellation of current processing."""
        self._cancel_requested = True
        # Cancel the processing task if running
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()

    async def request_cancel_async(self) -> None:
        """Request cancellation and send status update."""
        self.request_cancel()
        await self.send_status("stopped")
        await self.send_status("listening")
        # Reset VAD state
        self.vad.reset()

    def cleanup(self) -> None:
        """Cleanup resources."""
        self.llm.close()


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for voice/text chat."""
    await manager.connect(websocket)
    session = VoiceChatSession(websocket)

    try:
        # Fetch context window from Ollama for memory tracking
        await session.llm.fetch_context_window()
        await session.send_status("ready", include_memory=True)
        
        # Send initial wake word settings
        ww_settings = session.wakeword.get_settings()
        ww_settings["availableModels"] = WakeWordDetector.get_available_models()
        await manager.send_json(websocket, {"type": "wakeword_settings", **ww_settings})
        
        # Send initial wake status if enabled
        if session.wakeword.enabled:
            await session._send_wake_status(session.wakeword.state.value)

        while True:
            # Receive message
            message = await websocket.receive()

            # Check for disconnect
            if message.get("type") == "websocket.disconnect":
                break

            if "bytes" in message:
                # Audio data
                await session.process_audio_chunk(message["bytes"])

            elif "text" in message:
                # JSON message
                data = json.loads(message["text"])
                msg_type = data.get("type")

                if msg_type == "text":
                    # Text message - run in background task so we can receive stop
                    if session._processing_task and not session._processing_task.done():
                        continue  # Skip if already processing
                    session._processing_task = asyncio.create_task(
                        session.process_text_message(data.get("text", ""))
                    )

                elif msg_type == "clear_history":
                    session.llm.clear_history()
                    # Also clear messages in storage if conversation exists
                    if session.conversation_id:
                        conversation_storage.clear_messages(session.conversation_id)
                    await session.send_status("history_cleared")

                elif msg_type == "set_voice":
                    voice = data.get("voice")
                    if voice:
                        session.tts.set_voice(voice)
                        await session.send_status("voice_changed", {"voice": voice})

                elif msg_type == "stop":
                    await session.request_cancel_async()

                elif msg_type == "set_model":
                    model = data.get("model")
                    if model:
                        session.llm.model_name = model
                        # Fetch new model's context window
                        await session.llm.fetch_context_window()
                        await session.send_status("model_changed", {"model": model}, include_memory=True)

                elif msg_type == "set_conversation":
                    conversation_id = data.get("conversation_id")
                    if conversation_id:
                        session.set_conversation(conversation_id)
                        await session.send_status("conversation_changed", {"conversation_id": conversation_id}, include_memory=True)

                elif msg_type == "set_tts_enabled":
                    enabled = data.get("enabled", True)
                    print(f"[DEBUG] TTS enabled set to: {enabled}")
                    session._tts_enabled = enabled
                    await session.send_status("tts_enabled_changed", {"enabled": enabled})

                elif msg_type == "set_custom_rules":
                    rules = data.get("rules", "")
                    print(f"[DEBUG] Custom rules set: {rules[:50]}...")
                    session.set_custom_rules(rules)
                    await session.send_status("custom_rules_changed", {"rules": rules})

                elif msg_type == "get_tools":
                    # Return list of available tools with their enabled state
                    tools_list = [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "enabled": tool.enabled,
                            "requires_confirmation": tool.requires_confirmation,
                        }
                        for tool in tool_registry.get_all_tools()
                    ]
                    await manager.send_json(websocket, {"type": "tools_list", "tools": tools_list})

                elif msg_type == "set_tool_enabled":
                    tool_name = data.get("tool")
                    enabled = data.get("enabled", True)
                    if tool_name:
                        tool_registry.set_tool_enabled(tool_name, enabled)
                        print(f"[DEBUG] Tool '{tool_name}' enabled: {enabled}")
                        await session.send_status("tool_enabled_changed", {"tool": tool_name, "enabled": enabled})

                elif msg_type == "set_global_rules":
                    rules = data.get("rules", "")
                    print(f"[DEBUG] Global rules set: {rules[:50] if rules else '(empty)'}...")
                    session.llm.set_global_rules(rules)
                    await session.send_status("global_rules_changed", {"rules": rules})

                elif msg_type == "get_wakeword_settings":
                    # Return current wake word settings
                    ww_settings = session.wakeword.get_settings()
                    ww_settings["availableModels"] = WakeWordDetector.get_available_models()
                    await manager.send_json(websocket, {"type": "wakeword_settings", **ww_settings})

                elif msg_type == "set_wakeword_settings":
                    # Update wake word settings
                    enabled = data.get("enabled")
                    model = data.get("model")
                    threshold = data.get("threshold")
                    timeout = data.get("timeoutSeconds")
                    
                    session.wakeword.update_settings(
                        enabled=enabled,
                        model=model,
                        threshold=threshold,
                        timeout_seconds=timeout,
                    )
                    
                    print(f"[DEBUG] Wake word settings updated: enabled={enabled}, model={model}, threshold={threshold}")
                    
                    # Pre-load the model if enabling wake word
                    if enabled:
                        # Run model loading in background to avoid blocking WebSocket
                        import asyncio
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, session.wakeword.preload_model)
                        print(f"[DEBUG] Wake word model preloaded, ready={session.wakeword.is_ready}")
                    
                    # Send updated settings back (includes ready status)
                    ww_settings = session.wakeword.get_settings()
                    ww_settings["availableModels"] = WakeWordDetector.get_available_models()
                    await manager.send_json(websocket, {"type": "wakeword_settings", **ww_settings})
                    
                    # Also send current wake status
                    if session.wakeword.enabled:
                        await session._send_wake_status(session.wakeword.state.value)

    except WebSocketDisconnect:
        pass
    except RuntimeError as e:
        # Handle "Cannot call receive once disconnect received" error
        if "disconnect" not in str(e).lower():
            raise
    finally:
        manager.disconnect(websocket)
        session.cleanup()


@app.get("/api/voices")
async def get_voices():
    """Get available TTS voices."""
    # Return list of voice IDs for frontend compatibility
    return {"voices": list(TextToSpeech.list_voices().keys())}


@app.get("/api/wakeword/settings")
async def get_wakeword_settings():
    """Get wake word settings."""
    return {
        "enabled": settings.wakeword.enabled,
        "model": settings.wakeword.model,
        "threshold": settings.wakeword.threshold,
        "timeoutSeconds": settings.wakeword.timeout_seconds,
        "availableModels": WakeWordDetector.get_available_models(),
    }


class WakeWordSettingsRequest(BaseModel):
    """Request body for updating wake word settings."""
    enabled: Optional[bool] = None
    model: Optional[str] = None
    threshold: Optional[float] = None
    timeoutSeconds: Optional[int] = None


@app.post("/api/wakeword/settings")
async def update_wakeword_settings(request: WakeWordSettingsRequest):
    """Update wake word settings.
    
    Note: These settings are session-based. For persistent settings,
    use environment variables or .env file.
    """
    # Return the requested settings (actual update happens per-session via WebSocket)
    return {
        "enabled": request.enabled if request.enabled is not None else settings.wakeword.enabled,
        "model": request.model if request.model is not None else settings.wakeword.model,
        "threshold": request.threshold if request.threshold is not None else settings.wakeword.threshold,
        "timeoutSeconds": request.timeoutSeconds if request.timeoutSeconds is not None else settings.wakeword.timeout_seconds,
        "availableModels": WakeWordDetector.get_available_models(),
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    llm = LLMClient()
    ollama_ok = await llm.check_connection()
    await llm.aclose()

    return {
        "status": "ok" if ollama_ok else "degraded",
        "ollama": ollama_ok,
        "model": settings.llm.model_name,
    }


@app.get("/api/models")
async def get_models():
    """Get available Ollama models."""
    llm = LLMClient()
    try:
        response = await llm._async_client.get(f"{llm.base_url}/api/tags")
        response.raise_for_status()
        data = response.json()
        models = [m.get("name") for m in data.get("models", [])]
        return {
            "models": models,
            "current": settings.llm.model_name,
            "available": True,
        }
    except Exception as e:
        return {
            "models": [],
            "current": None,
            "available": False,
            "error": f"Ollama not available: {str(e)}. Run: ollama serve && ollama pull qwen3:8b",
        }
    finally:
        await llm.aclose()


# ===== Conversation CRUD Endpoints =====


class CreateConversationRequest(BaseModel):
    """Request body for creating a conversation."""
    title: str = "New Conversation"


class UpdateConversationRequest(BaseModel):
    """Request body for updating a conversation."""
    title: Optional[str] = None


class UpdateConversationSettingsRequest(BaseModel):
    """Request body for updating conversation settings."""
    custom_rules: Optional[str] = None


class AddMessageRequest(BaseModel):
    """Request body for adding a message."""
    role: str
    content: str


@app.get("/api/conversations")
async def list_conversations():
    """List all conversations (summaries only, sorted by updated_at)."""
    summaries = conversation_storage.list_summaries()
    return {"conversations": summaries}


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a single conversation with all messages."""
    conversation = conversation_storage.load(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"conversation": conversation.to_dict()}


@app.post("/api/conversations")
async def create_conversation(request: CreateConversationRequest = Body(default=CreateConversationRequest())):
    """Create a new conversation."""
    conversation = conversation_storage.create(request.title)
    return {"conversation": conversation.to_dict()}


@app.put("/api/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, request: UpdateConversationRequest):
    """Update a conversation title."""
    conversation = conversation_storage.load(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Update title if provided
    if request.title is not None:
        conversation.title = request.title

    conversation_storage.save(conversation)
    return {"conversation": conversation.to_dict()}


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    success = conversation_storage.delete(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True}


@app.put("/api/conversations/{conversation_id}/settings")
async def update_conversation_settings(
    conversation_id: str, 
    request: UpdateConversationSettingsRequest
):
    """Update conversation settings (custom rules, etc.)."""
    conversation = conversation_storage.load(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Update custom rules if provided
    if request.custom_rules is not None:
        conversation.custom_rules = request.custom_rules

    conversation_storage.save(conversation)
    return {
        "success": True,
        "custom_rules": conversation.custom_rules
    }


@app.get("/api/conversations/{conversation_id}/settings")
async def get_conversation_settings(conversation_id: str):
    """Get conversation settings."""
    conversation = conversation_storage.load(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {
        "custom_rules": conversation.custom_rules
    }


@app.post("/api/conversations/{conversation_id}/messages")
async def add_message(conversation_id: str, request: AddMessageRequest):
    """Add a message to a conversation."""
    message = conversation_storage.add_message(conversation_id, request.role, request.content)
    if message is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": message.to_dict()}


@app.delete("/api/conversations/{conversation_id}/messages")
async def clear_messages(conversation_id: str):
    """Clear all messages from a conversation."""
    success = conversation_storage.clear_messages(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True}


@app.get("/api/conversations/{conversation_id}/logs")
async def get_conversation_logs(conversation_id: str, limit: int = Query(default=50, ge=1, le=200)):
    """Get interaction logs for a conversation (for debugging).
    
    Returns detailed logs of each interaction including:
    - Input (voice/text)
    - Transcription details
    - Full LLM context (system prompt, history, user message)
    - LLM response
    - Tool calls
    - Timing information
    - Errors
    """
    logs = conversation_storage.get_interaction_logs(conversation_id, limit=limit)
    if not logs and conversation_storage.load(conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {
        "conversation_id": conversation_id,
        "log_count": len(logs),
        "logs": [log.to_dict() for log in logs]
    }


# Serve the web UI
WEB_DIR = Path(__file__).parent.parent.parent / "web"


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main page."""
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(
        """
        <html>
        <head><title>Voice Chatbot</title></head>
        <body>
            <h1>Voice Chatbot</h1>
            <p>Web UI not found. Run from project root or check web/index.html exists.</p>
        </body>
        </html>
        """
    )


def run_server(
    host: Optional[str] = None,
    port: Optional[int] = None,
    reload: bool = False,
) -> None:
    """Run the web server.

    Args:
        host: Server host
        port: Server port
        reload: Enable auto-reload for development
    """
    import uvicorn

    uvicorn.run(
        "src.interfaces.web:app",
        host=host or settings.web.host,
        port=port or settings.web.port,
        reload=reload,
    )


if __name__ == "__main__":
    run_server()
