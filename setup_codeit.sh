#!/bin/bash
# =========================================
#  CODEIT — One-Command Setup & Run
#  
#  Fresh install:
#    curl -fsSL https://raw.githubusercontent.com/AG973/OpenHands/main/setup_codeit.sh | bash
#  Or:
#    bash setup_codeit.sh
#
#  With GitHub token (private repo):
#    GITHUB_TOKEN=ghp_xxx bash setup_codeit.sh
#
#  Custom install directory:
#    CODEIT_HOME=/opt/codeit bash setup_codeit.sh
# =========================================
set -e

# ---- Configuration (override via env vars) ----
INSTALL_DIR="${CODEIT_HOME:-$HOME/OpenHands}"
BACKEND_PORT="${CODEIT_BACKEND_PORT:-3000}"
FRONTEND_PORT="${CODEIT_FRONTEND_PORT:-5173}"
ADMIN_USER="${CODEIT_ADMIN_USER:-admin}"
ADMIN_PASS="${CODEIT_ADMIN_PASS:-codeit}"
WORKSPACE="${CODEIT_WORKSPACE:-$HOME/workspace}"
REPO_URL="https://github.com/AG973/OpenHands.git"
LOG_BACKEND="/tmp/codeit-backend.log"
LOG_FRONTEND="/tmp/codeit-frontend.log"

# Use GitHub token if provided
if [ -n "$GITHUB_TOKEN" ]; then
  REPO_URL="https://${GITHUB_TOKEN}@github.com/AG973/OpenHands.git"
fi

# Auto-detect host IP (Tailscale > LAN > localhost)
HOST_IP="localhost"
if command -v tailscale >/dev/null 2>&1; then
  TS_IP=$(tailscale ip -4 2>/dev/null || true)
  [ -n "$TS_IP" ] && HOST_IP="$TS_IP"
fi
if [ "$HOST_IP" = "localhost" ] && command -v hostname >/dev/null 2>&1; then
  LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
  [ -n "$LAN_IP" ] && HOST_IP="$LAN_IP"
fi
HOST_IP="${CODEIT_HOST_IP:-$HOST_IP}"

C='\033[0;36m'  # cyan
G='\033[0;32m'  # green
R='\033[0;31m'  # red
Y='\033[0;33m'  # yellow
NC='\033[0m'    # reset

echo ""
echo -e "${C}=========================================${NC}"
echo -e "${C}  CODEIT — One-Command Setup & Run${NC}"
echo -e "${C}=========================================${NC}"
echo ""

# ---- Step 1: Check prerequisites ----
echo -e "${Y}[1/8] Checking prerequisites...${NC}"
MISSING=""
command -v python3 >/dev/null 2>&1 || MISSING="$MISSING python3"
command -v pip3 >/dev/null 2>&1    || MISSING="$MISSING pip3"
command -v node >/dev/null 2>&1    || MISSING="$MISSING node"
command -v npm >/dev/null 2>&1     || MISSING="$MISSING npm"
command -v git >/dev/null 2>&1     || MISSING="$MISSING git"

if [ -n "$MISSING" ]; then
  echo -e "${R}  Missing:${NC}$MISSING"
  echo ""
  echo "  Install them first. On Ubuntu/Debian:"
  echo "    sudo apt update && sudo apt install -y python3 python3-pip nodejs npm git"
  echo ""
  echo "  On macOS:"
  echo "    brew install python node git"
  exit 1
fi
echo -e "  Python: $(python3 --version) | Node: $(node --version) | npm: $(npm --version)"

# ---- Step 2: Kill existing CODEIT processes ----
echo -e "${Y}[2/8] Stopping any existing CODEIT processes...${NC}"
pkill -9 -f "uvicorn.*openhands" 2>/dev/null || true
pkill -9 -f "python.*openhands" 2>/dev/null || true
# Kill processes on our ports
for PORT in $BACKEND_PORT $FRONTEND_PORT; do
  PIDS=$(lsof -ti :$PORT 2>/dev/null || true)
  if [ -n "$PIDS" ]; then
    echo "  Killing PIDs on port $PORT: $PIDS"
    echo "$PIDS" | xargs kill -9 2>/dev/null || true
  fi
done
sleep 1
echo "  Done."

# ---- Step 3: Clone or update repo ----
echo -e "${Y}[3/8] Setting up repository...${NC}"
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "  Repo exists at $INSTALL_DIR — pulling latest..."
  cd "$INSTALL_DIR"
  git pull origin main 2>&1 | tail -3
else
  echo "  Cloning to $INSTALL_DIR..."
  git clone "$REPO_URL" "$INSTALL_DIR" 2>&1 | tail -3
  cd "$INSTALL_DIR"
fi
echo "  Done."

# ---- Step 4: Install Python dependencies ----
echo -e "${Y}[4/8] Installing Python dependencies...${NC}"
ALL_PRESENT=1
for PKG in socketio uvicorn fastapi litellm openhands; do
  python3 -c "import $PKG" 2>/dev/null || { ALL_PRESENT=0; break; }
done
if [ "$ALL_PRESENT" -eq 0 ]; then
  echo "  Installing (first run only, ~2-3 min)..."
  cd "$INSTALL_DIR"
  pip3 install --break-system-packages -e "." 2>&1 | tail -5
  echo "  Done."
else
  echo "  All present. Skipping."
fi

# ---- Step 5: Install frontend dependencies ----
echo -e "${Y}[5/8] Installing frontend dependencies...${NC}"
cd "$INSTALL_DIR/codeit-ui"
if [ ! -d "node_modules" ]; then
  echo "  Running npm ci (first run only, ~1 min)..."
  npm ci 2>&1 | tail -3
  echo "  Done."
else
  echo "  node_modules exists. Skipping."
fi

# ---- Step 6: Clean stale .env (common gotcha) ----
echo -e "${Y}[6/8] Cleaning stale config...${NC}"
if [ -f "$INSTALL_DIR/codeit-ui/.env" ]; then
  if grep -q "VITE_BACKEND_URL" "$INSTALL_DIR/codeit-ui/.env" 2>/dev/null; then
    echo "  Removing stale VITE_BACKEND_URL from .env (prevents proxy issues)..."
    sed -i '/VITE_BACKEND_URL/d' "$INSTALL_DIR/codeit-ui/.env"
  fi
fi
echo "  Done."

# ---- Step 7: Create workspace & config ----
echo -e "${Y}[7/8] Setting up workspace and config...${NC}"
mkdir -p "$WORKSPACE"
mkdir -p "$HOME/.codeit"
if [ ! -f "$INSTALL_DIR/config.toml" ]; then
  echo "  Creating config.toml..."
  cat > "$INSTALL_DIR/config.toml" << EOF
[core]
workspace_base = "$WORKSPACE"
run_as_openhands = true

[llm]
model = "ollama/llama3.2-vision:11b"
provider = "ollama"
base_url = "http://localhost:11434"
api_key = "ollama"
native_tool_calling = false
max_input_tokens = 32768
max_output_tokens = 4096
EOF
fi
echo "  Done."

# ---- Step 8: Start backend + frontend ----
echo -e "${Y}[8/8] Starting services...${NC}"

# Backend
cd "$INSTALL_DIR"
export CODEIT_ADMIN_USER="$ADMIN_USER"
export CODEIT_ADMIN_PASS="$ADMIN_PASS"
export CODEIT_CORS_ORIGINS="http://localhost:$FRONTEND_PORT,http://$HOST_IP:$FRONTEND_PORT"
export SERVE_FRONTEND=false
export WORKSPACE_BASE="$WORKSPACE"

nohup python3 -m uvicorn openhands.server.app:app --host 0.0.0.0 --port $BACKEND_PORT > "$LOG_BACKEND" 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID (port $BACKEND_PORT)"

# Wait for backend
echo "  Waiting for backend to start..."
for i in $(seq 1 60); do
  if curl -s "http://localhost:$BACKEND_PORT/api/codeit/health" >/dev/null 2>&1; then
    echo -e "  ${G}Backend UP${NC} (${i}s)"
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo -e "  ${R}Backend failed to start in 60s${NC}"
    echo "  Check logs: tail -f $LOG_BACKEND"
    tail -15 "$LOG_BACKEND" 2>/dev/null
    exit 1
  fi
  sleep 1
done

# Frontend (Vite dev server — auto-proxies /api to backend)
cd "$INSTALL_DIR/codeit-ui"
nohup npm run dev -- --host 0.0.0.0 --port $FRONTEND_PORT > "$LOG_FRONTEND" 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID (port $FRONTEND_PORT)"

# Wait for frontend
sleep 3
for i in $(seq 1 30); do
  if curl -s "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
    echo -e "  ${G}Frontend UP${NC} (${i}s)"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo -e "  ${Y}Frontend may still be starting...${NC}"
  fi
  sleep 1
done

echo ""
echo -e "${G}=========================================${NC}"
echo -e "${G}  CODEIT is running!${NC}"
echo -e "${G}=========================================${NC}"
echo ""
echo -e "  ${C}Open in browser:${NC}  http://$HOST_IP:$FRONTEND_PORT"
echo ""
echo -e "  ${C}Login:${NC}  username: ${G}$ADMIN_USER${NC}"
echo -e "          password: ${G}$ADMIN_PASS${NC}"
echo ""
echo -e "  ${C}Backend API:${NC}    http://$HOST_IP:$BACKEND_PORT"
echo -e "  ${C}Health check:${NC}   curl http://localhost:$BACKEND_PORT/api/codeit/health"
echo ""
echo -e "  ${C}Logs:${NC}"
echo "    Backend:  tail -f $LOG_BACKEND"
echo "    Frontend: tail -f $LOG_FRONTEND"
echo ""
echo -e "  ${C}Stop:${NC}  kill $BACKEND_PID $FRONTEND_PID"
echo -e "${G}=========================================${NC}"
