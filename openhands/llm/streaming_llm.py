# IMPORTANT: LEGACY V0 CODE - Deprecated since version 1.0.0, scheduled for removal April 1, 2026
# This file is part of the legacy (V0) implementation of OpenHands and will be removed soon as we complete the migration to V1.
# OpenHands V1 uses the Software Agent SDK for the agentic core and runs a new application server. Please refer to:
#   - V1 agentic core (SDK): https://github.com/OpenHands/software-agent-sdk
#   - V1 application server (in this repo): openhands/app_server/
# Unless you are working on deprecation, please avoid extending this legacy file and consult the V1 codepaths above.
# Tag: Legacy-V0
import asyncio
import time
from functools import partial
from typing import Any, Callable, cast

from litellm.types.utils import ModelResponse

from openhands.core.exceptions import UserCancelledError
from openhands.core.logger import openhands_logger as logger
from openhands.core.message import Message
from openhands.llm.async_llm import LLM_RETRY_EXCEPTIONS, AsyncLLM
from openhands.llm.model_features import get_features


class StreamingLLM(AsyncLLM):
    """Streaming LLM class."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # ── Native Ollama streaming path (bypasses LiteLLM) ──────────
        if self.config.provider == 'ollama':
            self._setup_ollama_streaming()
        else:
            self._setup_litellm_streaming()

    def _setup_litellm_streaming(self) -> None:
        """Standard LiteLLM streaming path."""
        self._async_streaming_completion = partial(
            self._call_acompletion,
            model=self.config.model,
            api_key=self.config.api_key.get_secret_value()
            if self.config.api_key
            else None,
            base_url=self.config.base_url,
            api_version=self.config.api_version,
            custom_llm_provider=self.config.custom_llm_provider,
            max_tokens=self.config.max_output_tokens,
            timeout=self.config.timeout,
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            drop_params=self.config.drop_params,
            stream=True,
        )

        async_streaming_completion_unwrapped = self._async_streaming_completion

        @self.retry_decorator(
            num_retries=self.config.num_retries,
            retry_exceptions=LLM_RETRY_EXCEPTIONS,
            retry_min_wait=self.config.retry_min_wait,
            retry_max_wait=self.config.retry_max_wait,
            retry_multiplier=self.config.retry_multiplier,
        )
        async def async_streaming_completion_wrapper(*args: Any, **kwargs: Any) -> Any:
            messages: list[dict[str, Any]] | dict[str, Any] = []

            if len(args) > 1:
                messages = args[1] if len(args) > 1 else args[0]
                kwargs['messages'] = messages
                args = args[2:]
            elif 'messages' in kwargs:
                messages = kwargs['messages']

            messages = messages if isinstance(messages, list) else [messages]

            if not messages:
                raise ValueError(
                    'The messages list is empty. At least one message is required.'
                )

            if (
                get_features(self.config.model).supports_reasoning_effort
                and self.config.reasoning_effort is not None
            ):
                kwargs['reasoning_effort'] = self.config.reasoning_effort

            logger.debug(
                f'[STREAMING-LLM] provider=litellm, model={self.config.model}, '
                f'base_url={self.config.base_url}, path=litellm_acompletion(stream=True)'
            )

            self.log_prompt(messages)

            try:
                resp = await async_streaming_completion_unwrapped(*args, **kwargs)

                async for chunk in resp:
                    if (
                        hasattr(self.config, 'on_cancel_requested_fn')
                        and self.config.on_cancel_requested_fn is not None
                        and await self.config.on_cancel_requested_fn()
                    ):
                        raise UserCancelledError(
                            'LLM request cancelled due to CANCELLED state'
                        )
                    message_back = chunk['choices'][0]['delta'].get('content', '')
                    if message_back:
                        self.log_response(message_back)
                    self._post_completion(chunk)
                    yield chunk

            except UserCancelledError:
                logger.debug('LLM request cancelled by user.')
                raise
            except Exception as e:
                logger.error(f'Completion Error occurred:\n{e}')
                raise

            finally:
                if kwargs.get('stream', False):
                    await asyncio.sleep(0.1)

        self._async_streaming_completion = async_streaming_completion_wrapper

    def _setup_ollama_streaming(self) -> None:
        """Native Ollama streaming — bypasses LiteLLM entirely.

        Converts OllamaStreamChunk objects into LiteLLM-compatible delta chunks
        so the rest of OpenHands' pipeline works without changes.
        """
        from openhands.llm.ollama_provider import (
            DEFAULT_OLLAMA_BASE_URL,
            OllamaProvider,
        )

        if self._ollama_provider is None:
            base_url = self.config.base_url or DEFAULT_OLLAMA_BASE_URL
            self._ollama_provider = OllamaProvider(base_url=base_url)

        provider = self._ollama_provider
        model_name = self.config.model
        if model_name.startswith('ollama/'):
            model_name = model_name[len('ollama/'):]

        config = self.config
        logger.info(
            f'[STREAMING-LLM] Using NATIVE Ollama streaming: model={model_name}, '
            f'base_url={provider.base_url}, client=OllamaProvider.achat_stream'
        )

        @self.retry_decorator(
            num_retries=self.config.num_retries,
            retry_exceptions=LLM_RETRY_EXCEPTIONS,
            retry_min_wait=self.config.retry_min_wait,
            retry_max_wait=self.config.retry_max_wait,
            retry_multiplier=self.config.retry_multiplier,
        )
        async def ollama_streaming_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Native Ollama streaming with retry, yielding LiteLLM-compatible chunks."""
            messages: list[dict[str, Any]] = []
            if len(args) > 1:
                messages = args[1] if len(args) > 1 else args[0]
                kwargs['messages'] = messages
                args = args[2:]
            elif 'messages' in kwargs:
                messages = kwargs['messages']

            messages = messages if isinstance(messages, list) else [messages]
            if messages and isinstance(messages[0], Message):
                messages = self.format_messages_for_llm(
                    cast(list[Message], messages)
                )

            if not messages:
                raise ValueError(
                    'The messages list is empty. At least one message is required.'
                )

            logger.debug(
                f'[STREAMING-LLM-OLLAMA] Streaming {len(messages)} messages to '
                f'{provider.base_url}/api/chat, model={model_name}'
            )
            self.log_prompt(messages)

            tools = kwargs.get('tools')
            start_time = time.time()
            chunk_count = 0

            try:
                async for ollama_chunk in provider.achat_stream(
                    model=model_name,
                    messages=messages,
                    temperature=config.temperature,
                    max_tokens=config.max_output_tokens,
                    top_p=config.top_p if config.top_p is not None else None,
                    top_k=int(config.top_k) if config.top_k is not None else None,
                    tools=tools,
                    seed=config.seed,
                ):
                    if (
                        hasattr(config, 'on_cancel_requested_fn')
                        and config.on_cancel_requested_fn is not None
                        and await config.on_cancel_requested_fn()
                    ):
                        raise UserCancelledError(
                            'LLM request cancelled due to CANCELLED state'
                        )

                    chunk_count += 1

                    # Convert OllamaStreamChunk to LiteLLM-compatible delta chunk
                    delta_dict: dict[str, Any] = {
                        'role': 'assistant',
                        'content': ollama_chunk.message.content,
                    }
                    if ollama_chunk.message.tool_calls:
                        delta_dict['tool_calls'] = ollama_chunk.message.tool_calls

                    finish_reason = None
                    if ollama_chunk.done:
                        finish_reason = ollama_chunk.done_reason or 'stop'

                    chunk_dict = {
                        'id': f'ollama-stream-{int(start_time * 1000)}',
                        'object': 'chat.completion.chunk',
                        'created': int(start_time),
                        'model': model_name,
                        'choices': [
                            {
                                'index': 0,
                                'delta': delta_dict,
                                'finish_reason': finish_reason,
                            }
                        ],
                    }

                    if ollama_chunk.done:
                        chunk_dict['usage'] = {
                            'prompt_tokens': ollama_chunk.prompt_eval_count,
                            'completion_tokens': ollama_chunk.eval_count,
                            'total_tokens': ollama_chunk.prompt_eval_count + ollama_chunk.eval_count,
                        }

                    chunk_resp = ModelResponse(**chunk_dict, stream=True)

                    content = ollama_chunk.message.content
                    if content:
                        self.log_response(content)
                    self._post_completion(chunk_resp)

                    yield chunk_resp

                latency = time.time() - start_time
                logger.debug(
                    f'[STREAMING-LLM-OLLAMA] Stream complete: '
                    f'{chunk_count} chunks in {latency:.2f}s'
                )

            except UserCancelledError:
                logger.debug('LLM request cancelled by user.')
                raise
            except Exception as e:
                logger.error(f'[STREAMING-LLM-OLLAMA] Streaming Error: {e}')
                raise

            finally:
                await asyncio.sleep(0.1)

        self._async_streaming_completion = ollama_streaming_wrapper

    @property
    def async_streaming_completion(self) -> Callable:
        """Decorator for the async litellm acompletion function with streaming."""
        return self._async_streaming_completion
