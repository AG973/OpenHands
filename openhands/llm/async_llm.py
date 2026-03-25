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

from litellm import acompletion as litellm_acompletion
from litellm.types.utils import ModelResponse

from openhands.core.exceptions import UserCancelledError
from openhands.core.logger import openhands_logger as logger
from openhands.core.message import Message
from openhands.llm.llm import (
    LLM,
    LLM_RETRY_EXCEPTIONS,
)
from openhands.llm.model_features import get_features
from openhands.utils.shutdown_listener import should_continue


class AsyncLLM(LLM):
    """Asynchronous LLM class."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # ── Native Ollama async path (bypasses LiteLLM) ──────────────
        if self.config.provider == 'ollama':
            self._setup_ollama_async_completion()
        else:
            self._setup_litellm_async_completion()

    def _setup_litellm_async_completion(self) -> None:
        """Standard LiteLLM async completion path."""
        self._async_completion = partial(
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
            seed=self.config.seed,
        )

        async_completion_unwrapped = self._async_completion

        @self.retry_decorator(
            num_retries=self.config.num_retries,
            retry_exceptions=LLM_RETRY_EXCEPTIONS,
            retry_min_wait=self.config.retry_min_wait,
            retry_max_wait=self.config.retry_max_wait,
            retry_multiplier=self.config.retry_multiplier,
        )
        async def async_completion_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper for the litellm acompletion function that adds logging and cost tracking."""
            messages: list[dict[str, Any]] | dict[str, Any] = []

            if len(args) > 1:
                messages = args[1] if len(args) > 1 else args[0]
                kwargs['messages'] = messages
                args = args[2:]
            elif 'messages' in kwargs:
                messages = kwargs['messages']

            if (
                get_features(self.config.model).supports_reasoning_effort
                and self.config.reasoning_effort is not None
            ):
                kwargs['reasoning_effort'] = self.config.reasoning_effort

            messages = messages if isinstance(messages, list) else [messages]

            if not messages:
                raise ValueError(
                    'The messages list is empty. At least one message is required.'
                )

            logger.debug(
                f'[ASYNC-LLM] provider=litellm, model={self.config.model}, '
                f'base_url={self.config.base_url}, path=litellm_acompletion'
            )

            self.log_prompt(messages)

            async def check_stopped() -> None:
                while should_continue():
                    if (
                        hasattr(self.config, 'on_cancel_requested_fn')
                        and self.config.on_cancel_requested_fn is not None
                        and await self.config.on_cancel_requested_fn()
                    ):
                        return
                    await asyncio.sleep(0.1)

            stop_check_task = asyncio.create_task(check_stopped())

            try:
                resp = await async_completion_unwrapped(*args, **kwargs)

                message_back = resp['choices'][0]['message']['content']
                self.log_response(message_back)
                self._post_completion(resp)
                return resp

            except UserCancelledError:
                logger.debug('LLM request cancelled by user.')
                raise
            except Exception as e:
                logger.error(f'Completion Error occurred:\n{e}')
                raise

            finally:
                await asyncio.sleep(0.1)
                stop_check_task.cancel()
                try:
                    await stop_check_task
                except asyncio.CancelledError:
                    pass

        self._async_completion = async_completion_wrapper

    def _setup_ollama_async_completion(self) -> None:
        """Native Ollama async completion — bypasses LiteLLM entirely."""
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
            f'[ASYNC-LLM] Using NATIVE Ollama async path: model={model_name}, '
            f'base_url={provider.base_url}, client=OllamaProvider.achat'
        )

        @self.retry_decorator(
            num_retries=self.config.num_retries,
            retry_exceptions=LLM_RETRY_EXCEPTIONS,
            retry_min_wait=self.config.retry_min_wait,
            retry_max_wait=self.config.retry_max_wait,
            retry_multiplier=self.config.retry_multiplier,
        )
        async def ollama_async_wrapper(*args: Any, **kwargs: Any) -> ModelResponse:
            """Native Ollama async completion with retry."""
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
                f'[ASYNC-LLM-OLLAMA] Sending {len(messages)} messages to '
                f'{provider.base_url}/api/chat, model={model_name}'
            )
            self.log_prompt(messages)

            tools = kwargs.get('tools')

            async def check_stopped() -> None:
                while should_continue():
                    if (
                        hasattr(config, 'on_cancel_requested_fn')
                        and config.on_cancel_requested_fn is not None
                        and await config.on_cancel_requested_fn()
                    ):
                        return
                    await asyncio.sleep(0.1)

            stop_check_task = asyncio.create_task(check_stopped())

            try:
                start_time = time.time()
                ollama_resp = await provider.achat(
                    model=model_name,
                    messages=messages,
                    temperature=config.temperature,
                    max_tokens=config.max_output_tokens,
                    top_p=config.top_p if config.top_p is not None else None,
                    top_k=int(config.top_k) if config.top_k is not None else None,
                    tools=tools,
                    seed=config.seed,
                )
                latency = time.time() - start_time

                resp_dict = provider.to_litellm_response(ollama_resp, model_name)
                resp = ModelResponse(**resp_dict)

                response_id = resp.get('id', 'unknown')
                self.metrics.add_response_latency(latency, response_id)

                message_back = resp['choices'][0]['message']['content']
                self.log_response(resp)
                self._post_completion(resp)

                logger.debug(
                    f'[ASYNC-LLM-OLLAMA] Response received: '
                    f'latency={latency:.2f}s, tokens={ollama_resp.eval_count}, '
                    f'speed={ollama_resp.tokens_per_second:.1f} tok/s'
                )

                return resp

            except UserCancelledError:
                logger.debug('LLM request cancelled by user.')
                raise
            except Exception as e:
                logger.error(f'[ASYNC-LLM-OLLAMA] Completion Error: {e}')
                raise

            finally:
                await asyncio.sleep(0.1)
                stop_check_task.cancel()
                try:
                    await stop_check_task
                except asyncio.CancelledError:
                    pass

        self._async_completion = ollama_async_wrapper

    async def _call_acompletion(self, *args: Any, **kwargs: Any) -> Any:
        """Wrapper for the litellm acompletion function."""
        return await litellm_acompletion(*args, **kwargs)

    @property
    def async_completion(self) -> Callable:
        """Decorator for the async litellm acompletion function."""
        return self._async_completion
