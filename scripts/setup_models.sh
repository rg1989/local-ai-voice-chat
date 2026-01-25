#!/bin/bash
# Setup script for Local Voice Chatbot
# This script installs required system dependencies and downloads models

set -e

echo "=========================================="
echo "Local Voice Chatbot - Setup Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}Error: This script is designed for macOS only${NC}"
    exit 1
fi

# Check for Apple Silicon
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    echo -e "${GREEN}✓ Apple Silicon detected${NC}"
else
    echo -e "${YELLOW}⚠ Intel Mac detected - performance may be reduced${NC}"
fi

echo ""
echo "Step 1: Installing Homebrew packages..."
echo "----------------------------------------"

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install portaudio for audio I/O
if ! brew list portaudio &> /dev/null; then
    echo "Installing portaudio..."
    brew install portaudio
else
    echo -e "${GREEN}✓ portaudio already installed${NC}"
fi

# Install ffmpeg for audio processing
if ! brew list ffmpeg &> /dev/null; then
    echo "Installing ffmpeg..."
    brew install ffmpeg
else
    echo -e "${GREEN}✓ ffmpeg already installed${NC}"
fi

echo ""
echo "Step 2: Installing Ollama..."
echo "----------------------------"

# Check for Ollama
if ! command -v ollama &> /dev/null; then
    echo "Installing Ollama..."
    brew install ollama
else
    echo -e "${GREEN}✓ Ollama already installed${NC}"
fi

# Start Ollama if not running
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama service..."
    ollama serve &
    sleep 3
fi

echo ""
echo "Step 3: Downloading LLM model..."
echo "--------------------------------"

# Pull the recommended model
echo "Pulling Qwen3 8B (4-bit quantized)..."
echo "This may take a few minutes depending on your internet speed..."
ollama pull qwen3:8b

# Alternative smaller model for 8GB Macs
echo ""
echo -e "${YELLOW}Note: If you have only 8GB RAM, you can also pull a smaller model:${NC}"
echo "  ollama pull llama3.2:3b"

echo ""
echo "Step 4: Setting up Python environment..."
echo "----------------------------------------"

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "Installing uv (fast Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Add uv to PATH for this session
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    
    # Source the env file if it exists
    if [ -f "$HOME/.local/bin/env" ]; then
        source "$HOME/.local/bin/env"
    fi
    
    # Verify uv is now available
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}Error: uv installation failed or not in PATH${NC}"
        echo "Please run: source \$HOME/.local/bin/env"
        echo "Then re-run this script"
        exit 1
    fi
else
    echo -e "${GREEN}✓ uv already installed${NC}"
fi

# Create virtual environment and install dependencies
echo "Creating virtual environment..."

# Check for Python 3.13, 3.12, 3.11, or 3.10 (in order of preference)
PYTHON_BIN=""
for version in python3.13 python3.12 python3.11 python3.10; do
    if command -v $version &> /dev/null; then
        PYTHON_BIN=$version
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo -e "${YELLOW}Python 3.10-3.13 not found. Installing Python 3.12...${NC}"
    brew install python@3.12
    PYTHON_BIN=$(brew --prefix python@3.12)/bin/python3.12
fi

echo "Using Python: $PYTHON_BIN"
uv venv --python "$PYTHON_BIN"

echo "Installing Python dependencies..."
uv pip install -e .

echo ""
echo "Step 5: Pre-downloading ML models..."
echo "------------------------------------"

# Download spaCy model for Kokoro TTS
echo "Downloading spaCy English model for TTS..."
source .venv/bin/activate
python -m spacy download en_core_web_sm || echo "spaCy model will download on first use"

# Pre-download Whisper model (will be cached)
echo "Pre-downloading Whisper model for STT..."
echo "(This downloads on first use, but we can warm up the cache)"
python -c "
import os
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '0'
try:
    from huggingface_hub import hf_hub_download
    # Download the whisper model config
    hf_hub_download(
        'Systran/faster-whisper-large-v3-turbo',
        'config.json',
        local_dir_use_symlinks=False
    )
    print('Whisper model cache initialized')
except Exception as e:
    print(f'Note: Model will download on first use: {e}')
" 2>/dev/null || echo "Model will download on first use"

echo ""
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "To start the voice chatbot:"
echo ""
echo "  1. Activate the virtual environment:"
echo "     source .venv/bin/activate"
echo ""
echo "  2. Run the chatbot:"
echo "     python -m src.main           # Voice mode"
echo "     python -m src.main --text    # Text mode"
echo "     python -m src.main --web     # Web interface"
echo ""
echo "  3. Check system requirements:"
echo "     python -m src.main --check"
echo ""
echo "For more options, run:"
echo "     python -m src.main --help"
echo ""
