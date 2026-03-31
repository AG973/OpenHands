#!/usr/bin/env bash
# ============================================================================
#  CODEIT + OpenHands — One-File Server Setup
#
#  This script installs EVERYTHING needed to run OpenHands/CODEIT with:
#    - DeepSeek R1 (local Ollama, uses your V100 GPU)
#    - Kimi2.5 (Ollama cloud API, no GPU needed)
#    - GLM5 (Ollama cloud API, no GPU needed)
#
#  Usage:
#    # Basic install (cloud models only — no GPU required):
#    export OLLAMA_API_KEY="your-ollama-cloud-api-key"
#    bash setup_codeit_server.sh
#
#    # Full install (cloud + local DeepSeek R1 on GPU):
#    export OLLAMA_API_KEY="your-ollama-cloud-api-key"
#    bash setup_codeit_server.sh --with-local-models
#
#    # Skip interactive prompts:
#    bash setup_codeit_server.sh --yes
#
#  Get your Ollama API key at: https://ollama.com/settings/keys
#  (Sign in → Settings → API Keys → Create New Key)
#
#  Tested on: Ubuntu 22.04/24.04, V100 16GB
# ============================================================================
set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────

INSTALL_DIR="${CODEIT_INSTALL_DIR:-$HOME/OpenHands}"
WORKSPACE_DIR="${CODEIT_WORKSPACE:-$HOME/workspace}"
FRONTEND_PORT="${CODEIT_FRONTEND_PORT:-8080}"
BACKEND_PORT="${CODEIT_BACKEND_PORT:-3000}"
OLLAMA_API_KEY="${OLLAMA_API_KEY:-}"
WITH_LOCAL_MODELS=false
AUTO_YES=false
DEEPSEEK_MODEL="deepseek-r1:8b"  # 8B fits in V100 16GB with room to spare

# ── Parse arguments ────────────────────────────────────────────────────────

for arg in "$@"; do
    case $arg in
        --with-local-models) WITH_LOCAL_MODELS=true ;;
        --yes|-y) AUTO_YES=true ;;
        --help|-h)
            echo "Usage: bash setup_codeit_server.sh [--with-local-models] [--yes]"
            echo ""
            echo "Options:"
            echo "  --with-local-models   Install Ollama + pull DeepSeek R1 for local GPU inference"
            echo "  --yes, -y             Skip confirmation prompts"
            echo ""
            echo "Environment variables:"
            echo "  OLLAMA_API_KEY        Ollama cloud API key (for Kimi2.5, GLM5)"
            echo "  CODEIT_INSTALL_DIR    Install directory (default: ~/OpenHands)"
            echo "  CODEIT_WORKSPACE      Agent workspace (default: ~/workspace)"
            echo "  CODEIT_FRONTEND_PORT  Frontend port (default: 8080)"
            echo "  CODEIT_BACKEND_PORT   Backend port (default: 3000)"
            exit 0
            ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

# ── Helper functions ───────────────────────────────────────────────────────

log()  { echo -e "\n\033[1;36m[$1]\033[0m $2"; }
ok()   { echo -e "  \033[1;32m✓\033[0m $1"; }
warn() { echo -e "  \033[1;33m⚠\033[0m $1"; }
err()  { echo -e "  \033[1;31m✗\033[0m $1"; }
need() { command -v "$1" &>/dev/null; }

confirm() {
    if $AUTO_YES; then return 0; fi
    read -rp "  → $1 [Y/n] " ans
    [[ -z "$ans" || "$ans" =~ ^[Yy] ]]
}

HOST_IP="localhost"
if command -v hostname &>/dev/null; then
    LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
    [ -n "$LAN_IP" ] && HOST_IP="$LAN_IP"
fi

# ── Banner ─────────────────────────────────────────────────────────────────

echo ""
echo "=============================================="
echo "  CODEIT — Full Server Setup"
echo "=============================================="
echo ""
echo "  Install dir:     $INSTALL_DIR"
echo "  Workspace:       $WORKSPACE_DIR"
echo "  Frontend port:   $FRONTEND_PORT"
echo "  Backend port:    $BACKEND_PORT"
echo "  Host IP:         $HOST_IP"
echo "  Local models:    $WITH_LOCAL_MODELS"
echo "  Ollama API key:  ${OLLAMA_API_KEY:+set}${OLLAMA_API_KEY:-NOT SET}"
echo ""

if [ -z "$OLLAMA_API_KEY" ]; then
    warn "OLLAMA_API_KEY not set — cloud models (Kimi2.5, GLM5) won't work."
    warn "Get your key at: https://ollama.com/settings/keys"
    echo ""
fi

if ! $AUTO_YES; then
    confirm "Proceed with installation?" || exit 0
fi

# ============================================================================
#  STEP 1: System Dependencies
# ============================================================================

log "1/8" "Installing system dependencies..."

sudo apt-get update -qq

# Core tools
PKGS="git curl wget build-essential tmux jq lsof net-tools unzip"

# Python build deps
PKGS="$PKGS python3 python3-pip python3-venv python3-dev"

# Docker deps (if not installed)
if ! need docker; then
    PKGS="$PKGS ca-certificates gnupg"
fi

sudo apt-get install -y -qq $PKGS
ok "System packages installed"

# ============================================================================
#  STEP 2: Python 3.11+ (OpenHands requires 3.11 or 3.12)
# ============================================================================

log "2/8" "Checking Python version..."

PYTHON_CMD=""
for py in python3.12 python3.11 python3; do
    if command -v "$py" &>/dev/null; then
        PY_VER=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
            PYTHON_CMD="$py"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    warn "Python 3.11+ not found. Installing Python 3.12..."
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3.12 python3.12-venv python3.12-dev
    PYTHON_CMD="python3.12"
fi

ok "Python: $($PYTHON_CMD --version)"

# ============================================================================
#  STEP 3: Node.js 20+ (for frontend build)
# ============================================================================

log "3/8" "Checking Node.js..."

if need node; then
    NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_VER" -ge 18 ]; then
        ok "Node.js: $(node -v)"
    else
        warn "Node.js too old ($(node -v)). Installing v20..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y -qq nodejs
        ok "Node.js: $(node -v)"
    fi
else
    warn "Node.js not found. Installing v20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y -qq nodejs
    ok "Node.js: $(node -v)"
fi

# ============================================================================
#  STEP 4: Docker (for OpenHands sandbox runtime)
# ============================================================================

log "4/8" "Checking Docker..."

if need docker; then
    ok "Docker: $(docker --version | head -1)"
else
    warn "Docker not found. Installing..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    ok "Docker installed. NOTE: You may need to log out and back in for group permissions."
fi

# Ensure Docker daemon is running
if ! docker info &>/dev/null; then
    sudo systemctl start docker 2>/dev/null || sudo service docker start 2>/dev/null || true
fi

# Pull the OpenHands runtime image
RUNTIME_IMAGE="ghcr.io/all-hands-ai/runtime:0.38-nikolaik"
log "4b/8" "Pulling OpenHands runtime Docker image (~2GB)..."
docker pull "$RUNTIME_IMAGE" || warn "Docker pull failed — will retry on first run"

# ============================================================================
#  STEP 5: Ollama (local LLM server)
# ============================================================================

log "5/8" "Setting up Ollama..."

if need ollama; then
    ok "Ollama already installed: $(ollama --version 2>/dev/null || echo 'installed')"
else
    if $WITH_LOCAL_MODELS; then
        warn "Installing Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh
        ok "Ollama installed"
    else
        warn "Ollama not installed (skipping — not needed for cloud-only mode)"
        warn "To install later: curl -fsSL https://ollama.com/install.sh | sh"
    fi
fi

# Pull local model if requested
if $WITH_LOCAL_MODELS && need ollama; then
    log "5b/8" "Pulling DeepSeek R1 model (~4.9GB)..."

    # Start Ollama if not running
    if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
        ollama serve &>/dev/null &
        sleep 3
    fi

    ollama pull "$DEEPSEEK_MODEL"
    ok "DeepSeek R1 ready: $DEEPSEEK_MODEL"
fi

# ============================================================================
#  STEP 6: Clone & Install OpenHands (CODEIT fork)
# ============================================================================

log "6/8" "Setting up OpenHands/CODEIT..."

if [ -d "$INSTALL_DIR/.git" ]; then
    ok "Repository exists at $INSTALL_DIR — pulling latest..."
    cd "$INSTALL_DIR"
    git pull origin main 2>/dev/null || git pull 2>/dev/null || true
else
    warn "Cloning AG973/OpenHands..."
    git clone https://github.com/AG973/OpenHands.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Create virtual environment
if [ ! -d "$INSTALL_DIR/.venv" ]; then
    $PYTHON_CMD -m venv "$INSTALL_DIR/.venv"
fi

source "$INSTALL_DIR/.venv/bin/activate"
ok "Virtual environment: $INSTALL_DIR/.venv"

# Install OpenHands + dependencies
pip install --upgrade pip setuptools wheel -q
pip install -e "$INSTALL_DIR" -q 2>&1 | tail -3
pip install openai httpx -q  # for direct LLM tests
ok "OpenHands Python packages installed"

# Install Playwright browsers (needed for agent sandbox)
if ! npx playwright --version &>/dev/null 2>&1; then
    npx playwright install chromium 2>/dev/null || true
fi

# ============================================================================
#  STEP 7: Build CODEIT Frontend
# ============================================================================

log "7/8" "Building CODEIT frontend..."

UIDIR="$INSTALL_DIR/codeit-ui"
if [ -d "$UIDIR" ]; then
    cd "$UIDIR"
    npm install --legacy-peer-deps 2>&1 | tail -3

    # Create production .env
    cat > "$UIDIR/.env" <<ENVEOF
VITE_BACKEND_BASE_URL=http://${HOST_IP}:${BACKEND_PORT}
VITE_MOCK_API=false
ENVEOF

    npm run build 2>&1 | tail -5
    ok "Frontend built: $UIDIR/dist"
else
    warn "codeit-ui directory not found — frontend build skipped"
    warn "You can build it manually after cloning"
fi

# ============================================================================
#  STEP 8: Create Configuration & Helper Scripts
# ============================================================================

log "8/8" "Creating configuration files..."

mkdir -p "$WORKSPACE_DIR"

# ── Ollama cloud config ────────────────────────────────────────────────────

cat > "$INSTALL_DIR/.env.llm" <<ENVEOF
# ============================================
#  LLM Configuration for CODEIT
# ============================================

# ── Ollama Cloud API (Kimi2.5, GLM5 — no GPU needed) ──
OLLAMA_API_KEY=${OLLAMA_API_KEY}
OLLAMA_CLOUD_URL=https://ollama.com/v1

# ── Local Ollama (DeepSeek R1 — needs GPU) ──
OLLAMA_LOCAL_URL=http://localhost:11434/v1

# ── Default model (change to switch models) ──
#   Cloud:  kimi-k2.5, glm-5
#   Local:  deepseek-r1:8b
LLM_MODEL=kimi-k2.5
LLM_BASE_URL=https://ollama.com/v1
LLM_API_KEY=${OLLAMA_API_KEY}
LLM_NATIVE_TOOL_CALLING=false
LLM_DROP_PARAMS=true
ENVEOF

ok "LLM config: $INSTALL_DIR/.env.llm"

# ── Quick-start script ─────────────────────────────────────────────────────

cat > "$INSTALL_DIR/start.sh" <<'STARTEOF'
#!/usr/bin/env bash
# Quick-start CODEIT (backend + frontend)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.venv/bin/activate"
source "$SCRIPT_DIR/.env.llm"

HOST_IP="localhost"
LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
[ -n "$LAN_IP" ] && HOST_IP="$LAN_IP"

BACKEND_PORT="${CODEIT_BACKEND_PORT:-3000}"
FRONTEND_PORT="${CODEIT_FRONTEND_PORT:-8080}"
WORKSPACE="${CODEIT_WORKSPACE:-$HOME/workspace}"

echo "Starting CODEIT..."
echo "  Backend:  http://${HOST_IP}:${BACKEND_PORT}"
echo "  Frontend: http://${HOST_IP}:${FRONTEND_PORT}"

# Kill existing processes
pkill -9 -f "python.*openhands" 2>/dev/null || true
pkill -9 -f "serve dist" 2>/dev/null || true
sleep 1

# Export LLM env vars for OpenHands
export LLM_MODEL LLM_BASE_URL LLM_API_KEY LLM_NATIVE_TOOL_CALLING LLM_DROP_PARAMS
export WORKSPACE_BASE="$WORKSPACE"

# Start backend
cd "$SCRIPT_DIR"
python -m openhands.server.listen --port "$BACKEND_PORT" &>/tmp/openhands.log &
echo "  Backend PID: $!"

# Start frontend
if [ -d "$SCRIPT_DIR/codeit-ui/dist" ]; then
    cd "$SCRIPT_DIR/codeit-ui"
    npx serve dist -l "$FRONTEND_PORT" --cors &>/tmp/codeit-ui.log &
    echo "  Frontend PID: $!"
fi

sleep 2
echo ""
echo "CODEIT is running!"
echo "  Open: http://${HOST_IP}:${FRONTEND_PORT}"
echo "  Logs: tail -f /tmp/openhands.log"
STARTEOF
chmod +x "$INSTALL_DIR/start.sh"
ok "Start script: $INSTALL_DIR/start.sh"

# ── Model switcher script ──────────────────────────────────────────────────

cat > "$INSTALL_DIR/switch_model.sh" <<'SWITCHEOF'
#!/usr/bin/env bash
# Switch the active LLM model
# Usage: bash switch_model.sh kimi-k2.5|glm-5|deepseek-r1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env.llm"

MODEL="${1:-}"
if [ -z "$MODEL" ]; then
    echo "Usage: bash switch_model.sh <model>"
    echo ""
    echo "Available models:"
    echo "  kimi-k2.5    — Ollama cloud (no GPU, fast)"
    echo "  glm-5        — Ollama cloud (no GPU, fast)"
    echo "  deepseek-r1  — Local Ollama (needs GPU + ollama serve)"
    exit 1
fi

case "$MODEL" in
    kimi-k2.5|glm-5)
        sed -i "s|^LLM_MODEL=.*|LLM_MODEL=$MODEL|" "$ENV_FILE"
        sed -i "s|^LLM_BASE_URL=.*|LLM_BASE_URL=https://ollama.com/v1|" "$ENV_FILE"
        source "$ENV_FILE"
        sed -i "s|^LLM_API_KEY=.*|LLM_API_KEY=$OLLAMA_API_KEY|" "$ENV_FILE"
        echo "Switched to $MODEL (cloud). Restart CODEIT to apply."
        ;;
    deepseek-r1)
        sed -i "s|^LLM_MODEL=.*|LLM_MODEL=deepseek-r1:8b|" "$ENV_FILE"
        sed -i "s|^LLM_BASE_URL=.*|LLM_BASE_URL=http://localhost:11434/v1|" "$ENV_FILE"
        sed -i "s|^LLM_API_KEY=.*|LLM_API_KEY=ollama|" "$ENV_FILE"
        echo "Switched to DeepSeek R1 (local). Make sure 'ollama serve' is running."
        ;;
    *)
        echo "Unknown model: $MODEL"
        echo "Valid: kimi-k2.5, glm-5, deepseek-r1"
        exit 1
        ;;
esac
SWITCHEOF
chmod +x "$INSTALL_DIR/switch_model.sh"
ok "Model switcher: $INSTALL_DIR/switch_model.sh"

# ── Direct LLM test script ────────────────────────────────────────────────

if [ -f "$INSTALL_DIR/tests/llm-evaluation/direct_llm_test.py" ]; then
    ok "LLM test script: $INSTALL_DIR/tests/llm-evaluation/direct_llm_test.py"
fi

# ============================================================================
#  DONE
# ============================================================================

echo ""
echo "=============================================="
echo "  CODEIT Setup Complete!"
echo "=============================================="
echo ""
echo "  Install dir:  $INSTALL_DIR"
echo "  Workspace:    $WORKSPACE_DIR"
echo "  Host IP:      $HOST_IP"
echo ""
echo "  ── Quick Start ──────────────────────────"
echo ""
echo "  1. Start CODEIT:"
echo "     cd $INSTALL_DIR && bash start.sh"
echo ""
echo "  2. Open in browser:"
echo "     http://${HOST_IP}:${FRONTEND_PORT}"
echo ""
echo "  3. Switch models:"
echo "     bash switch_model.sh kimi-k2.5   # cloud (default)"
echo "     bash switch_model.sh glm-5       # cloud"
echo "     bash switch_model.sh deepseek-r1 # local GPU"
echo ""
echo "  4. Run direct LLM evaluation:"
echo "     source .venv/bin/activate"
echo "     python tests/llm-evaluation/direct_llm_test.py --all"
echo ""
if [ -z "$OLLAMA_API_KEY" ]; then
    echo "  ⚠  IMPORTANT: Set your Ollama API key before starting!"
    echo "     export OLLAMA_API_KEY=\"your-key-here\""
    echo "     Get it at: https://ollama.com/settings/keys"
    echo ""
fi
echo "  ── Logs ───────────────────────────────────"
echo "  Backend:  tail -f /tmp/openhands.log"
echo "  Frontend: tail -f /tmp/codeit-ui.log"
echo ""
