"""Ollama instance and model discovery — auto-detect running Ollama instances.

Scans common Ollama endpoints to find running instances and enumerate
available models. Ported from OpenClaw's provider-ollama-setup patterns.
"""

import logging
import socket
from dataclasses import dataclass, field

from openhands.core.logger import openhands_logger as logger
from openhands.llm.ollama_provider import (
    DEFAULT_OLLAMA_BASE_URL,
    OllamaError,
    OllamaModelInfo,
    OllamaProvider,
)

# Common Ollama endpoints to scan
OLLAMA_SCAN_ENDPOINTS = [
    'http://localhost:11434',
    'http://127.0.0.1:11434',
    'http://host.docker.internal:11434',  # Docker host access
    'http://ollama:11434',  # Docker compose service name
]

# Known model capabilities for selecting the best model
MODEL_CAPABILITIES: dict[str, dict[str, bool]] = {
    'deepseek-r1': {'coding': True, 'reasoning': False, 'general': True},
    'deepseek-coder': {'coding': True, 'reasoning': False, 'general': False},
    'mistral': {'coding': True, 'reasoning': True, 'general': True},
    'mixtral': {'coding': True, 'reasoning': True, 'general': True},
    'qwen3': {'coding': True, 'reasoning': True, 'general': True},
    'qwen2.5-coder': {'coding': True, 'reasoning': False, 'general': False},
    'codellama': {'coding': True, 'reasoning': False, 'general': False},
    'llama3': {'coding': True, 'reasoning': True, 'general': True},
    'llama3.1': {'coding': True, 'reasoning': True, 'general': True},
    'llama3.2': {'coding': True, 'reasoning': True, 'general': True},
    'phi3': {'coding': True, 'reasoning': True, 'general': True},
    'gemma2': {'coding': True, 'reasoning': True, 'general': True},
    'command-r': {'coding': False, 'reasoning': True, 'general': True},
    'starcoder2': {'coding': True, 'reasoning': False, 'general': False},
    'devstral': {'coding': True, 'reasoning': False, 'general': False},
}

# Model quality ranking for auto-selection (higher = better for coding tasks)
MODEL_CODING_RANK: dict[str, int] = {
    'qwen3': 95,
    'deepseek-r1': 90,
    'devstral': 88,
    'mistral': 85,
    'mixtral': 85,
    'qwen2.5-coder': 83,
    'llama3.1': 80,
    'llama3.2': 80,
    'llama3': 78,
    'phi3': 75,
    'gemma2': 73,
    'deepseek-coder': 70,
    'codellama': 65,
    'starcoder2': 60,
}

# Known embedding models
EMBEDDING_MODELS = [
    'nomic-embed-text',
    'mxbai-embed-large',
    'all-minilm',
    'snowflake-arctic-embed',
    'bge-large',
    'bge-m3',
]


@dataclass
class OllamaInstance:
    """A discovered Ollama instance."""

    base_url: str
    is_available: bool = False
    models: list[OllamaModelInfo] = field(default_factory=list)
    version: str = ''
    error: str = ''


@dataclass
class OllamaDiscoveryResult:
    """Result of Ollama discovery scan."""

    instances: list[OllamaInstance] = field(default_factory=list)
    best_instance: OllamaInstance | None = None
    best_coding_model: str | None = None
    best_embedding_model: str | None = None
    has_ollama: bool = False


def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Quick TCP check if a port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except (socket.error, OSError):
        return False


def _extract_host_port(url: str) -> tuple[str, int]:
    """Extract host and port from a URL."""
    # Remove protocol
    stripped = url.replace('http://', '').replace('https://', '')
    # Split host:port
    if ':' in stripped:
        host, port_str = stripped.rsplit(':', 1)
        try:
            return host, int(port_str)
        except ValueError:
            return host, 11434
    return stripped, 11434


def _get_model_family(model_name: str) -> str:
    """Extract the model family from a full model name.

    Examples:
        'deepseek-r1:14b' -> 'deepseek-r1'
        'mistral:latest' -> 'mistral'
        'qwen3:14b-q4_K_M' -> 'qwen3'
    """
    # Remove tag/version
    base = model_name.split(':')[0]
    return base


def _rank_model_for_coding(model: OllamaModelInfo) -> int:
    """Rank a model for coding tasks. Higher = better."""
    family = _get_model_family(model.name)

    # Check if we have a known ranking
    for known_family, rank in MODEL_CODING_RANK.items():
        if family.startswith(known_family) or known_family in family:
            # Bonus for larger parameter sizes
            size_bonus = 0
            param_size = model.parameter_size.lower()
            if '70b' in param_size or '72b' in param_size:
                size_bonus = 15
            elif '34b' in param_size or '32b' in param_size:
                size_bonus = 10
            elif '14b' in param_size or '13b' in param_size:
                size_bonus = 5
            elif '7b' in param_size or '8b' in param_size:
                size_bonus = 2
            return rank + size_bonus

    # Unknown model — give it a base score
    return 50


def discover_ollama(
    extra_endpoints: list[str] | None = None,
    timeout: float = 2.0,
) -> OllamaDiscoveryResult:
    """Discover running Ollama instances and available models.

    Scans common endpoints (localhost, Docker host, etc.) and returns
    information about available instances and models.

    Args:
        extra_endpoints: Additional URLs to scan beyond the defaults
        timeout: Connection timeout per endpoint in seconds

    Returns:
        OllamaDiscoveryResult with discovered instances and recommendations
    """
    result = OllamaDiscoveryResult()
    endpoints = list(OLLAMA_SCAN_ENDPOINTS)
    if extra_endpoints:
        endpoints.extend(extra_endpoints)

    # Deduplicate endpoints
    seen_urls: set[str] = set()
    unique_endpoints: list[str] = []
    for ep in endpoints:
        normalized = ep.rstrip('/')
        if normalized not in seen_urls:
            seen_urls.add(normalized)
            unique_endpoints.append(normalized)

    for endpoint in unique_endpoints:
        instance = _probe_endpoint(endpoint, timeout)
        result.instances.append(instance)

        if instance.is_available:
            result.has_ollama = True
            # Track best instance (prefer one with most models)
            if result.best_instance is None or len(instance.models) > len(
                result.best_instance.models
            ):
                result.best_instance = instance

    # Find best coding model across all instances
    if result.has_ollama:
        all_models: list[OllamaModelInfo] = []
        for inst in result.instances:
            if inst.is_available:
                all_models.extend(inst.models)

        # Find best coding model
        coding_models = [
            m for m in all_models if m.name not in EMBEDDING_MODELS and not _is_embedding_model(m.name)
        ]
        if coding_models:
            best = max(coding_models, key=_rank_model_for_coding)
            result.best_coding_model = best.name

        # Find best embedding model
        embed_models = [m for m in all_models if _is_embedding_model(m.name)]
        if embed_models:
            result.best_embedding_model = embed_models[0].name

    return result


def _is_embedding_model(name: str) -> bool:
    """Check if a model name is likely an embedding model."""
    lower = name.lower()
    for known in EMBEDDING_MODELS:
        if known in lower:
            return True
    return 'embed' in lower or 'bge' in lower


def _probe_endpoint(endpoint: str, timeout: float) -> OllamaInstance:
    """Probe a single Ollama endpoint."""
    instance = OllamaInstance(base_url=endpoint)

    # Quick port check first
    host, port = _extract_host_port(endpoint)
    if not _is_port_open(host, port, timeout=timeout):
        instance.error = f'Port {port} not open on {host}'
        return instance

    # Try full API check
    try:
        provider = OllamaProvider(
            base_url=endpoint,
            connect_timeout=timeout,
            read_timeout=timeout * 2,
        )

        if not provider.is_available():
            instance.error = 'Ollama not responding at endpoint'
            provider.close()
            return instance

        instance.is_available = True
        instance.models = provider.list_models()
        provider.close()

        logger.info(
            f'Found Ollama at {endpoint} with {len(instance.models)} models: '
            f'{[m.name for m in instance.models]}'
        )

    except OllamaError as e:
        instance.error = str(e)
        logger.debug(f'Ollama probe failed at {endpoint}: {e}')
    except Exception as e:
        instance.error = f'Unexpected error: {e}'
        logger.debug(f'Ollama probe failed at {endpoint}: {e}')

    return instance


def select_best_model(
    models: list[OllamaModelInfo],
    task: str = 'coding',
) -> str | None:
    """Select the best available model for a given task.

    Args:
        models: List of available models
        task: Task type ('coding', 'general', 'embedding')

    Returns:
        Model name string or None if no suitable model found
    """
    if not models:
        return None

    if task == 'embedding':
        for model in models:
            if _is_embedding_model(model.name):
                return model.name
        return None

    # Filter out embedding models for non-embedding tasks
    task_models = [m for m in models if not _is_embedding_model(m.name)]
    if not task_models:
        return None

    if task == 'coding':
        best = max(task_models, key=_rank_model_for_coding)
        return best.name

    # For 'general' task, prefer models with general capability
    for model in task_models:
        family = _get_model_family(model.name)
        caps = MODEL_CAPABILITIES.get(family, {})
        if caps.get('general', False):
            return model.name

    # Fallback to any available model
    return task_models[0].name if task_models else None
