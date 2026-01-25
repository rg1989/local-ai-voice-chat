# Local Voice Chatbot

A fully local voice assistant that runs entirely on your Mac, powered by:
- **Qwen3-8B** - Conversational LLM via Ollama
- **MLX Whisper** - Fast speech-to-text optimized for Apple Silicon
- **Kokoro** - Natural text-to-speech with multiple voices
- **Silero VAD** - Voice activity detection

No cloud services, no API keys, complete privacy.

## Features

- **Sub-second latency** - Streaming architecture for natural conversations
- **Voice & text modes** - Use microphone or type your messages
- **Web interface** - Beautiful browser-based UI
- **Multiple voices** - Choose from American and British English voices
- **Conversation memory** - Maintains context across the chat session

## Requirements

- **macOS** with Apple Silicon (M1/M2/M3) recommended
- **16GB RAM** (8GB works with smaller models)
- **Python 3.10+**
- **~10GB disk space** for models

## Quick Start

### 1. Run the setup script

```bash
chmod +x scripts/setup_models.sh
./scripts/setup_models.sh
```

This will:
- Install Homebrew packages (portaudio, ffmpeg)
- Install and configure Ollama
- Download the Qwen3-8B model
- Set up Python environment with uv

### 2. Activate the environment

```bash
source .venv/bin/activate
```

### 3. Start chatting

```bash
# Voice mode (requires microphone)
python -m src.main

# Text mode (no microphone needed)
python -m src.main --text

# Web interface
python -m src.main --web
```

## Manual Installation

If you prefer to install manually:

### System dependencies

```bash
brew install portaudio ffmpeg ollama
```

### Ollama model

```bash
ollama serve  # Start Ollama (run in background)
ollama pull qwen3:8b
```

### Python environment

```bash
# Using uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv
uv pip install -e .

# Or using pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

### CLI Options

```bash
python -m src.main [OPTIONS]

Options:
  --text, -t      Use text input instead of voice
  --no-tts        Disable text-to-speech output
  --web, -w       Start web interface
  --host HOST     Web server host (default: 0.0.0.0)
  --port, -p PORT Web server port (default: 8000)
  --check         Check system requirements
  --list-devices  List audio devices
  --list-voices   List available TTS voices
  --help          Show help message
```

### Examples

```bash
# Start voice chat
python -m src.main

# Text chat with speech output
python -m src.main --text

# Text chat without speech (quiet mode)
python -m src.main --text --no-tts

# Web interface on custom port
python -m src.main --web --port 3000

# Check if everything is set up correctly
python -m src.main --check
```

## Configuration

Create a `.env` file in the project root to customize settings:

```env
# LLM settings
LLM_MODEL_NAME=qwen3:8b
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=512

# TTS settings
TTS_VOICE=af_heart
TTS_SPEED=1.0

# Audio settings
AUDIO_SAMPLE_RATE=16000

# VAD settings
VAD_THRESHOLD=0.5
VAD_MIN_SILENCE_DURATION_MS=500

# Web server
WEB_HOST=0.0.0.0
WEB_PORT=8000

# Debug
DEBUG=false
```

## Available Voices

| Voice ID | Description |
|----------|-------------|
| `af_heart` | American Female - Heart (warm, friendly) |
| `af_bella` | American Female - Bella |
| `af_sarah` | American Female - Sarah |
| `am_adam` | American Male - Adam |
| `am_michael` | American Male - Michael |
| `bf_emma` | British Female - Emma |
| `bm_george` | British Male - George |

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Microphone  │────▶│  Silero VAD │────▶│ MLX Whisper │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Speaker   │◀────│   Kokoro    │◀────│  Qwen3-8B   │
└─────────────┘     │    TTS      │     │ via Ollama  │
                    └─────────────┘     └─────────────┘
                           ▲
                           │
                    ┌─────────────┐
                    │ Sentencizer │
                    │ (streaming) │
                    └─────────────┘
```

### Streaming Pipeline

The key to low latency is streaming at every stage:

1. **VAD** detects when you start/stop speaking
2. **STT** transcribes your speech as audio arrives
3. **LLM** streams tokens as they're generated
4. **Sentencizer** buffers tokens until a sentence is complete
5. **TTS** speaks each sentence while the LLM continues generating

This allows the bot to start speaking before it finishes thinking!

## Troubleshooting

### "Ollama not running"

Start Ollama in a terminal:
```bash
ollama serve
```

### "No audio devices found"

Make sure portaudio is installed:
```bash
brew install portaudio
```

Then reinstall sounddevice:
```bash
uv pip install --force-reinstall sounddevice
```

### "Model not found"

Download the model:
```bash
ollama pull qwen3:8b
```

### Slow performance

1. Make sure you're using Apple Silicon (not Rosetta)
2. Close other memory-intensive apps
3. Try a smaller model: `ollama pull llama3.2:3b`

### High memory usage

The models require significant RAM:
- Qwen3-8B (4-bit): ~5GB
- Whisper: ~1.5GB
- Kokoro: ~100MB
- System overhead: ~2GB

For 8GB Macs, use `llama3.2:3b` instead.

## Development

### Project Structure

```
local-voice-chatbot/
├── src/
│   ├── main.py           # Entry point
│   ├── config.py         # Settings
│   ├── pipeline/
│   │   ├── vad.py        # Voice activity detection
│   │   ├── stt.py        # Speech-to-text
│   │   ├── llm.py        # LLM client
│   │   ├── tts.py        # Text-to-speech
│   │   └── sentencizer.py
│   ├── audio/
│   │   ├── capture.py    # Microphone input
│   │   └── playback.py   # Speaker output
│   └── interfaces/
│       ├── cli.py        # Terminal interface
│       └── web.py        # Web interface
├── web/
│   └── index.html        # Web UI
├── scripts/
│   └── setup_models.sh   # Setup script
├── pyproject.toml
└── README.md
```

### Running in development mode

```bash
# Web interface with auto-reload
python -m src.main --web --reload
```

## License

MIT License - feel free to use and modify for your projects.

## Acknowledgments

- [Ollama](https://ollama.ai/) for easy local LLM deployment
- [MLX](https://github.com/ml-explore/mlx) for Apple Silicon optimization
- [Kokoro](https://github.com/hexgrad/kokoro) for amazing TTS
- [Silero VAD](https://github.com/snakers4/silero-vad) for voice detection# local-ai-voice-chat
