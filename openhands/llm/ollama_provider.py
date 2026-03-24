"""Native Ollama LLM provider — bypasses LiteLLM for direct local model communication.

This module provides a direct HTTP client for Ollama's API, eliminating the need
for LiteLLM as an intermediary when using local models. It supports:
- Chat completions via /api/chat
- Text generation via /api/generate
- Model listing via /api/tags
- Model pulling via /api/pull
- Embedding generation via /api/embeddings
- Streaming responses
- Function/tool calling (for models that support it)

Ported from OpenClaw's provider-ollama patterns to Python.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator

import httpx

from openhands.core.logger import openhands_logger as logger

# Default Ollama endpoint
DEFAULT_OLLAMA_BASE_URL = 'http://localhost:11434'

# Timeout configuration
OLLAMA_CONNECT_TIMEOUT = 5.0
OLLAMA_READ_TIMEOUT = 300.0  # 5 minutes for generation
OLLAMA_PULL_TIMEOUT = 3600.0  # 1 hour for model pulls


class OllamaErrorType(Enum):
    """Classification of Ollama errors for retry/recovery decisions."""

    CONNECTION_REFUSED = 'connection_refused'
    TIMEOUT = 'timeout'
    MODEL_NOT_FOUND = 'model_not_found'
    MODEL_LOADING = 'model_loading'
    OUT_OF_MEMORY = 'out_of_memory'
    INVALID_REQUEST = 'invalid_request'
    SERVER_ERROR = 'server_error'
    UNKNOWN = 'unknown'


class OllamaError(Exception):
    """Structured error from Ollama operations."""

    def __init__(
        self,
        message: str,
        error_type: OllamaErrorType = OllamaErrorType.UNKNOWN,
        status_code: int | None = None,
        is_transient: bool = False,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
        self.is_transient = is_transient


@dataclass
class OllamaModelInfo:
    """Information about an available Ollama model."""

    name: str
    size: int = 0
    digest: str = ''
    modified_at: str = ''
    parameter_size: str = ''
    quantization_level: str = ''
    family: str = ''
    families: list[str] = field(default_factory=list)


@dataclass
class OllamaChatMessage:
    """A single message in an Ollama chat conversation."""

    role: str
    content: str
    images: list[str] | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class OllamaChatResponse:
    """Response from Ollama /api/chat endpoint."""

    model: str
    message: OllamaChatMessage
    done: bool
    total_duration: int = 0
    load_duration: int = 0
    prompt_eval_count: int = 0
    prompt_eval_duration: int = 0
    eval_count: int = 0
    eval_duration: int = 0
    done_reason: str = ''

    @property
    def tokens_per_second(self) -> float:
        """Calculate generation speed in tokens/second."""
        if self.eval_duration > 0:
            return self.eval_count / (self.eval_duration / 1e9)
        return 0.0


@dataclass
class OllamaStreamChunk:
    """A single chunk from a streaming Ollama response."""

    model: str
    message: OllamaChatMessage
    done: bool
    total_duration: int = 0
    load_duration: int = 0
    prompt_eval_count: int = 0
    prompt_eval_duration: int = 0
    eval_count: int = 0
    eval_duration: int = 0
    done_reason: str = ''


def _classify_error(exc: Exception) -> OllamaError:
    """Classify an exception into an OllamaError with proper error type."""
    if isinstance(exc, httpx.ConnectError):
        return OllamaError(
            f'Cannot connect to Ollama. Is it running? Error: {exc}',
            error_type=OllamaErrorType.CONNECTION_REFUSED,
            is_transient=True,
        )
    if isinstance(exc, httpx.TimeoutException):
        return OllamaError(
            f'Ollama request timed out: {exc}',
            error_type=OllamaErrorType.TIMEOUT,
            is_transient=True,
        )
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        body = ''
        try:
            body = exc.response.text
        except Exception:
            pass

        if status == 404:
            return OllamaError(
                f'Model not found: {body}',
                error_type=OllamaErrorType.MODEL_NOT_FOUND,
                status_code=status,
                is_transient=False,
            )
        if status == 500 and 'out of memory' in body.lower():
            return OllamaError(
                f'Ollama out of memory: {body}',
                error_type=OllamaErrorType.OUT_OF_MEMORY,
                status_code=status,
                is_transient=False,
            )
        if status == 500:
            return OllamaError(
                f'Ollama server error: {body}',
                error_type=OllamaErrorType.SERVER_ERROR,
                status_code=status,
                is_transient=True,
            )
        return OllamaError(
            f'Ollama HTTP {status}: {body}',
            error_type=OllamaErrorType.INVALID_REQUEST,
            status_code=status,
            is_transient=False,
        )
    return OllamaError(
        f'Unexpected error communicating with Ollama: {exc}',
        error_type=OllamaErrorType.UNKNOWN,
        is_transient=False,
    )


class OllamaProvider:
    """Direct Ollama API client, bypassing LiteLLM entirely.

    This provider communicates directly with Ollama's HTTP API for:
    - Chat completions (/api/chat)
    - Model management (/api/tags, /api/pull)
    - Embeddings (/api/embeddings)
    """

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        connect_timeout: float = OLLAMA_CONNECT_TIMEOUT,
        read_timeout: float = OLLAMA_READ_TIMEOUT,
    ):
        self.base_url = base_url.rstrip('/')
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(
                connect=connect_timeout,
                read=read_timeout,
                write=30.0,
                pool=30.0,
            ),
        )
        self._async_client: httpx.AsyncClient | None = None

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(
                    connect=OLLAMA_CONNECT_TIMEOUT,
                    read=OLLAMA_READ_TIMEOUT,
                    write=30.0,
                    pool=30.0,
                ),
            )
        return self._async_client

    def close(self) -> None:
        """Close HTTP clients and release resources."""
        self._client.close()
        if self._async_client is not None and not self._async_client.is_closed:
            # For sync close, we can't await — caller should use aclose() in async context
            pass

    async def aclose(self) -> None:
        """Async close of HTTP clients."""
        self._client.close()
        if self._async_client is not None and not self._async_client.is_closed:
            await self._async_client.aclose()

    # ── Health Check ──────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if Ollama is running and reachable."""
        try:
            resp = self._client.get('/')
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def ais_available(self) -> bool:
        """Async check if Ollama is running and reachable."""
        try:
            client = self._get_async_client()
            resp = await client.get('/')
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    # ── Model Discovery ───────────────────────────────────────────────

    def list_models(self) -> list[OllamaModelInfo]:
        """List all locally available models."""
        try:
            resp = self._client.get('/api/tags')
            resp.raise_for_status()
            data = resp.json()
            models: list[OllamaModelInfo] = []
            for m in data.get('models', []):
                details = m.get('details', {})
                models.append(
                    OllamaModelInfo(
                        name=m.get('name', ''),
                        size=m.get('size', 0),
                        digest=m.get('digest', ''),
                        modified_at=m.get('modified_at', ''),
                        parameter_size=details.get('parameter_size', ''),
                        quantization_level=details.get('quantization_level', ''),
                        family=details.get('family', ''),
                        families=details.get('families', []),
                    )
                )
            return models
        except Exception as exc:
            raise _classify_error(exc) from exc

    async def alist_models(self) -> list[OllamaModelInfo]:
        """Async list all locally available models."""
        try:
            client = self._get_async_client()
            resp = await client.get('/api/tags')
            resp.raise_for_status()
            data = resp.json()
            models: list[OllamaModelInfo] = []
            for m in data.get('models', []):
                details = m.get('details', {})
                models.append(
                    OllamaModelInfo(
                        name=m.get('name', ''),
                        size=m.get('size', 0),
                        digest=m.get('digest', ''),
                        modified_at=m.get('modified_at', ''),
                        parameter_size=details.get('parameter_size', ''),
                        quantization_level=details.get('quantization_level', ''),
                        family=details.get('family', ''),
                        families=details.get('families', []),
                    )
                )
            return models
        except Exception as exc:
            raise _classify_error(exc) from exc

    def has_model(self, model_name: str) -> bool:
        """Check if a specific model is available locally."""
        try:
            models = self.list_models()
            return any(m.name == model_name or m.name.startswith(f'{model_name}:') for m in models)
        except OllamaError:
            return False

    def pull_model(self, model_name: str, stream: bool = True) -> Iterator[dict[str, Any]]:
        """Pull/download a model from the Ollama registry.

        Args:
            model_name: Model to pull (e.g., 'deepseek-r1:14b')
            stream: If True, yields progress updates

        Yields:
            Progress dictionaries with 'status', 'digest', 'total', 'completed' keys
        """
        try:
            with self._client.stream(
                'POST',
                '/api/pull',
                json={'name': model_name, 'stream': stream},
                timeout=httpx.Timeout(
                    connect=OLLAMA_CONNECT_TIMEOUT,
                    read=OLLAMA_PULL_TIMEOUT,
                    write=30.0,
                    pool=30.0,
                ),
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.strip():
                        yield json.loads(line)
        except Exception as exc:
            raise _classify_error(exc) from exc

    # ── Chat Completion ───────────────────────────────────────────────

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        format_type: str | None = None,
        seed: int | None = None,
        stop: list[str] | None = None,
    ) -> OllamaChatResponse:
        """Send a chat completion request (non-streaming).

        Args:
            model: Model name (e.g., 'deepseek-r1:14b', 'mistral', 'qwen3:14b')
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate
            top_p: Top-p sampling
            top_k: Top-k sampling
            tools: Tool/function definitions for function calling
            format_type: Response format ('json' for JSON mode)
            seed: Random seed for reproducibility
            stop: Stop sequences

        Returns:
            OllamaChatResponse with the complete response
        """
        payload = self._build_chat_payload(
            model=model,
            messages=messages,
            stream=False,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            tools=tools,
            format_type=format_type,
            seed=seed,
            stop=stop,
        )

        try:
            resp = self._client.post('/api/chat', json=payload)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_chat_response(data)
        except Exception as exc:
            raise _classify_error(exc) from exc

    async def achat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        format_type: str | None = None,
        seed: int | None = None,
        stop: list[str] | None = None,
    ) -> OllamaChatResponse:
        """Async chat completion request (non-streaming)."""
        payload = self._build_chat_payload(
            model=model,
            messages=messages,
            stream=False,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            tools=tools,
            format_type=format_type,
            seed=seed,
            stop=stop,
        )

        try:
            client = self._get_async_client()
            resp = await client.post('/api/chat', json=payload)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_chat_response(data)
        except Exception as exc:
            raise _classify_error(exc) from exc

    def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        format_type: str | None = None,
        seed: int | None = None,
        stop: list[str] | None = None,
    ) -> Iterator[OllamaStreamChunk]:
        """Send a streaming chat completion request.

        Yields:
            OllamaStreamChunk objects as they arrive
        """
        payload = self._build_chat_payload(
            model=model,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            tools=tools,
            format_type=format_type,
            seed=seed,
            stop=stop,
        )

        try:
            with self._client.stream('POST', '/api/chat', json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.strip():
                        data = json.loads(line)
                        yield self._parse_stream_chunk(data)
        except Exception as exc:
            raise _classify_error(exc) from exc

    # ── Embeddings ────────────────────────────────────────────────────

    def embed(
        self,
        model: str,
        input_text: str | list[str],
    ) -> list[list[float]]:
        """Generate embeddings for text input.

        Args:
            model: Embedding model (e.g., 'nomic-embed-text', 'mxbai-embed-large')
            input_text: Text string or list of strings to embed

        Returns:
            List of embedding vectors (one per input text)
        """
        if isinstance(input_text, str):
            input_text = [input_text]

        try:
            resp = self._client.post(
                '/api/embed',
                json={
                    'model': model,
                    'input': input_text,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get('embeddings', [])
        except Exception as exc:
            raise _classify_error(exc) from exc

    async def aembed(
        self,
        model: str,
        input_text: str | list[str],
    ) -> list[list[float]]:
        """Async generate embeddings for text input."""
        if isinstance(input_text, str):
            input_text = [input_text]

        try:
            client = self._get_async_client()
            resp = await client.post(
                '/api/embed',
                json={
                    'model': model,
                    'input': input_text,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get('embeddings', [])
        except Exception as exc:
            raise _classify_error(exc) from exc

    # ── LiteLLM-compatible Response Conversion ────────────────────────

    def to_litellm_response(
        self,
        ollama_response: OllamaChatResponse,
        model: str,
    ) -> dict[str, Any]:
        """Convert an OllamaChatResponse to a LiteLLM-compatible ModelResponse dict.

        This allows the Ollama provider to be a drop-in replacement for LiteLLM
        in OpenHands' existing LLM pipeline.
        """
        response_id = f'ollama-{int(time.time() * 1000)}'

        # Build the message dict
        message_dict: dict[str, Any] = {
            'role': ollama_response.message.role,
            'content': ollama_response.message.content,
        }
        if ollama_response.message.tool_calls:
            message_dict['tool_calls'] = ollama_response.message.tool_calls

        # Build usage info
        prompt_tokens = ollama_response.prompt_eval_count
        completion_tokens = ollama_response.eval_count
        total_tokens = prompt_tokens + completion_tokens

        return {
            'id': response_id,
            'object': 'chat.completion',
            'created': int(time.time()),
            'model': model,
            'choices': [
                {
                    'index': 0,
                    'message': message_dict,
                    'finish_reason': ollama_response.done_reason or 'stop',
                }
            ],
            'usage': {
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total_tokens,
            },
            '_ollama_metrics': {
                'total_duration_ns': ollama_response.total_duration,
                'load_duration_ns': ollama_response.load_duration,
                'prompt_eval_duration_ns': ollama_response.prompt_eval_duration,
                'eval_duration_ns': ollama_response.eval_duration,
                'tokens_per_second': ollama_response.tokens_per_second,
            },
        }

    # ── Internal Helpers ──────────────────────────────────────────────

    def _build_chat_payload(
        self,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        format_type: str | None = None,
        seed: int | None = None,
        stop: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build the JSON payload for /api/chat."""
        # Convert OpenAI-style messages to Ollama format
        ollama_messages = []
        for msg in messages:
            ollama_msg: dict[str, Any] = {
                'role': msg.get('role', 'user'),
                'content': msg.get('content', ''),
            }
            # Handle image content (multimodal)
            if isinstance(msg.get('content'), list):
                text_parts = []
                images = []
                for part in msg['content']:
                    if isinstance(part, dict):
                        if part.get('type') == 'text':
                            text_parts.append(part.get('text', ''))
                        elif part.get('type') == 'image_url':
                            url = part.get('image_url', {}).get('url', '')
                            if url.startswith('data:'):
                                # Extract base64 data
                                base64_data = url.split(',', 1)[-1] if ',' in url else url
                                images.append(base64_data)
                ollama_msg['content'] = '\n'.join(text_parts)
                if images:
                    ollama_msg['images'] = images

            # Handle tool call results
            if msg.get('role') == 'tool':
                ollama_msg['role'] = 'tool'
                if 'tool_call_id' in msg:
                    ollama_msg['tool_call_id'] = msg['tool_call_id']

            # Handle assistant messages with tool calls
            if msg.get('tool_calls'):
                ollama_msg['tool_calls'] = msg['tool_calls']

            ollama_messages.append(ollama_msg)

        payload: dict[str, Any] = {
            'model': model,
            'messages': ollama_messages,
            'stream': stream,
        }

        # Build options
        options: dict[str, Any] = {}
        if temperature is not None:
            options['temperature'] = temperature
        if max_tokens is not None:
            options['num_predict'] = max_tokens
        if top_p is not None:
            options['top_p'] = top_p
        if top_k is not None:
            options['top_k'] = top_k
        if seed is not None:
            options['seed'] = seed
        if stop is not None:
            options['stop'] = stop

        if options:
            payload['options'] = options

        # Tools (function calling)
        if tools:
            payload['tools'] = tools

        # JSON mode
        if format_type == 'json':
            payload['format'] = 'json'

        return payload

    def _parse_chat_response(self, data: dict[str, Any]) -> OllamaChatResponse:
        """Parse a complete chat response from Ollama."""
        msg_data = data.get('message', {})
        message = OllamaChatMessage(
            role=msg_data.get('role', 'assistant'),
            content=msg_data.get('content', ''),
            images=msg_data.get('images'),
            tool_calls=msg_data.get('tool_calls'),
        )
        return OllamaChatResponse(
            model=data.get('model', ''),
            message=message,
            done=data.get('done', True),
            total_duration=data.get('total_duration', 0),
            load_duration=data.get('load_duration', 0),
            prompt_eval_count=data.get('prompt_eval_count', 0),
            prompt_eval_duration=data.get('prompt_eval_duration', 0),
            eval_count=data.get('eval_count', 0),
            eval_duration=data.get('eval_duration', 0),
            done_reason=data.get('done_reason', ''),
        )

    def _parse_stream_chunk(self, data: dict[str, Any]) -> OllamaStreamChunk:
        """Parse a single streaming chunk from Ollama."""
        msg_data = data.get('message', {})
        message = OllamaChatMessage(
            role=msg_data.get('role', 'assistant'),
            content=msg_data.get('content', ''),
            images=msg_data.get('images'),
            tool_calls=msg_data.get('tool_calls'),
        )
        return OllamaStreamChunk(
            model=data.get('model', ''),
            message=message,
            done=data.get('done', False),
            total_duration=data.get('total_duration', 0),
            load_duration=data.get('load_duration', 0),
            prompt_eval_count=data.get('prompt_eval_count', 0),
            prompt_eval_duration=data.get('prompt_eval_duration', 0),
            eval_count=data.get('eval_count', 0),
            eval_duration=data.get('eval_duration', 0),
            done_reason=data.get('done_reason', ''),
        )
