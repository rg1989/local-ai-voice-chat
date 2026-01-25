"""FastAPI web interface with WebSocket audio streaming."""

import asyncio
import base64
import json
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..config import settings
from ..pipeline.llm import LLMClient
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

    async def send_json(self, websocket: WebSocket, data: dict) -> None:
        await websocket.send_json(data)

    async def broadcast_json(self, data: dict) -> None:
        for connection in self.active_connections:
            await connection.send_json(data)


manager = ConnectionManager()


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

    def __init__(self, websocket: WebSocket):
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

    async def send_status(self, status: str, data: Optional[dict] = None) -> None:
        """Send status update to client."""
        message = {"type": "status", "status": status}
        if data:
            message["data"] = data
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
        # Convert bytes to numpy array (assuming 16-bit PCM)
        audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Process through VAD
        result = self.vad.process(audio)

        if result.state == SpeechState.SPEECH_START:
            self._is_speaking = True
            await self.send_status("listening")

        elif result.state == SpeechState.SPEECH_END:
            self._is_speaking = False
            await self.process_speech_end()

    async def process_speech_end(self) -> None:
        """Process end of speech segment."""
        # Get accumulated speech from VAD
        speech_audio = self.vad.get_speech_audio()
        
        # Reset VAD for next utterance
        self.vad.reset()
        
        if speech_audio is None or len(speech_audio) < settings.audio.sample_rate * 0.5:
            await self.send_status("listening")
            return

        # Transcribe
        await self.send_status("transcribing")
        result = await self.stt.transcribe_async(speech_audio, settings.audio.sample_rate)

        if not result.text.strip():
            await self.send_status("ready")
            return

        await self.send_transcription(result.text)

        # Get LLM response
        await self.send_status("thinking")

        self.sentencizer.reset()
        full_response = []

        # Stream response
        async for token in await self.llm.chat_async(result.text, stream=True):
            await self.send_response_token(token)
            full_response.append(token)

            # Check for complete sentence
            sentence = self.sentencizer.add_token(token)
            if sentence:
                await self.synthesize_and_send(sentence)

        # Flush remaining
        remaining = self.sentencizer.flush()
        if remaining:
            await self.synthesize_and_send(remaining)

        await self.send_response_end()
        # Send "listening" to resume audio streaming
        await self.send_status("listening")

    async def synthesize_and_send(self, text: str) -> None:
        """Synthesize text and send audio to client."""
        await self.send_status("speaking")
        segment = await self.tts.synthesize_async(text)
        if len(segment.audio) > 0:
            await self.send_audio(segment.audio, segment.sample_rate)

    async def process_text_message(self, text: str) -> None:
        """Process a text message (for text-only mode)."""
        await self.send_transcription(text)
        await self.send_status("thinking")

        self.sentencizer.reset()

        # Stream response
        async for token in await self.llm.chat_async(text, stream=True):
            await self.send_response_token(token)

            sentence = self.sentencizer.add_token(token)
            if sentence:
                await self.synthesize_and_send(sentence)

        remaining = self.sentencizer.flush()
        if remaining:
            await self.synthesize_and_send(remaining)

        await self.send_response_end()
        # Send "listening" to resume audio streaming
        await self.send_status("listening")

    def cleanup(self) -> None:
        """Cleanup resources."""
        self.llm.close()


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for voice/text chat."""
    await manager.connect(websocket)
    session = VoiceChatSession(websocket)

    try:
        await session.send_status("ready")

        while True:
            # Receive message
            message = await websocket.receive()

            if "bytes" in message:
                # Audio data
                await session.process_audio_chunk(message["bytes"])

            elif "text" in message:
                # JSON message
                data = json.loads(message["text"])
                msg_type = data.get("type")

                if msg_type == "text":
                    # Text message
                    await session.process_text_message(data.get("text", ""))

                elif msg_type == "clear_history":
                    session.llm.clear_history()
                    await session.send_status("history_cleared")

                elif msg_type == "set_voice":
                    voice = data.get("voice")
                    if voice:
                        session.tts.set_voice(voice)
                        await session.send_status("voice_changed", {"voice": voice})

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
        session.cleanup()


@app.get("/api/voices")
async def get_voices():
    """Get available TTS voices."""
    return {"voices": TextToSpeech.list_voices()}


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
