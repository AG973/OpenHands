# Running OpenHands with Local Ollama Models

This guide documents every correction and adjustment required to make OpenHands work reliably with local Ollama models. These fixes were discovered and validated during production deployment on a server with a Tesla V100 GPU running GLM-4.7-flash.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Ollama Installation & Configuration](#ollama-installation--configuration)
3. [OpenHands config.toml](#openhands-configtoml)
4. [Starting the Backend](#starting-the-backend)
5. [Settings API (First Run)](#settings-api-first-run)
6. [Issues & Fixes Reference](#issues--fixes-reference)
7. [Switching Models](#switching-models)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- **Ollama** installed and running on the host machine
- **Docker** installed (OpenHands runs agent code in Docker containers)
- **Python 3.12+** with Poetry
- A pulled Ollama model (e.g. `ollama pull glm-4.7-flash`)

---

## Ollama Installation & Configuration

### 1. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Set Context Window Size (CRITICAL)

OpenHands loads ~37 microagent skills into the system prompt, consuming ~20,000+ tokens. Ollama's default context window is only **4,096 tokens**, which is far too small and causes the agent to hang or produce garbage output.

**Fix**: Set `OLLAMA_CONTEXT_LENGTH=32768` in the Ollama systemd service:

```bash
sudo systemctl edit ollama.service
```

Add these lines under `[Service]`:

```ini
[Service]
Environment="OLLAMA_CONTEXT_LENGTH=32768"
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_KEEP_ALIVE=-1"
```

- `OLLAMA_CONTEXT_LENGTH=32768` — Increases context window to 32K tokens (required for OpenHands system prompt)
- `OLLAMA_HOST=0.0.0.0:11434` — Listens on all interfaces so Docker containers can reach it
- `OLLAMA_KEEP_ALIVE=-1` — Keeps model loaded in GPU memory permanently (avoids reload delays)

Then reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### 3. Pull Your Model

```bash
ollama pull glm-4.7-flash    # 19GB, requires ~16GB VRAM
# OR any other model:
ollama pull deepseek-r1:14b
ollama pull qwen3:14b
```

---

## OpenHands config.toml

Create `config.toml` in the OpenHands root directory:

```toml
[core]
workspace_base="./workspace"

[llm]
model="openai/glm-4.7-flash"
base_url="http://host.docker.internal:11434/v1"
api_key="local-llm"
native_tool_calling=false
drop_params=true
modify_params=true
num_retries=3
timeout=600
```

### Field-by-field explanation:

| Field | Value | Why |
|-------|-------|-----|
| `model` | `"openai/glm-4.7-flash"` | The `openai/` prefix tells litellm to use the OpenAI-compatible API format. Ollama exposes this at `/v1/chat/completions`. Do NOT use the `ollama/` or `ollama_chat/` prefixes — they use litellm's native Ollama provider which has response format incompatibilities. |
| `base_url` | `"http://host.docker.internal:11434/v1"` | Docker containers cannot reach `localhost` on the host. `host.docker.internal` is Docker's built-in DNS name that resolves to the host machine. The `/v1` suffix is required for the OpenAI-compatible endpoint. |
| `api_key` | `"local-llm"` | Ollama doesn't require an API key, but litellm requires a non-empty value. Any string works. |
| `native_tool_calling` | `false` | **CRITICAL**: Many Ollama models (GLM, Qwen, etc.) match litellm's `FUNCTION_CALLING_PATTERNS` and auto-detect as supporting native function calling. However, local Ollama models don't handle native tool calling reliably. Setting this to `false` forces OpenHands to use its own JSON-schema-based tool calling instead. |
| `drop_params` | `true` | Drops unsupported parameters from API calls rather than erroring. Ollama doesn't support all OpenAI parameters. |
| `modify_params` | `true` | Allows litellm to modify parameters for compatibility with the Ollama endpoint. |
| `num_retries` | `3` | Retries on transient failures. |
| `timeout` | `600` | 10-minute timeout. Local models on consumer GPUs can be slow, especially with the large system prompt. |

### Fields you must NOT use:

- `stream=false` — There is no `stream` field in `LLMConfig`. Adding it causes Pydantic validation to fail silently with `Extra inputs are not permitted`, which makes the **entire `[llm]` section fall back to defaults** (including `native_tool_calling=None`, which auto-detects to `True` for GLM/Qwen models). This was a critical silent failure we discovered in production.

### Valid LLMConfig fields:

Only these fields are accepted in the `[llm]` section:
```
model, base_url, api_key, native_tool_calling, drop_params, modify_params,
num_retries, timeout, api_version, custom_llm_provider, max_message_chars,
max_input_tokens, max_output_tokens, input_cost_per_token, output_cost_per_token,
temperature, top_p, caching_prompt, disable_stop_word, reasoning_effort,
verify_ssl, log_completions, draft_editor, custom_tokenizer
```

---

## Starting the Backend

The backend must be started with environment variables that propagate LLM config to Docker containers:

```bash
env LLM_NATIVE_TOOL_CALLING=false \
    LLM_DROP_PARAMS=true \
    LLM_MODIFY_PARAMS=true \
    poetry run uvicorn openhands.server.listen:app --host 0.0.0.0 --port 3000
```

### Why environment variables are needed:

OpenHands runs agent code inside Docker containers (the "agent-server"). These containers are **separate processes** that do NOT read `config.toml`. Instead, they receive settings via a POST request from the backend, but **only `model`, `api_key`, and `base_url` are transferred** through this mechanism.

The `native_tool_calling` setting is NOT transferred via the settings POST. When the container builds its LLM config from settings, `native_tool_calling` defaults to `None`. For models matching `FUNCTION_CALLING_PATTERNS` (GLM, Qwen, etc.), `None` auto-detects to `True` — causing the agent to hang on tool calls.

**The fix** (in `openhands/runtime/base.py`): The `_default_env_vars()` function now propagates a safe allowlist of `LLM_`-prefixed environment variables from the backend process into Docker containers. The container's `load_from_env()` then picks up these overrides at startup.

Only non-secret behavioral settings are propagated:
```
LLM_NATIVE_TOOL_CALLING, LLM_DROP_PARAMS, LLM_MODIFY_PARAMS,
LLM_NUM_RETRIES, LLM_TIMEOUT, LLM_DISABLE_STOP_WORD,
LLM_CACHING_PROMPT, LLM_REASONING_EFFORT, LLM_MAX_MESSAGE_CHARS
```

Credentials (`LLM_API_KEY`, `LLM_AWS_ACCESS_KEY_ID`, `LLM_AWS_SECRET_ACCESS_KEY`) are **excluded** from propagation to prevent leaking secrets into sandboxed user code.

---

## Settings API (First Run)

On first run (or after deleting the database), configure settings via the API:

```bash
curl -s -X POST http://localhost:3000/api/settings \
  -H 'Content-Type: application/json' \
  -d '{
    "llm_model": "openai/glm-4.7-flash",
    "llm_base_url": "http://host.docker.internal:11434/v1",
    "llm_api_key": "local-llm"
  }'
```

**Important**: OpenHands stores settings in a SQLite database at `~/.openhands/openhands.db`. If you change the model in `config.toml` but the database already has cached settings, the old model name will be used. To force a reset:

```bash
# Stop backend first
rm -f ~/.openhands/openhands.db
# Restart backend — it will pick up config.toml values
```

Verify settings are correct:

```bash
curl -s http://localhost:3000/api/settings | python3 -c \
  'import sys,json; d=json.load(sys.stdin); print(f"Model: {d.get(\"llm_model\")}\nBase URL: {d.get(\"llm_base_url\")}")'
```

---

## Issues & Fixes Reference

### Issue 1: Docker Container Cannot Reach Ollama

**Symptom**: `ConnectionRefusedError` when agent tries to call LLM  
**Cause**: Docker containers can't access `localhost:11434` on the host  
**Fix**: Use `host.docker.internal:11434` as the `base_url` in config.toml. Also ensure Ollama listens on `0.0.0.0` (not just `127.0.0.1`).

### Issue 2: Agent Hangs or Produces Empty/Garbage Responses

**Symptom**: Agent shows "Running task" indefinitely, or returns `{}` or malformed JSON  
**Cause**: Ollama's default 4096 context window is too small for OpenHands' ~20K token system prompt  
**Fix**: Set `OLLAMA_CONTEXT_LENGTH=32768` in Ollama's systemd service config.

### Issue 3: Agent Hangs on Tool-Calling Tasks

**Symptom**: Agent responds to simple questions (e.g. "2+2") but hangs when asked to create files or run commands  
**Cause**: Model auto-detects as supporting native function calling (`FUNCTION_CALLING_PATTERNS` in litellm), but Ollama models don't handle native tool calling reliably  
**Fix**: Set `native_tool_calling=false` in config.toml AND pass `LLM_NATIVE_TOOL_CALLING=false` as environment variable when starting the backend.

### Issue 4: Config Silently Falls Back to Defaults

**Symptom**: `native_tool_calling=false` in config.toml has no effect; agent still uses native tool calling  
**Cause**: An invalid field in `[llm]` section (e.g. `stream=false`) causes Pydantic validation to fail. The entire `[llm]` section silently reverts to defaults. Look for `Cannot parse [llm] config from toml` in backend logs.  
**Fix**: Only use valid `LLMConfig` fields. Remove any invalid fields. Check logs for the parse warning.

### Issue 5: Old Model Name Cached in Database

**Symptom**: After changing model in config.toml, agent still tries to use the old model  
**Cause**: Settings are cached in SQLite database at `~/.openhands/openhands.db`  
**Fix**: Delete the database and restart backend, or update via the settings API.

### Issue 6: `openai/` vs `ollama/` Provider Prefix

**Symptom**: LLM returns empty responses `{}` or malformed data  
**Cause**: litellm's native `ollama/` and `ollama_chat/` providers have response format incompatibilities with OpenHands  
**Fix**: Use `openai/` prefix with `base_url` pointing to Ollama's `/v1` endpoint. This uses litellm's OpenAI provider which correctly parses Ollama's OpenAI-compatible responses.

---

## Switching Models

To switch to a different Ollama model:

1. Pull the new model:
   ```bash
   ollama pull <model-name>
   ```

2. Update `config.toml`:
   ```toml
   [llm]
   model="openai/<model-name>"
   ```

3. Reset the settings database and restart:
   ```bash
   rm -f ~/.openhands/openhands.db
   # Restart the backend
   ```

**Compatible models tested:**
- `glm-4.7-flash` — 19GB, works well on 16GB+ VRAM
- `qwen3:14b-q4_K_M` — 8.9GB, works on 12GB+ VRAM
- `deepseek-r1:14b` — Works on 16GB+ VRAM

Any model available on Ollama should work — no code changes needed.

---

## Troubleshooting

### Live Log Monitoring

Always monitor logs in real-time when debugging:

```bash
# Backend logs
tail -f /path/to/OpenHands/logs/backend.log

# Docker container events
docker events --filter 'type=container'

# Container-specific logs
docker logs -f <container-id>
```

### Quick Health Checks

```bash
# Backend is running
curl -s http://localhost:3000/api/options/models | head -c 100

# Ollama is reachable
curl -s http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"glm-4.7-flash","messages":[{"role":"user","content":"Hi"}],"max_tokens":50}'

# Settings are correct
curl -s http://localhost:3000/api/settings | python3 -m json.tool

# Container env vars are correct
docker exec <container-id> env | grep LLM_
```

### Common Error Messages

| Error | Meaning | Fix |
|-------|---------|-----|
| `Cannot parse [llm] config from toml` | Invalid field in `[llm]` section | Remove invalid fields, check valid fields list above |
| `model 'xxx' not found` | Model not pulled in Ollama or wrong name in settings | `ollama pull <model>` and reset DB |
| `ConnectionRefusedError` | Docker can't reach Ollama | Use `host.docker.internal` and ensure Ollama binds to `0.0.0.0` |
| `UserWarning: ... cost calculation` | litellm doesn't have pricing for local model | Harmless warning, can be ignored |
| `context_length_exceeded` or truncation | Context window too small | Set `OLLAMA_CONTEXT_LENGTH=32768` |

---

## Summary of Code Changes

All changes are in **one file**: `openhands/runtime/base.py`

The `_default_env_vars()` function was modified to propagate safe LLM config environment variables into Docker sandbox containers. This allows behavioral settings like `native_tool_calling=false` to reach the agent-server container without exposing credentials.

**Before** (upstream OpenHands):
```python
def _default_env_vars(sandbox_config: SandboxConfig) -> dict[str, str]:
    ret = {}
    for key in os.environ:
        if key.startswith('SANDBOX_ENV_'):
            sandbox_key = key.removeprefix('SANDBOX_ENV_')
            ret[sandbox_key] = os.environ[key]
    if sandbox_config.enable_auto_lint:
        ret['ENABLE_AUTO_LINT'] = 'true'
    return ret
```

**After** (this fix):
```python
def _default_env_vars(sandbox_config: SandboxConfig) -> dict[str, str]:
    ret = {}
    for key in os.environ:
        if key.startswith('SANDBOX_ENV_'):
            sandbox_key = key.removeprefix('SANDBOX_ENV_')
            ret[sandbox_key] = os.environ[key]
    if sandbox_config.enable_auto_lint:
        ret['ENABLE_AUTO_LINT'] = 'true'
    # Propagate safe LLM_ config env vars to containers for config override.
    _SAFE_LLM_ENV_VARS = frozenset({
        'LLM_NATIVE_TOOL_CALLING',
        'LLM_DROP_PARAMS',
        'LLM_MODIFY_PARAMS',
        'LLM_NUM_RETRIES',
        'LLM_TIMEOUT',
        'LLM_DISABLE_STOP_WORD',
        'LLM_CACHING_PROMPT',
        'LLM_REASONING_EFFORT',
        'LLM_MAX_MESSAGE_CHARS',
    })
    for key in _SAFE_LLM_ENV_VARS:
        if key in os.environ and key not in ret:
            ret[key] = os.environ[key]
    return ret
```
