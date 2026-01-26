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
# Step 1: Check/Setup Python Environment
# ============================================
echo -e "${BLUE}[1/5]${NC} Checking Python environment..."

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}  → Creating Python virtual environment...${NC}"
    
    # Check for uv
    if command -v uv &> /dev/null; then
        uv venv
        source .venv/bin/activate
        uv pip install -e .
    else
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -e .
    fi
    echo -e "${GREEN}  ✓ Python environment created${NC}"
else
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
