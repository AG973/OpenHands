#!/usr/bin/env bash
#
# Run OpenHands E2E tests with all 3 models sequentially.
#
# This script launches the OpenHands agent with each model backend and
# asks it to build a real estate marketplace from the spec file.
#
# Prerequisites:
#   - OpenHands installed (pip install -e .)
#   - Ollama running locally (for DeepSeek R1)
#   - OLLAMA_API_KEY set (for Kimi2.5 and GLM5 cloud models)
#   - tmux installed (for local runtime)
#   - Playwright browsers installed (npx playwright install chromium)
#
# Usage:
#   export OLLAMA_API_KEY="your-ollama-cloud-api-key"
#   bash run_all_models.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORKSPACE="${REPO_ROOT}/workspace"
RESULTS_DIR="${SCRIPT_DIR}/e2e-results"
SPEC_FILE="${SCRIPT_DIR}/realestate_spec.md"

# ── Validate prerequisites ─────────────────────────────────────────────────

if [ -z "${OLLAMA_API_KEY:-}" ]; then
    echo "WARNING: OLLAMA_API_KEY not set — cloud models (Kimi2.5, GLM5) will be skipped."
    echo "  Get your key at: https://ollama.com/settings/keys"
    echo ""
fi

if ! command -v tmux &>/dev/null; then
    echo "ERROR: tmux is required. Install with: sudo apt install tmux"
    exit 1
fi

mkdir -p "$WORKSPACE" "$RESULTS_DIR"

# ── Task specification ─────────────────────────────────────────────────────

TASK="Build a complete real estate marketplace backend with FastAPI. Create:
1. backend/models.py — 10 SQLAlchemy models (User, Property, Address, PropertyImage, PropertyFeature, Favorite, Inquiry, Review, Agency, AgentProfile)
2. backend/main.py — FastAPI app with full CRUD
3. backend/auth.py — JWT auth with RBAC
4. backend/schemas.py — Pydantic v2 schemas
5. requirements.txt
All models must have relationships, foreign keys, and timestamps."

# ── Run a single model test ────────────────────────────────────────────────

run_test() {
    local MODEL_NAME=$1
    local LLM_MODEL_VAL=$2
    local BASE_URL=$3
    local API_KEY=$4

    echo "============================================"
    echo "  Testing: ${MODEL_NAME}"
    echo "  Model:   ${LLM_MODEL_VAL}"
    echo "  URL:     ${BASE_URL}"
    echo "============================================"

    local LOG_FILE="${RESULTS_DIR}/${MODEL_NAME}_$(date +%Y%m%d_%H%M%S).log"

    export LLM_MODEL="$LLM_MODEL_VAL"
    export LLM_BASE_URL="$BASE_URL"
    export LLM_API_KEY="$API_KEY"
    export LLM_NATIVE_TOOL_CALLING=false
    export LLM_DROP_PARAMS=true

    local START_TIME=$(date +%s)

    # Run OpenHands with 15 iterations max, 10-minute timeout
    timeout 600 python -m openhands.core.main \
        -t "$TASK" \
        -d "$WORKSPACE" \
        -i 15 \
        2>&1 | tee "$LOG_FILE" || true

    local END_TIME=$(date +%s)
    local ELAPSED=$((END_TIME - START_TIME))

    echo ""
    echo "  Completed: ${MODEL_NAME} in ${ELAPSED}s"
    echo "  Log: ${LOG_FILE}"
    echo ""

    # Save workspace output
    if [ -d "$WORKSPACE" ]; then
        local SNAPSHOT="${RESULTS_DIR}/${MODEL_NAME}_workspace"
        cp -r "$WORKSPACE" "$SNAPSHOT" 2>/dev/null || true
        echo "  Workspace snapshot: ${SNAPSHOT}"
    fi
}

# ── Run all models ─────────────────────────────────────────────────────────

echo ""
echo "========================================================"
echo "  OpenHands E2E Evaluation — Real Estate Marketplace"
echo "  $(date)"
echo "========================================================"
echo ""

# 1. DeepSeek R1 (local Ollama — requires GPU)
if curl -s http://localhost:11434/api/tags &>/dev/null; then
    run_test "deepseek-r1" "deepseek-r1:8b" "http://localhost:11434/v1" "ollama"
else
    echo "SKIP: DeepSeek R1 — local Ollama not running (start with: ollama serve)"
fi

# 2. Kimi2.5 (cloud — no GPU needed)
if [ -n "${OLLAMA_API_KEY:-}" ]; then
    run_test "kimi-k2.5" "kimi-k2.5" "https://ollama.com/v1" "$OLLAMA_API_KEY"
else
    echo "SKIP: Kimi2.5 — OLLAMA_API_KEY not set"
fi

# 3. GLM5 (cloud — no GPU needed)
if [ -n "${OLLAMA_API_KEY:-}" ]; then
    run_test "glm-5" "glm-5" "https://ollama.com/v1" "$OLLAMA_API_KEY"
else
    echo "SKIP: GLM5 — OLLAMA_API_KEY not set"
fi

echo ""
echo "========================================================"
echo "  All tests complete. Results in: ${RESULTS_DIR}"
echo "========================================================"
