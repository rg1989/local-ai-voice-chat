"""FastAPI web interface with WebSocket audio streaming."""

import asyncio
import base64
import json
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles

from ..config import settings
from ..pipeline.llm import LLMClient
from ..storage.conversations import ConversationStorage
from ..pipeline.sentencizer import StreamingSentencizer
from ..pipeline.stt import SpeechToText
from ..pipeline.tts import TextToSpeech
from ..pipeline.vad import SpeechState, VoiceActivityDetector

# Create FastAPI app
app = FastAPI(
    title="Local Voice Chatbot",
    description="A fully local voice assistant",
    version="0.1.0",
)


@app.on_event("startup")
async def startup_event():
    """Preload models on server startup."""
    print("Server starting - preloading models...")
    # Run in thread pool to not block startup
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, VoiceChatSession.preload_models)


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
        """Preload STT and TTS models for faster first response."""
        if cls._shared_stt is None:
            print("Preloading Whisper STT model...")
            cls._shared_stt = SpeechToText()
            cls._shared_stt._ensure_loaded()
        
        if cls._shared_tts is None:
            print("Preloading Kokoro TTS model...")
            cls._shared_tts = TextToSpeech()
            cls._shared_tts._ensure_loaded()
        
        print("Models preloaded!")

    def __init__(self, websocket: WebSocket, conversation_id: Optional[str] = None):
        self.websocket = websocket
        self.vad = VoiceActivityDetector()
        
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
                
                # Update token estimate based on loaded history
                self.llm.update_token_estimate_from_history()
        else:
            # New conversation - reset token count
            self.llm._last_prompt_tokens = 0

    def set_conversation(self, conversation_id: str) -> None:
        """Switch to a different conversation."""
        self.conversation_id = conversation_id
        self.llm.clear_history()
        self._load_conversation_history()

    def _save_message(self, role: str, content: str) -> None:
        """Save a message to the current conversation."""
        if self.conversation_id and content.strip():
            conversation_storage.add_message(self.conversation_id, role, content)

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
        # Skip if already processing
        if self._processing_task and not self._processing_task.done():
            return
            
        # Convert bytes to numpy array (assuming 16-bit PCM)
        audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Process through VAD
        result = self.vad.process(audio)

        if result.state == SpeechState.SPEECH_START:
            self._is_speaking = True
            await self.send_status("listening")

        elif result.state == SpeechState.SPEECH_END:
            self._is_speaking = False
            # Run processing in background task so we can receive stop messages
            self._processing_task = asyncio.create_task(self.process_speech_end())

    async def process_speech_end(self) -> None:
        """Process end of speech segment."""
        try:
            # Get accumulated speech from VAD
            speech_audio = self.vad.get_speech_audio()
            
            # Reset VAD for next utterance
            self.vad.reset()
            
            if speech_audio is None or len(speech_audio) < settings.audio.sample_rate * 0.5:
                print(f"[DEBUG] Audio too short or empty, returning to listening")
                await self.send_status("listening")
                return

            print(f"[DEBUG] Starting transcription of {len(speech_audio)} samples...")
            
            # Transcribe
            await self.send_status("transcribing")
            result = await self.stt.transcribe_async(speech_audio, settings.audio.sample_rate)
            
            print(f"[DEBUG] Transcription complete: '{result.text}'")

            # Check for cancellation after transcription
            if self._cancel_requested:
                self._cancel_requested = False
                print("[DEBUG] Cancelled after transcription")
                await self.send_status("listening")
                return

            if not result.text.strip():
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
                print("[DEBUG] Cancelled before LLM")
                await self.send_status("listening")
                return

            # Get LLM response
            print(f"[DEBUG] Starting LLM call with model: {self.llm.model_name}")
            await self.send_status("thinking")

            self.sentencizer.reset()
            full_response = []
            cancelled = False

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

            if cancelled:
                print("[DEBUG] Cancelled during LLM streaming")
                await self.send_status("stopped")
                await self.send_status("listening")
                return

            # Flush remaining
            remaining = self.sentencizer.flush()
            if remaining and not self._cancel_requested:
                await self.synthesize_and_send(remaining)

            await self.send_response_end()
            
            # Save assistant message to conversation
            full_response_text = "".join(full_response)
            self._save_message("assistant", full_response_text)
            
            print(f"[DEBUG] Response complete: {len(full_response)} tokens")
            
            # Send "listening" with memory usage to resume audio streaming
            await self.send_status("listening", include_memory=True)
            
        except asyncio.CancelledError:
            print("[DEBUG] Task was cancelled")
            return
        except Exception as e:
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
        await self.send_status("speaking")
        segment = await self.tts.synthesize_async(text)
        if len(segment.audio) > 0:
            await self.send_audio(segment.audio, segment.sample_rate)

    async def process_text_message(self, text: str) -> None:
        """Process a text message (for text-only mode)."""
        try:
            await self.send_transcription(text)
            
            # Save user message to conversation
            self._save_message("user", text)
            
            await self.send_status("thinking")

            self.sentencizer.reset()
            cancelled = False
            full_response = []

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

            if cancelled:
                return

            remaining = self.sentencizer.flush()
            if remaining and not self._cancel_requested:
                await self.synthesize_and_send(remaining)

            await self.send_response_end()
            
            # Save assistant message to conversation
            full_response_text = "".join(full_response)
            self._save_message("assistant", full_response_text)
            
            # Send "listening" with memory usage to resume audio streaming
            await self.send_status("listening", include_memory=True)
            
        except asyncio.CancelledError:
            # Task was cancelled
            return
        except Exception as e:
            print(f"LLM error: {e}")
            await manager.send_json(
                self.websocket,
                {"type": "error", "message": f"LLM error: {str(e)}"}
            )
            await self.send_status("listening", include_memory=True)

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
