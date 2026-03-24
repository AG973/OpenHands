"""Context assembly engine — pluggable context management with token budgets.

Provides a pluggable interface for assembling, compacting, and managing
the context window for LLM calls. Ported from OpenClaw's context-engine/types.ts.

Per OPERATING_RULES.md RULE 5: Production-grade — token budget enforcement, compaction triggers.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class CompactionTarget(Enum):
    """What compaction strategy to use."""

    BUDGET = 'budget'  # Compact to fit within token budget
    THRESHOLD = 'threshold'  # Compact when exceeding threshold


@dataclass
class BootstrapResult:
    """Result of context engine bootstrap."""

    session_id: str
    restored: bool = False
    message_count: int = 0
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestResult:
    """Result of ingesting a message into the context engine."""

    accepted: bool = True
    token_count: int = 0
    needs_compaction: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssembleResult:
    """Result of assembling context for an LLM call."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    total_tokens: int = 0
    budget_remaining: int = 0
    truncated: bool = False
    running_notes: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompactResult:
    """Result of compacting the context."""

    success: bool = True
    tokens_before: int = 0
    tokens_after: int = 0
    messages_before: int = 0
    messages_after: int = 0
    summary: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubagentSpawnPreparation:
    """Preparation result for spawning a sub-agent."""

    parent_context_summary: str = ''
    shared_notes: str = ''
    token_budget_allocated: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class SubagentEndReason(Enum):
    """Why a sub-agent session ended."""

    COMPLETED = 'completed'
    FAILED = 'failed'
    TIMEOUT = 'timeout'
    CANCELLED = 'cancelled'
    ORPHANED = 'orphaned'


class ContextEngine(ABC):
    """Abstract interface for context assembly engines.

    Implementations manage the lifecycle of context for LLM calls:
    - Bootstrap: restore context from a previous session
    - Ingest: add new messages to the context
    - Assemble: build the final context for an LLM call with token budgets
    - Compact: compress context when it exceeds limits

    Ported from OpenClaw's ContextEngine interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine name for registry/logging."""
        ...

    @abstractmethod
    def bootstrap(
        self,
        session_id: str,
        session_file: str = '',
    ) -> BootstrapResult:
        """Bootstrap the context engine for a session.

        This may restore context from a previous session file.
        """
        ...

    @abstractmethod
    def ingest(
        self,
        session_id: str,
        message: dict[str, Any],
        is_heartbeat: bool = False,
    ) -> IngestResult:
        """Ingest a new message into the context.

        Args:
            session_id: Current session identifier
            message: Message dict with 'role' and 'content'
            is_heartbeat: Whether this is a heartbeat message (may be prunable)
        """
        ...

    @abstractmethod
    def assemble(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        token_budget: int = 0,
        model: str = '',
        prompt: str = '',
    ) -> AssembleResult:
        """Assemble the context for an LLM call.

        Builds the final message list that fits within the token budget,
        including system prompt, running notes, and conversation history.

        Args:
            session_id: Current session
            messages: Raw message history
            token_budget: Maximum tokens allowed (0 = unlimited)
            model: Model name for tokenizer selection
            prompt: System prompt to include
        """
        ...

    @abstractmethod
    def compact(
        self,
        session_id: str,
        session_file: str = '',
        token_budget: int = 0,
        force: bool = False,
        current_token_count: int = 0,
        compaction_target: CompactionTarget = CompactionTarget.BUDGET,
    ) -> CompactResult:
        """Compact the context to reduce token usage.

        Args:
            session_id: Current session
            session_file: Path to session transcript file
            token_budget: Target token count after compaction
            force: Force compaction even if not needed
            current_token_count: Current token usage
            compaction_target: Strategy for compaction
        """
        ...

    def prepare_subagent_spawn(
        self,
        parent_session_key: str,
        child_session_key: str,
        ttl_ms: int = 0,
    ) -> SubagentSpawnPreparation | None:
        """Prepare context for spawning a sub-agent.

        Creates a context summary for the child agent.
        Default implementation returns None (no special preparation).
        """
        return None

    def on_subagent_ended(
        self,
        child_session_key: str,
        reason: SubagentEndReason,
    ) -> None:
        """Handle sub-agent session ending. Override for cleanup."""
        pass

    def dispose(self) -> None:
        """Cleanup resources. Override for custom cleanup."""
        pass


class DefaultContextEngine(ContextEngine):
    """Default context engine implementation.

    Uses simple token counting and message truncation for context management.
    Running notes survive compaction to preserve critical context.
    """

    def __init__(
        self,
        default_budget: int = 128000,
        compaction_threshold: float = 0.75,
    ):
        self._default_budget = default_budget
        self._compaction_threshold = compaction_threshold
        self._sessions: dict[str, _SessionContext] = {}

    @property
    def name(self) -> str:
        return 'default'

    def bootstrap(
        self,
        session_id: str,
        session_file: str = '',
    ) -> BootstrapResult:
        """Initialize or restore session context."""
        if session_id not in self._sessions:
            self._sessions[session_id] = _SessionContext()

        ctx = self._sessions[session_id]
        return BootstrapResult(
            session_id=session_id,
            restored=False,
            message_count=len(ctx.messages),
            token_count=ctx.estimated_tokens,
        )

    def ingest(
        self,
        session_id: str,
        message: dict[str, Any],
        is_heartbeat: bool = False,
    ) -> IngestResult:
        """Add a message to the session context."""
        if session_id not in self._sessions:
            self._sessions[session_id] = _SessionContext()

        ctx = self._sessions[session_id]
        msg_tokens = _estimate_tokens(message)
        ctx.messages.append(message)
        ctx.estimated_tokens += msg_tokens
        if is_heartbeat:
            ctx.heartbeat_indices.add(len(ctx.messages) - 1)

        needs_compaction = (
            self._default_budget > 0
            and ctx.estimated_tokens > self._default_budget * self._compaction_threshold
        )

        return IngestResult(
            accepted=True,
            token_count=msg_tokens,
            needs_compaction=needs_compaction,
        )

    def assemble(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        token_budget: int = 0,
        model: str = '',
        prompt: str = '',
    ) -> AssembleResult:
        """Assemble context within token budget."""
        budget = token_budget or self._default_budget
        ctx = self._sessions.get(session_id)

        assembled: list[dict[str, Any]] = []
        total_tokens = 0

        # 1. System prompt always first
        if prompt:
            system_msg = {'role': 'system', 'content': prompt}
            prompt_tokens = _estimate_tokens(system_msg)
            assembled.append(system_msg)
            total_tokens += prompt_tokens

        # 2. Running notes (survive compaction)
        if ctx and ctx.running_notes:
            notes_msg = {
                'role': 'system',
                'content': f'[Running Notes]\n{ctx.running_notes}',
            }
            notes_tokens = _estimate_tokens(notes_msg)
            assembled.append(notes_msg)
            total_tokens += notes_tokens

        # 3. Messages — include as many as fit, prioritizing recent
        remaining_budget = budget - total_tokens
        use_messages = messages if messages else (ctx.messages if ctx else [])

        # Work backwards from most recent to fit within budget
        selected: list[dict[str, Any]] = []
        for msg in reversed(use_messages):
            msg_tokens = _estimate_tokens(msg)
            if remaining_budget > 0 and msg_tokens <= remaining_budget:
                selected.insert(0, msg)
                remaining_budget -= msg_tokens
                total_tokens += msg_tokens
            elif remaining_budget <= 0:
                break

        assembled.extend(selected)
        truncated = len(selected) < len(use_messages)

        return AssembleResult(
            messages=assembled,
            total_tokens=total_tokens,
            budget_remaining=budget - total_tokens,
            truncated=truncated,
            running_notes=ctx.running_notes if ctx else '',
        )

    def compact(
        self,
        session_id: str,
        session_file: str = '',
        token_budget: int = 0,
        force: bool = False,
        current_token_count: int = 0,
        compaction_target: CompactionTarget = CompactionTarget.BUDGET,
    ) -> CompactResult:
        """Compact context by summarizing older messages."""
        ctx = self._sessions.get(session_id)
        if ctx is None:
            return CompactResult(success=False)

        budget = token_budget or self._default_budget
        tokens_before = ctx.estimated_tokens
        messages_before = len(ctx.messages)

        if not force and tokens_before <= budget * self._compaction_threshold:
            return CompactResult(
                success=True,
                tokens_before=tokens_before,
                tokens_after=tokens_before,
                messages_before=messages_before,
                messages_after=messages_before,
            )

        # Strategy: keep last N messages that fit in budget, summarize the rest
        target_tokens = int(budget * 0.5)  # Compact to 50% of budget
        kept_messages: list[dict[str, Any]] = []
        kept_tokens = 0

        # Always keep recent messages
        for msg in reversed(ctx.messages):
            msg_tokens = _estimate_tokens(msg)
            if kept_tokens + msg_tokens <= target_tokens:
                kept_messages.insert(0, msg)
                kept_tokens += msg_tokens
            else:
                break

        # Create summary of removed messages
        removed_count = messages_before - len(kept_messages)
        if removed_count > 0:
            summary = f'[Context compacted: {removed_count} older messages summarized to save tokens]'
            ctx.running_notes += f'\n{summary}' if ctx.running_notes else summary

        ctx.messages = kept_messages
        ctx.estimated_tokens = kept_tokens
        ctx.heartbeat_indices.clear()

        return CompactResult(
            success=True,
            tokens_before=tokens_before,
            tokens_after=kept_tokens,
            messages_before=messages_before,
            messages_after=len(kept_messages),
            summary=f'Compacted from {tokens_before} to {kept_tokens} tokens',
        )

    def add_running_note(self, session_id: str, note: str) -> None:
        """Add a running note that survives compaction."""
        if session_id not in self._sessions:
            self._sessions[session_id] = _SessionContext()
        ctx = self._sessions[session_id]
        if ctx.running_notes:
            ctx.running_notes += f'\n{note}'
        else:
            ctx.running_notes = note


@dataclass
class _SessionContext:
    """Internal session context tracking."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    estimated_tokens: int = 0
    running_notes: str = ''
    heartbeat_indices: set[int] = field(default_factory=set)


def _estimate_tokens(message: dict[str, Any]) -> int:
    """Rough token estimate for a message (4 chars ≈ 1 token)."""
    content = message.get('content', '')
    if isinstance(content, list):
        # Multimodal content
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get('type') == 'text':
                text_parts.append(part.get('text', ''))
        content = ' '.join(text_parts)
    if not isinstance(content, str):
        content = str(content)
    return max(1, len(content) // 4)


class ContextEngineRegistry:
    """Registry for pluggable context engines."""

    def __init__(self) -> None:
        self._engines: dict[str, ContextEngine] = {}
        self._default_engine: ContextEngine | None = None

    def register(self, engine: ContextEngine, is_default: bool = False) -> None:
        """Register a context engine."""
        self._engines[engine.name] = engine
        if is_default or self._default_engine is None:
            self._default_engine = engine

    def get(self, name: str) -> ContextEngine | None:
        """Get a context engine by name."""
        return self._engines.get(name)

    @property
    def default(self) -> ContextEngine:
        """Get the default context engine."""
        if self._default_engine is None:
            self._default_engine = DefaultContextEngine()
            self._engines['default'] = self._default_engine
        return self._default_engine

    def dispose_all(self) -> None:
        """Dispose all engines."""
        for engine in self._engines.values():
            try:
                engine.dispose()
            except Exception as e:
                logger.warning(f'Error disposing context engine {engine.name}: {e}')
        self._engines.clear()
        self._default_engine = None
