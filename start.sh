#!/bin/bash

# Local Voice Chatbot - Start Script
# This script sets up (if needed) and starts both backend and frontend servers

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ -f /etc/debian_version ]]; then
        echo "debian"
    elif [[ -f /etc/redhat-release ]]; then
        echo "redhat"
    else
        echo "linux"
    fi
}

OS_TYPE=$(detect_os)

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    
    # Kill background processes
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    
    # Kill any remaining processes on our ports
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    lsof -ti:5173 | xargs kill -9 2>/dev/null || true
    
    echo -e "${GREEN}Goodbye!${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           Local Voice Chatbot - Startup Script            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================
# Step 0: Check Prerequisites
# ============================================
echo -e "${BLUE}[0/5]${NC} Checking prerequisites..."

MISSING_DEPS=""

# Check for Python 3.10+
if ! command -v python3 &> /dev/null; then
    MISSING_DEPS="${MISSING_DEPS}\n  - Python 3.10+ is not installed"
else
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        MISSING_DEPS="${MISSING_DEPS}\n  - Python 3.10+ required (found $PYTHON_VERSION)"
    fi
fi

# Check for python3-venv (common issue on Debian/Ubuntu)
if command -v python3 &> /dev/null; then
    if ! python3 -c "import venv" 2>/dev/null; then
        MISSING_DEPS="${MISSING_DEPS}\n  - Python venv module not installed"
    fi
fi

# Check for Node.js
if ! command -v node &> /dev/null; then
    MISSING_DEPS="${MISSING_DEPS}\n  - Node.js is not installed"
else
    NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_VERSION" -lt 18 ]; then
        MISSING_DEPS="${MISSING_DEPS}\n  - Node.js 18+ required (found v$NODE_VERSION)"
    fi
fi

# Check for npm
if ! command -v npm &> /dev/null; then
    MISSING_DEPS="${MISSING_DEPS}\n  - npm is not installed"
fi

# Check for Linux audio/TTS dependencies
if [[ "$OS_TYPE" == "debian" ]] || [[ "$OS_TYPE" == "linux" ]]; then
    # PortAudio (required by sounddevice)
    if ! ldconfig -p 2>/dev/null | grep -q libportaudio; then
        if ! dpkg -l 2>/dev/null | grep -q portaudio19-dev; then
            MISSING_DEPS="${MISSING_DEPS}\n  - PortAudio library not installed (required for audio)"
        fi
    fi
    # espeak-ng (required by Kokoro TTS for text processing)
    if ! command -v espeak-ng &> /dev/null; then
        MISSING_DEPS="${MISSING_DEPS}\n  - espeak-ng not installed (required for TTS)"
    fi
elif [[ "$OS_TYPE" == "redhat" ]]; then
    if ! ldconfig -p 2>/dev/null | grep -q libportaudio; then
        MISSING_DEPS="${MISSING_DEPS}\n  - PortAudio library not installed (required for audio)"
    fi
    if ! command -v espeak-ng &> /dev/null; then
        MISSING_DEPS="${MISSING_DEPS}\n  - espeak-ng not installed (required for TTS)"
    fi
fi

# If there are missing dependencies, offer to install them
if [ -n "$MISSING_DEPS" ]; then
    echo -e "${RED}  ✗ Missing dependencies:${NC}"
    echo -e "$MISSING_DEPS"
    echo ""
    
    # Check if we can auto-install
    CAN_AUTO_INSTALL=false
    INSTALL_CMD=""
    
    if [[ "$OS_TYPE" == "debian" ]]; then
        CAN_AUTO_INSTALL=true
        INSTALL_CMD="sudo apt update && sudo apt install -y python3 python3-venv python3-pip portaudio19-dev espeak-ng ffmpeg"
        # Check if Node.js is missing and add it
        if ! command -v node &> /dev/null; then
            INSTALL_CMD="$INSTALL_CMD && curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs"
        fi
    elif [[ "$OS_TYPE" == "redhat" ]]; then
        CAN_AUTO_INSTALL=true
        INSTALL_CMD="sudo dnf install -y python3 python3-pip portaudio-devel espeak-ng ffmpeg nodejs npm"
    fi
    
    if [[ "$CAN_AUTO_INSTALL" == true ]]; then
        echo -e "${YELLOW}Would you like to install missing dependencies automatically? (requires sudo)${NC}"
        echo ""
        read -p "Install now? [Y/n] " -n 1 -r
        echo ""
        
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            echo -e "${BLUE}  → Installing dependencies...${NC}"
            eval $INSTALL_CMD
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}  ✓ Dependencies installed successfully${NC}"
                echo ""
                echo -e "${YELLOW}Restarting setup...${NC}"
                echo ""
                exec "$0" "$@"  # Restart the script
            else
                echo -e "${RED}  ✗ Installation failed. Please install manually.${NC}"
                exit 1
            fi
        else
            echo ""
            echo -e "${YELLOW}Manual installation instructions:${NC}"
            echo ""
            if [[ "$OS_TYPE" == "debian" ]]; then
                echo "  sudo apt update"
                echo "  sudo apt install -y python3 python3-venv python3-pip portaudio19-dev espeak-ng ffmpeg"
                if ! command -v node &> /dev/null; then
                    echo "  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -"
                    echo "  sudo apt install -y nodejs"
                fi
            elif [[ "$OS_TYPE" == "redhat" ]]; then
                echo "  sudo dnf install -y python3 python3-pip portaudio-devel espeak-ng ffmpeg nodejs npm"
            fi
            echo ""
            echo -e "After installing, run ${GREEN}./start.sh${NC} again."
            exit 1
        fi
    else
        # macOS or unknown - show manual instructions
        echo -e "${YELLOW}Installation instructions:${NC}"
        echo ""
        
        if [[ "$OS_TYPE" == "macos" ]]; then
            echo "  # Install Homebrew (if not installed):"
            echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            echo ""
            echo "  # Install Python and Node.js:"
            echo "  brew install python@3.11 node"
            echo ""
        else
            echo "  Please install Python 3.10+, Node.js 18+, PortAudio, espeak-ng, and ffmpeg for your distribution."
            echo ""
        fi
        
        echo -e "After installing dependencies, run ${GREEN}./start.sh${NC} again."
        exit 1
    fi
fi

echo -e "${GREEN}  ✓ All prerequisites installed${NC}"

# ============================================
# Step 1: Check/Setup Python Environment
# ============================================
echo -e "${BLUE}[1/5]${NC} Checking Python environment..."

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}  → Creating Python virtual environment...${NC}"
    
    # Check for uv (faster package manager)
    if command -v uv &> /dev/null; then
        uv venv
        source .venv/bin/activate
        echo -e "${YELLOW}  → Installing Python dependencies (using uv)...${NC}"
        uv pip install -e .
    else
        python3 -m venv .venv
        if [ ! -f ".venv/bin/activate" ]; then
            echo -e "${RED}  ✗ Failed to create virtual environment${NC}"
            echo "    Try: python3 -m venv .venv"
            exit 1
        fi
        source .venv/bin/activate
        echo -e "${YELLOW}  → Installing Python dependencies (this may take a few minutes)...${NC}"
        pip install --upgrade pip
        pip install -e .
    fi
    echo -e "${GREEN}  ✓ Python environment created${NC}"
else
    if [ ! -f ".venv/bin/activate" ]; then
        echo -e "${RED}  ✗ Virtual environment is corrupted. Removing and recreating...${NC}"
        rm -rf .venv
        exec "$0" "$@"  # Restart the script
    fi
    source .venv/bin/activate
    echo -e "${GREEN}  ✓ Python environment activated${NC}"
fi

# ============================================
# Step 2: Check/Setup Frontend
# ============================================
echo -e "${BLUE}[2/5]${NC} Checking frontend dependencies..."

if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}  → Installing frontend dependencies...${NC}"
    cd frontend
    npm install
    cd ..
    echo -e "${GREEN}  ✓ Frontend dependencies installed${NC}"
else
    echo -e "${GREEN}  ✓ Frontend dependencies ready${NC}"
fi

# ============================================
# Step 3: Check Ollama
# ============================================
echo -e "${BLUE}[3/5]${NC} Checking Ollama..."

if ! command -v ollama &> /dev/null; then
    echo -e "${RED}  ✗ Ollama not installed. Please install it first:${NC}"
    echo "    brew install ollama"
    exit 1
fi

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${YELLOW}  → Starting Ollama...${NC}"
    ollama serve > /dev/null 2>&1 &
    sleep 2
fi

# Check if model is available
if ! ollama list | grep -q "qwen3:8b"; then
    echo -e "${YELLOW}  → Downloading Qwen3 model (this may take a while)...${NC}"
    ollama pull qwen3:8b
fi

echo -e "${GREEN}  ✓ Ollama ready${NC}"

# ============================================
# Step 4: Start Frontend (in background)
# ============================================
echo -e "${BLUE}[4/5]${NC} Starting frontend server..."

# Kill any existing process on port 5173
lsof -ti:5173 | xargs kill -9 2>/dev/null || true

cd frontend
npm run dev > /tmp/voice-chatbot-frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait for frontend to be ready
echo -n "  → Waiting for frontend"
for i in {1..15}; do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ Frontend running on port 5173${NC}"
else
    echo -e "${RED}  ✗ Frontend failed to start. Check /tmp/voice-chatbot-frontend.log${NC}"
    exit 1
fi

# ============================================
# Step 5: Start Backend (with live logs)
# ============================================
echo -e "${BLUE}[5/5]${NC} Starting backend server..."

# Kill any existing process on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# ============================================
# Ready!
# ============================================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    🎤 Ready to Chat! 🎤                   ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}Open this URL in your browser:${NC}"
echo ""
echo -e "    ${GREEN}➜  http://localhost:5173${NC}"
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}                      Backend Logs                              ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Run backend in foreground so logs are visible
python -m src.main --web
