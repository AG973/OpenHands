# Local Server Setup Guide — V100 16GB

## Prerequisites

- Ubuntu 22.04 or 24.04
- NVIDIA V100 16GB GPU (or any GPU with 8GB+ VRAM for DeepSeek R1)
- 16GB+ system RAM
- 50GB free disk space
- Internet access (for Ollama cloud API)

## Quick Setup (One Command)

```bash
# 1. Get your Ollama API key from: https://ollama.com/settings/keys
export OLLAMA_API_KEY="your-key-here"

# 2. Run the setup script (cloud models only — no GPU needed):
bash tests/llm-evaluation/setup_codeit_server.sh

# OR with local DeepSeek R1 model (uses GPU):
bash tests/llm-evaluation/setup_codeit_server.sh --with-local-models
```

The script installs everything: Python 3.12, Node.js 20, Docker, Ollama, OpenHands, and the CODEIT frontend.

## What Gets Installed

| Component | Purpose | Size |
|---|---|---|
| Python 3.12 + venv | OpenHands backend | ~200MB |
| Node.js 20 | Frontend build | ~100MB |
| Docker | Agent sandbox runtime | ~500MB |
| OpenHands runtime image | Docker sandbox | ~2GB |
| Ollama | Local LLM server | ~50MB |
| DeepSeek R1 8B | Local model (optional) | ~4.9GB |
| CODEIT frontend | Web UI | ~50MB |

## Available Models

### Cloud Models (No GPU Required)
These run on Ollama's cloud infrastructure. You only need an API key.

| Model | API Base URL | Notes |
|---|---|---|
| **kimi-k2.5** | `https://ollama.com/v1` | Best code quality, ~125s response |
| **glm-5** | `https://ollama.com/v1` | Strong alternative, ~120s response |

### Local Model (Requires GPU)
Runs on your V100 GPU. No API key needed, fully offline.

| Model | Ollama Name | VRAM Usage | Notes |
|---|---|---|---|
| **DeepSeek R1 8B** | `deepseek-r1:8b` | ~6GB | Fast (~15s), shorter responses |

## Getting Your Ollama API Key

1. Go to [ollama.com](https://ollama.com) and sign in (or create an account)
2. Navigate to **Settings → API Keys** (https://ollama.com/settings/keys)
3. Click **Create New Key**
4. Copy the key and set it as an environment variable:
   ```bash
   export OLLAMA_API_KEY="your-key-here"
   ```

## Usage After Setup

### Start CODEIT
```bash
cd ~/OpenHands
bash start.sh
# Open http://YOUR-SERVER-IP:8080 in your browser
```

### Switch Models
```bash
bash switch_model.sh kimi-k2.5    # Cloud (default, best quality)
bash switch_model.sh glm-5        # Cloud (alternative)
bash switch_model.sh deepseek-r1  # Local GPU
# Then restart: bash start.sh
```

### Run Direct LLM Tests
```bash
source .venv/bin/activate
python tests/llm-evaluation/direct_llm_test.py --all
python tests/llm-evaluation/direct_llm_test.py --model kimi-k2.5
```

### Run OpenHands E2E Tests
```bash
source .venv/bin/activate
bash tests/llm-evaluation/run_all_models.sh
```

### Use DeepSeek R1 Locally
```bash
# Start Ollama server (if not already running)
ollama serve &

# Verify model is available
ollama list

# Switch to local model
bash switch_model.sh deepseek-r1
bash start.sh
```

## Troubleshooting

### "OLLAMA_API_KEY not set"
```bash
export OLLAMA_API_KEY="your-key-here"
# Or add to ~/.bashrc for persistence:
echo 'export OLLAMA_API_KEY="your-key-here"' >> ~/.bashrc
```

### "Docker permission denied"
```bash
sudo usermod -aG docker $USER
# Log out and back in, then retry
```

### "Ollama connection refused" (local model)
```bash
ollama serve &   # Start Ollama server
sleep 3
ollama list      # Verify models are loaded
```

### Frontend not loading
```bash
cd ~/OpenHands/codeit-ui
npm run build    # Rebuild frontend
npx serve dist -l 8080 --cors  # Start manually
```

### Backend not responding
```bash
tail -f /tmp/openhands.log  # Check backend logs
# Common fix: kill and restart
pkill -f "python.*openhands"
cd ~/OpenHands && bash start.sh
```

## Architecture

```
Your Server (V100 16GB)
├── OpenHands Backend (port 3000)
│   ├── Agent controller
│   ├── Docker sandbox runtime
│   └── LLM connector
├── CODEIT Frontend (port 8080)
│   └── React app (Vite build)
├── Ollama (port 11434) — optional, for local models
│   └── DeepSeek R1 8B
└── Cloud API calls
    ├── https://ollama.com/v1 → Kimi2.5
    └── https://ollama.com/v1 → GLM5
```
