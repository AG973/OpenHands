"""CODEIT model discovery — lists available LLM models from Ollama + cloud presets."""

import os
import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from openhands.core.logger import openhands_logger as logger

router = APIRouter(prefix="/api/codeit", tags=["codeit-models"])

# Cloud API model presets — users still need to provide their own API keys
CLOUD_PRESETS = [
    # OpenAI
    {"id": "openai/gpt-4o", "name": "GPT-4o", "provider": "OpenAI", "base_url": "https://api.openai.com/v1", "requires_key": True},
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI", "base_url": "https://api.openai.com/v1", "requires_key": True},
    {"id": "openai/gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "OpenAI", "base_url": "https://api.openai.com/v1", "requires_key": True},
    # Anthropic
    {"id": "anthropic/claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "provider": "Anthropic", "base_url": "https://api.anthropic.com", "requires_key": True},
    {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Anthropic", "base_url": "https://api.anthropic.com", "requires_key": True},
    # Google
    {"id": "gemini/gemini-2.0-flash", "name": "Gemini 2.0 Flash", "provider": "Google", "base_url": "https://generativelanguage.googleapis.com/v1beta", "requires_key": True},
    {"id": "gemini/gemini-1.5-pro", "name": "Gemini 1.5 Pro", "provider": "Google", "base_url": "https://generativelanguage.googleapis.com/v1beta", "requires_key": True},
    # DeepSeek
    {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat (V3)", "provider": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "requires_key": True},
    {"id": "deepseek/deepseek-coder", "name": "DeepSeek Coder", "provider": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "requires_key": True},
    # Moonshot / Kimi
    {"id": "openai/moonshot-v1-128k", "name": "Kimi Moonshot V1 128K", "provider": "Moonshot", "base_url": "https://api.moonshot.cn/v1", "requires_key": True},
    # GLM / Zhipu
    {"id": "openai/glm-4-flash", "name": "GLM-4 Flash", "provider": "Zhipu AI", "base_url": "https://open.bigmodel.cn/api/paas/v4", "requires_key": True},
]


def _get_ollama_url() -> str:
    """Resolve the Ollama API base URL."""
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


async def _fetch_ollama_models() -> list[dict]:
    """Query Ollama /api/tags for locally available models."""
    url = f"{_get_ollama_url()}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.debug(f"Ollama returned {resp.status_code} from {url}")
                return []
            data = resp.json()
            models = []
            for m in data.get("models", []):
                name = m.get("name", "")
                size_bytes = m.get("size", 0)
                size_gb = round(size_bytes / (1024 ** 3), 1) if size_bytes else None
                models.append({
                    "id": f"ollama/{name}",
                    "name": name,
                    "provider": "Ollama (Local)",
                    "base_url": f"{_get_ollama_url()}/v1",
                    "requires_key": False,
                    "size_gb": size_gb,
                    "details": m.get("details", {}),
                })
            return models
    except Exception as e:
        logger.debug(f"Could not reach Ollama at {url}: {e}")
        return []


@router.get("/models")
async def list_models() -> JSONResponse:
    """Return all available models grouped by provider."""
    ollama_models = await _fetch_ollama_models()
    ollama_available = len(ollama_models) > 0

    # Group models by provider
    groups: dict[str, list[dict]] = {}
    for m in ollama_models:
        groups.setdefault(m["provider"], []).append(m)
    for m in CLOUD_PRESETS:
        groups.setdefault(m["provider"], []).append(m)

    return JSONResponse(content={
        "ollama_available": ollama_available,
        "ollama_url": _get_ollama_url(),
        "groups": groups,
        "all_models": ollama_models + CLOUD_PRESETS,
    })
