"""Error classification system — categorize errors as transient vs permanent.

Ported from OpenClaw's infra/errors.ts patterns. Provides structured error
classification for retry/recovery decisions throughout the agent lifecycle.

Per OPERATING_RULES.md RULE 5: No missing error handling — classify transient vs permanent errors.
Per OPERATING_RULES.md RULE 15: NO silent failures — every exception must be logged, DLQ'd, or re-raised.
"""

import re
import traceback
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class ErrorSeverity(Enum):
    """How severe is this error?"""

    LOW = 'low'  # Informational, operation may still succeed
    MEDIUM = 'medium'  # Operation failed but system is healthy
    HIGH = 'high'  # System component degraded
    CRITICAL = 'critical'  # System integrity at risk


class ErrorCategory(Enum):
    """High-level error category."""

    LLM = 'llm'
    RUNTIME = 'runtime'
    NETWORK = 'network'
    AUTHENTICATION = 'authentication'
    RESOURCE = 'resource'
    VALIDATION = 'validation'
    PLUGIN = 'plugin'
    MEMORY = 'memory'
    AGENT = 'agent'
    UNKNOWN = 'unknown'


class ErrorClassification(Enum):
    """Specific error classification for retry/recovery decisions."""

    # Transient errors — should retry with backoff
    TRANSIENT_RATE_LIMIT = 'transient_rate_limit'
    TRANSIENT_TIMEOUT = 'transient_timeout'
    TRANSIENT_UNAVAILABLE = 'transient_unavailable'
    TRANSIENT_CONNECTION = 'transient_connection'
    TRANSIENT_SERVER_ERROR = 'transient_server_error'
    TRANSIENT_OVERLOADED = 'transient_overloaded'

    # Permanent errors — should NOT retry, abort or escalate
    PERMANENT_BAD_REQUEST = 'permanent_bad_request'
    PERMANENT_AUTH = 'permanent_auth'
    PERMANENT_NOT_FOUND = 'permanent_not_found'
    PERMANENT_SCHEMA = 'permanent_schema'
    PERMANENT_CONTENT_POLICY = 'permanent_content_policy'
    PERMANENT_CONTEXT_LENGTH = 'permanent_context_length'
    PERMANENT_OUT_OF_CREDITS = 'permanent_out_of_credits'
    PERMANENT_MODEL_NOT_FOUND = 'permanent_model_not_found'
    PERMANENT_INSUFFICIENT_RESOURCES = 'permanent_insufficient_resources'

    # Agent-level errors
    AGENT_STUCK = 'agent_stuck'
    AGENT_MAX_ITERATIONS = 'agent_max_iterations'
    AGENT_INVALID_ACTION = 'agent_invalid_action'

    # Unknown — needs manual triage
    UNKNOWN = 'unknown'


class ClassifiedError:
    """An error with classification metadata for retry/recovery decisions."""

    def __init__(
        self,
        original_error: Exception,
        classification: ErrorClassification,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        is_transient: bool = False,
        should_retry: bool = False,
        max_retries: int = 0,
        suggested_wait_ms: int = 0,
        context: dict[str, Any] | None = None,
        redacted_message: str = '',
    ):
        self.original_error = original_error
        self.classification = classification
        self.category = category
        self.severity = severity
        self.is_transient = is_transient
        self.should_retry = should_retry
        self.max_retries = max_retries
        self.suggested_wait_ms = suggested_wait_ms
        self.context = context or {}
        self.redacted_message = redacted_message or _redact_sensitive(str(original_error))

    def __str__(self) -> str:
        return (
            f'ClassifiedError('
            f'classification={self.classification.value}, '
            f'category={self.category.value}, '
            f'severity={self.severity.value}, '
            f'transient={self.is_transient}, '
            f'retry={self.should_retry}, '
            f'message={self.redacted_message!r}'
            f')'
        )

    def __repr__(self) -> str:
        return str(self)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for logging/DLQ."""
        return {
            'classification': self.classification.value,
            'category': self.category.value,
            'severity': self.severity.value,
            'is_transient': self.is_transient,
            'should_retry': self.should_retry,
            'max_retries': self.max_retries,
            'suggested_wait_ms': self.suggested_wait_ms,
            'redacted_message': self.redacted_message,
            'error_type': type(self.original_error).__name__,
            'context': self.context,
        }


# ── Sensitive text redaction ──────────────────────────────────────────

# Patterns that might contain secrets/tokens
_SENSITIVE_PATTERNS = [
    re.compile(r'(api[_-]?key|token|secret|password|authorization|bearer)\s*[=:]\s*\S+', re.IGNORECASE),
    re.compile(r'sk-[a-zA-Z0-9]{20,}'),  # OpenAI-style keys
    re.compile(r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+'),  # JWT tokens
]


def _redact_sensitive(text: str) -> str:
    """Redact potentially sensitive information from error messages."""
    result = text
    for pattern in _SENSITIVE_PATTERNS:
        result = pattern.sub('[REDACTED]', result)
    return result


# ── Error classification logic ────────────────────────────────────────

def classify_error(exc: Exception) -> ClassifiedError:
    """Classify an exception into a structured ClassifiedError.

    This is the main entry point for error classification. It examines
    the exception type, message, and any nested causes to determine
    the appropriate classification and recovery strategy.

    Args:
        exc: The exception to classify

    Returns:
        ClassifiedError with classification, retry strategy, etc.
    """
    # Try specific classifiers in order
    classified = (
        _classify_litellm_error(exc)
        or _classify_http_error(exc)
        or _classify_connection_error(exc)
        or _classify_ollama_error(exc)
        or _classify_agent_error(exc)
        or _classify_runtime_error(exc)
        or _classify_by_message(exc)
    )

    if classified is not None:
        return classified

    # Fallback: unknown error
    return ClassifiedError(
        original_error=exc,
        classification=ErrorClassification.UNKNOWN,
        category=ErrorCategory.UNKNOWN,
        severity=ErrorSeverity.MEDIUM,
        is_transient=False,
        should_retry=False,
    )


def _classify_litellm_error(exc: Exception) -> ClassifiedError | None:
    """Classify LiteLLM-specific exceptions."""
    exc_type = type(exc).__name__
    exc_module = type(exc).__module__ or ''

    if 'litellm' not in exc_module:
        return None

    msg = str(exc).lower()

    if exc_type == 'RateLimitError' or 'rate_limit' in msg or '429' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_RATE_LIMIT,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.LOW,
            is_transient=True,
            should_retry=True,
            max_retries=5,
            suggested_wait_ms=8000,
        )

    if exc_type == 'AuthenticationError' or '401' in msg or '403' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.PERMANENT_AUTH,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            is_transient=False,
            should_retry=False,
        )

    if exc_type == 'APIConnectionError' or 'connection' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_CONNECTION,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            is_transient=True,
            should_retry=True,
            max_retries=3,
            suggested_wait_ms=5000,
        )

    if exc_type in ('ServiceUnavailableError', 'BadGatewayError') or '502' in msg or '503' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_UNAVAILABLE,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.MEDIUM,
            is_transient=True,
            should_retry=True,
            max_retries=3,
            suggested_wait_ms=10000,
        )

    if exc_type == 'Timeout' or 'timeout' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_TIMEOUT,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.LOW,
            is_transient=True,
            should_retry=True,
            max_retries=3,
            suggested_wait_ms=5000,
        )

    if exc_type == 'InternalServerError' or '500' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_SERVER_ERROR,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.MEDIUM,
            is_transient=True,
            should_retry=True,
            max_retries=2,
            suggested_wait_ms=15000,
        )

    if exc_type == 'ContentPolicyViolationError' or 'content_policy' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.PERMANENT_CONTENT_POLICY,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.MEDIUM,
            is_transient=False,
            should_retry=False,
        )

    if 'context_length' in msg or 'context window' in msg or re.search(r'max.*token', msg):
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.PERMANENT_CONTEXT_LENGTH,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.MEDIUM,
            is_transient=False,
            should_retry=False,
        )

    if 'exceededbudget' in msg or 'out of credits' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.PERMANENT_OUT_OF_CREDITS,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.HIGH,
            is_transient=False,
            should_retry=False,
        )

    if exc_type == 'BadRequestError' or '400' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.PERMANENT_BAD_REQUEST,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.MEDIUM,
            is_transient=False,
            should_retry=False,
        )

    if exc_type == 'NotFoundError' or '404' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.PERMANENT_MODEL_NOT_FOUND,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.HIGH,
            is_transient=False,
            should_retry=False,
        )

    return None


def _classify_http_error(exc: Exception) -> ClassifiedError | None:
    """Classify HTTP-related errors."""
    exc_type = type(exc).__name__
    if 'httpx' not in (type(exc).__module__ or '') and exc_type not in (
        'HTTPStatusError',
        'ConnectError',
        'TimeoutException',
        'ReadTimeout',
        'WriteTimeout',
        'PoolTimeout',
    ):
        return None

    msg = str(exc).lower()

    if 'timeout' in exc_type.lower() or 'timeout' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_TIMEOUT,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.LOW,
            is_transient=True,
            should_retry=True,
            max_retries=3,
            suggested_wait_ms=5000,
        )

    if 'connect' in exc_type.lower() or 'connection' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_CONNECTION,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            is_transient=True,
            should_retry=True,
            max_retries=3,
            suggested_wait_ms=5000,
        )

    return None


def _classify_connection_error(exc: Exception) -> ClassifiedError | None:
    """Classify generic connection errors."""
    if isinstance(exc, (ConnectionError, ConnectionRefusedError, ConnectionResetError)):
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_CONNECTION,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            is_transient=True,
            should_retry=True,
            max_retries=3,
            suggested_wait_ms=5000,
        )

    if isinstance(exc, TimeoutError):
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_TIMEOUT,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.LOW,
            is_transient=True,
            should_retry=True,
            max_retries=3,
            suggested_wait_ms=5000,
        )

    return None


def _classify_ollama_error(exc: Exception) -> ClassifiedError | None:
    """Classify Ollama-specific errors."""
    exc_type = type(exc).__name__
    if exc_type != 'OllamaError':
        return None

    # Import here to avoid circular dependency
    from openhands.llm.ollama_provider import OllamaErrorType

    error_type = getattr(exc, 'error_type', None)
    is_transient = getattr(exc, 'is_transient', False)

    if error_type == OllamaErrorType.CONNECTION_REFUSED:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_CONNECTION,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.HIGH,
            is_transient=True,
            should_retry=True,
            max_retries=5,
            suggested_wait_ms=3000,
            context={'hint': 'Is Ollama running? Try: ollama serve'},
        )

    if error_type == OllamaErrorType.MODEL_NOT_FOUND:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.PERMANENT_MODEL_NOT_FOUND,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.HIGH,
            is_transient=False,
            should_retry=False,
            context={'hint': 'Pull the model with: ollama pull <model_name>'},
        )

    if error_type == OllamaErrorType.OUT_OF_MEMORY:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.PERMANENT_INSUFFICIENT_RESOURCES,
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.CRITICAL,
            is_transient=False,
            should_retry=False,
            context={'hint': 'Try a smaller model or free up GPU memory'},
        )

    if error_type == OllamaErrorType.TIMEOUT:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_TIMEOUT,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.LOW,
            is_transient=True,
            should_retry=True,
            max_retries=2,
            suggested_wait_ms=10000,
        )

    return ClassifiedError(
        original_error=exc,
        classification=ErrorClassification.UNKNOWN,
        category=ErrorCategory.LLM,
        severity=ErrorSeverity.MEDIUM,
        is_transient=is_transient,
        should_retry=is_transient,
        max_retries=2 if is_transient else 0,
        suggested_wait_ms=5000 if is_transient else 0,
    )


def _classify_agent_error(exc: Exception) -> ClassifiedError | None:
    """Classify agent-specific errors from OpenHands."""
    exc_type = type(exc).__name__

    if exc_type == 'AgentStuckInLoopError':
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.AGENT_STUCK,
            category=ErrorCategory.AGENT,
            severity=ErrorSeverity.HIGH,
            is_transient=False,
            should_retry=False,
        )

    if exc_type in ('FunctionCallNotExistsError', 'FunctionCallValidationError'):
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.AGENT_INVALID_ACTION,
            category=ErrorCategory.AGENT,
            severity=ErrorSeverity.MEDIUM,
            is_transient=False,
            should_retry=False,
        )

    if exc_type == 'LLMContextWindowExceedError':
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.PERMANENT_CONTEXT_LENGTH,
            category=ErrorCategory.LLM,
            severity=ErrorSeverity.MEDIUM,
            is_transient=False,
            should_retry=False,
        )

    if exc_type in ('LLMMalformedActionError', 'LLMNoActionError', 'LLMResponseError'):
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.AGENT_INVALID_ACTION,
            category=ErrorCategory.AGENT,
            severity=ErrorSeverity.MEDIUM,
            is_transient=True,  # These can be retried — LLM may produce valid output next time
            should_retry=True,
            max_retries=3,
            suggested_wait_ms=1000,
        )

    return None


def _classify_runtime_error(exc: Exception) -> ClassifiedError | None:
    """Classify runtime/sandbox errors."""
    msg = str(exc).lower()
    exc_type = type(exc).__name__

    if 'docker' in msg or 'container' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_UNAVAILABLE,
            category=ErrorCategory.RUNTIME,
            severity=ErrorSeverity.HIGH,
            is_transient=True,
            should_retry=True,
            max_retries=2,
            suggested_wait_ms=10000,
        )

    if 'permission denied' in msg or 'access denied' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.PERMANENT_AUTH,
            category=ErrorCategory.RUNTIME,
            severity=ErrorSeverity.HIGH,
            is_transient=False,
            should_retry=False,
        )

    if 'out of memory' in msg or 'oom' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.PERMANENT_INSUFFICIENT_RESOURCES,
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.CRITICAL,
            is_transient=False,
            should_retry=False,
        )

    return None


def _classify_by_message(exc: Exception) -> ClassifiedError | None:
    """Last-resort classification based on error message content."""
    msg = str(exc).lower()

    if 'rate limit' in msg or '429' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_RATE_LIMIT,
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.LOW,
            is_transient=True,
            should_retry=True,
            max_retries=5,
            suggested_wait_ms=8000,
        )

    if 'timeout' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.TRANSIENT_TIMEOUT,
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.LOW,
            is_transient=True,
            should_retry=True,
            max_retries=3,
            suggested_wait_ms=5000,
        )

    if 'unauthorized' in msg or '401' in msg or 'forbidden' in msg or '403' in msg:
        return ClassifiedError(
            original_error=exc,
            classification=ErrorClassification.PERMANENT_AUTH,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            is_transient=False,
            should_retry=False,
        )

    return None


# ── Error graph traversal (from OpenClaw) ─────────────────────────────

def collect_error_chain(exc: Exception) -> list[Exception]:
    """Collect the full chain of causes from a nested exception.

    Traverses __cause__ and __context__ to find all related errors.
    Ported from OpenClaw's collectErrorGraphCandidates.
    """
    chain: list[Exception] = []
    seen: set[int] = set()
    current: BaseException | None = exc

    while current is not None:
        exc_id = id(current)
        if exc_id in seen:
            break
        seen.add(exc_id)
        if isinstance(current, Exception):
            chain.append(current)
        # Follow both explicit cause and implicit context
        next_exc = current.__cause__ if current.__cause__ is not None else current.__context__
        current = next_exc

    return chain


def classify_error_chain(exc: Exception) -> ClassifiedError:
    """Classify an error by examining its entire cause chain.

    If the root error is unknown, walks the chain to find a more specific
    classification from nested causes.
    """
    chain = collect_error_chain(exc)

    # Try to classify the root error first
    root_classified = classify_error(exc)
    if root_classified.classification != ErrorClassification.UNKNOWN:
        return root_classified

    # Walk the chain to find a more specific classification
    for cause in chain[1:]:
        classified = classify_error(cause)
        if classified.classification != ErrorClassification.UNKNOWN:
            # Use the cause's classification but keep the original error
            classified.original_error = exc
            classified.context['root_cause'] = str(cause)
            return classified

    return root_classified
