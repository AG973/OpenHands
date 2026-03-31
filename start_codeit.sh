#!/bin/bash
# =========================================
#  CODEIT - Full Auto Setup & Start
#  Usage: bash start_codeit.sh
#  (run from the OpenHands repo root, or it auto-detects)
# =========================================

# Auto-detect install directory (where this script lives)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OHDIR="${CODEIT_HOME:-$SCRIPT_DIR}"
UIDIR="$OHDIR/codeit-ui"
BACKEND_PORT="${CODEIT_BACKEND_PORT:-3000}"
FRONTEND_PORT="${CODEIT_FRONTEND_PORT:-8080}"
WORKSPACE="${CODEIT_WORKSPACE:-$HOME/workspace}"
LOG_BACKEND="/tmp/openhands.log"
LOG_FRONTEND="/tmp/codeit-ui.log"
RUNTIME_IMAGE="ghcr.io/all-hands-ai/runtime:0.38-nikolaik"

# Auto-detect host IP for display (Tailscale > LAN > localhost)
HOST_IP="localhost"
if command -v tailscale >/dev/null 2>&1; then
  TS_IP=$(tailscale ip -4 2>/dev/null || true)
  [ -n "$TS_IP" ] && HOST_IP="$TS_IP"
fi
if [ "$HOST_IP" = "localhost" ] && command -v hostname >/dev/null 2>&1; then
  LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
  [ -n "$LAN_IP" ] && HOST_IP="$LAN_IP"
fi
# Allow override via env var
HOST_IP="${CODEIT_HOST_IP:-$HOST_IP}"

echo "========================================="
echo "  CODEIT - Full Auto Setup & Start"
echo "========================================="

# ---- Step 1: Kill ALL existing processes, containers, and free ports ----
echo "[1/7] Stopping all existing processes, containers, and freeing ports..."
pkill -9 -f "python.*openhands" 2>/dev/null || true
pkill -9 -f "uvicorn.*openhands" 2>/dev/null || true
pkill -9 -f "serve dist" 2>/dev/null || true
pkill -9 -f "npx.*serve" 2>/dev/null || true
for PORT in $BACKEND_PORT $FRONTEND_PORT; do
  PIDS=$(lsof -ti :$PORT 2>/dev/null || true)
  if [ -n "$PIDS" ]; then
    echo "  Killing PIDs on port $PORT: $PIDS"
    echo "$PIDS" | xargs kill -9 2>/dev/null || true
  fi
done
# Only stop/remove OpenHands runtime containers (not unrelated workloads)
OH_CONTAINERS=$(docker ps -aq --filter "ancestor=$RUNTIME_IMAGE" 2>/dev/null)
if [ -n "$OH_CONTAINERS" ]; then
  echo "  Stopping OpenHands runtime containers..."
  echo "$OH_CONTAINERS" | xargs docker stop 2>/dev/null || true
  echo "$OH_CONTAINERS" | xargs docker rm 2>/dev/null || true
fi
# Also catch containers with openhands in their name
OH_NAME_CONTAINERS=$(docker ps -aq --filter "name=openhands" 2>/dev/null)
if [ -n "$OH_NAME_CONTAINERS" ]; then
  echo "$OH_NAME_CONTAINERS" | xargs docker stop 2>/dev/null || true
  echo "$OH_NAME_CONTAINERS" | xargs docker rm 2>/dev/null || true
fi
sleep 2
echo "  Done."

# ---- Step 2: Check Python & Node ----
echo "[2/7] Checking Python and Node..."
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: node not found"; exit 1; }
command -v npx >/dev/null 2>&1 || { echo "ERROR: npx not found"; exit 1; }
echo "  Python: $(python3 --version) | Node: $(node --version)"

# ---- Step 3: Install Python dependencies (skip if already installed) ----
echo "[3/7] Checking Python dependencies..."
ALL_PRESENT=1
for PKG in socketio uvicorn fastapi litellm docker toml openhands; do
  python3 -c "import $PKG" 2>/dev/null || { ALL_PRESENT=0; break; }
done
if [ "$ALL_PRESENT" -eq 0 ]; then
  echo "  Some dependencies missing. Installing (first run only, ~2-3 min)..."
  touch "$OHDIR/README.md" 2>/dev/null || true
  cd "$OHDIR" || { echo "ERROR: Cannot cd to $OHDIR"; exit 1; }
  pip3 install --break-system-packages -e "." 2>&1 | tail -3
  echo "  Done."
else
  echo "  All present. Skipping."
fi

# ---- Step 4: Check npm serve ----
echo "[4/7] Checking npm serve..."
if ! command -v serve >/dev/null 2>&1 && ! npx serve --help >/dev/null 2>&1; then
  echo "  Installing serve..."
  npm install -g serve 2>&1 | tail -2
else
  echo "  Already available."
fi

# ---- Step 5: Check Docker runtime image ----
echo "[5/7] Checking Docker runtime image..."
if docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -q "runtime:0.38-nikolaik"; then
  echo "  Already present. Skipping."
else
  echo "  Missing. Pulling (~5 min first time)..."
  docker pull "$RUNTIME_IMAGE" 2>&1 | tail -3
  echo "  Done."
fi

# ---- Step 6: Create config.toml if missing ----
echo "[6/7] Checking config..."
mkdir -p "$WORKSPACE"
if [ ! -f "$OHDIR/config.toml" ]; then
  echo "  Creating config.toml..."
  cat > "$OHDIR/config.toml" << EOF
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
  echo "  Done."
else
  echo "  config.toml exists."
fi

# ---- Step 7: Start Backend + Frontend ----
echo "[7/7] Starting services..."

# Backend
cd "$OHDIR" || { echo "ERROR: Cannot cd to $OHDIR"; exit 1; }
export SERVE_FRONTEND=false
export LLM_MODEL="ollama/llama3.2-vision:11b"
export LLM_BASE_URL="http://localhost:11434"
export LLM_API_KEY="ollama"
export LLM_NATIVE_TOOL_CALLING="false"
export WORKSPACE_BASE="$WORKSPACE"
nohup python3 -m uvicorn openhands.server.listen:app --host 0.0.0.0 --port $BACKEND_PORT > "$LOG_BACKEND" 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Wait for backend
echo "  Waiting for backend..."
for i in $(seq 1 90); do
  if ss -tlnp 2>/dev/null | grep -q ":${BACKEND_PORT} "; then
    echo "  Backend UP on port $BACKEND_PORT (${i}s)"
    break
  fi
  if [ "$i" -eq 90 ]; then
    echo "  ERROR: Backend not up in 90s. Check: tail -f $LOG_BACKEND"
    tail -15 "$LOG_BACKEND" 2>/dev/null
    exit 1
  fi
  sleep 1
done

# Frontend
cd "$UIDIR" || { echo "ERROR: Cannot cd to $UIDIR"; exit 1; }
if [ ! -d "dist" ]; then
  echo "  ERROR: $UIDIR/dist/ not found."
  exit 1
fi
nohup npx serve dist -p $FRONTEND_PORT -s > "$LOG_FRONTEND" 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"
sleep 3

echo ""
echo "========================================="
echo "  CODEIT is running!"
echo "========================================="
echo "  Frontend: http://$HOST_IP:$FRONTEND_PORT"
echo "  Backend:  http://$HOST_IP:$BACKEND_PORT"
echo ""
echo "  Backend logs:  tail -f $LOG_BACKEND"
echo "  Frontend logs: tail -f $LOG_FRONTEND"
echo "========================================="
