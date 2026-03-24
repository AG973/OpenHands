"""Session lifecycle events — branching, pausing, resuming, and tracking.

Ported from OpenClaw's session lifecycle patterns. Provides:
- Session state machine with defined transitions
- Event emission for lifecycle changes
- Branch/fork support for session trees
- Metadata and tag tracking

Per OPERATING_RULES.md RULE 5: No missing logging — structured context propagation.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from openhands.core.logger import openhands_logger as logger

# Limits
MAX_SESSION_TAGS = 50
MAX_TAG_LENGTH = 100
MAX_METADATA_SIZE = 1000


class SessionState(Enum):
    """Session lifecycle states."""

    CREATED = 'created'
    RUNNING = 'running'
    PAUSED = 'paused'
    WAITING_FOR_USER = 'waiting_for_user'
    COMPLETING = 'completing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    TIMED_OUT = 'timed_out'


class SessionEventType(Enum):
    """Types of session lifecycle events."""

    CREATED = 'session_created'
    STARTED = 'session_started'
    PAUSED = 'session_paused'
    RESUMED = 'session_resumed'
    WAITING = 'session_waiting'
    COMPLETING = 'session_completing'
    COMPLETED = 'session_completed'
    FAILED = 'session_failed'
    CANCELLED = 'session_cancelled'
    TIMED_OUT = 'session_timed_out'
    BRANCHED = 'session_branched'
    TAGGED = 'session_tagged'
    METADATA_UPDATED = 'session_metadata_updated'


# Valid state transitions
_VALID_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.CREATED: {SessionState.RUNNING, SessionState.CANCELLED},
    SessionState.RUNNING: {
        SessionState.PAUSED,
        SessionState.WAITING_FOR_USER,
        SessionState.COMPLETING,
        SessionState.COMPLETED,
        SessionState.FAILED,
        SessionState.CANCELLED,
        SessionState.TIMED_OUT,
    },
    SessionState.PAUSED: {
        SessionState.RUNNING,
        SessionState.CANCELLED,
        SessionState.FAILED,
    },
    SessionState.WAITING_FOR_USER: {
        SessionState.RUNNING,
        SessionState.CANCELLED,
        SessionState.TIMED_OUT,
    },
    SessionState.COMPLETING: {
        SessionState.COMPLETED,
        SessionState.FAILED,
    },
    # Terminal states — no transitions out
    SessionState.COMPLETED: set(),
    SessionState.FAILED: set(),
    SessionState.CANCELLED: set(),
    SessionState.TIMED_OUT: set(),
}


@dataclass
class SessionEvent:
    """A lifecycle event for a session."""

    event_type: SessionEventType
    session_id: str
    timestamp: float = 0.0
    old_state: SessionState | None = None
    new_state: SessionState | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class SessionInfo:
    """Full session tracking information."""

    session_id: str
    state: SessionState = SessionState.CREATED
    parent_id: str | None = None
    branch_point: str | None = None  # Event ID where branch occurred
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    events: list[SessionEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()

    @property
    def is_terminal(self) -> bool:
        return self.state in (
            SessionState.COMPLETED,
            SessionState.FAILED,
            SessionState.CANCELLED,
            SessionState.TIMED_OUT,
        )

    @property
    def duration_s(self) -> float:
        """Session duration in seconds."""
        end = self.completed_at if self.completed_at > 0 else time.time()
        start = self.started_at if self.started_at > 0 else self.created_at
        return end - start


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class SessionLifecycle:
    """Manages session lifecycle with state machine and event tracking.

    Each session follows a defined state machine. State transitions
    emit events that can be observed by handlers.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionInfo] = {}
        self._event_handlers: list[Callable[[SessionEvent], None]] = []

    def create(
        self,
        session_id: str | None = None,
        parent_id: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionInfo:
        """Create a new session.

        Args:
            session_id: Optional ID (generated if not provided)
            parent_id: Parent session ID for branched sessions
            tags: Initial tags
            metadata: Initial metadata
        """
        if session_id is None:
            session_id = f'session-{uuid.uuid4().hex[:12]}'

        if session_id in self._sessions:
            raise ValueError(f'Session {session_id} already exists')

        safe_tags = _validate_tags(tags or [])
        safe_metadata = _validate_metadata(metadata or {})

        info = SessionInfo(
            session_id=session_id,
            parent_id=parent_id,
            tags=safe_tags,
            metadata=safe_metadata,
        )
        self._sessions[session_id] = info

        self._emit(SessionEvent(
            event_type=SessionEventType.CREATED,
            session_id=session_id,
            new_state=SessionState.CREATED,
            metadata={'parent_id': parent_id},
        ))

        logger.info(f'Session created: {session_id} (parent={parent_id})')
        return info

    def transition(
        self,
        session_id: str,
        new_state: SessionState,
        metadata: dict[str, Any] | None = None,
    ) -> SessionInfo:
        """Transition a session to a new state.

        Args:
            session_id: Session to transition
            new_state: Target state
            metadata: Additional metadata for the event

        Raises:
            InvalidTransitionError: If the transition is not valid
        """
        info = self._get_session(session_id)
        old_state = info.state

        valid_next = _VALID_TRANSITIONS.get(old_state, set())
        if new_state not in valid_next:
            raise InvalidTransitionError(
                f'Cannot transition session {session_id} '
                f'from {old_state.value} to {new_state.value}. '
                f'Valid transitions: {[s.value for s in valid_next]}'
            )

        info.state = new_state

        # Track timestamps
        if new_state == SessionState.RUNNING and info.started_at == 0.0:
            info.started_at = time.time()
        if info.is_terminal and info.completed_at == 0.0:
            info.completed_at = time.time()

        event_type = _state_to_event(new_state)
        event = SessionEvent(
            event_type=event_type,
            session_id=session_id,
            old_state=old_state,
            new_state=new_state,
            metadata=metadata or {},
        )
        info.events.append(event)
        self._emit(event)

        logger.info(
            f'Session {session_id}: {old_state.value} → {new_state.value}'
        )
        return info

    def branch(
        self,
        parent_session_id: str,
        branch_point: str = '',
        tags: list[str] | None = None,
    ) -> SessionInfo:
        """Create a branch (fork) of an existing session.

        Args:
            parent_session_id: Session to branch from
            branch_point: Optional event ID marking the branch point
            tags: Tags for the new branch

        Returns:
            New session branched from the parent
        """
        parent = self._get_session(parent_session_id)

        child = self.create(
            parent_id=parent_session_id,
            tags=tags,
            metadata={
                'branched_from': parent_session_id,
                'branch_point': branch_point,
            },
        )
        child.branch_point = branch_point

        self._emit(SessionEvent(
            event_type=SessionEventType.BRANCHED,
            session_id=parent_session_id,
            metadata={
                'child_id': child.session_id,
                'branch_point': branch_point,
            },
        ))

        logger.info(
            f'Session branched: {parent_session_id} → {child.session_id}'
        )
        return child

    def add_tag(self, session_id: str, tag: str) -> bool:
        """Add a tag to a session."""
        info = self._get_session(session_id)

        if len(tag) > MAX_TAG_LENGTH:
            tag = tag[:MAX_TAG_LENGTH]

        if len(info.tags) >= MAX_SESSION_TAGS:
            logger.warning(f'Session {session_id} has max tags ({MAX_SESSION_TAGS})')
            return False

        if tag not in info.tags:
            info.tags.append(tag)
            self._emit(SessionEvent(
                event_type=SessionEventType.TAGGED,
                session_id=session_id,
                metadata={'tag': tag},
            ))
        return True

    def update_metadata(
        self, session_id: str, updates: dict[str, Any]
    ) -> SessionInfo:
        """Update session metadata."""
        info = self._get_session(session_id)
        safe_updates = _validate_metadata(updates)
        info.metadata.update(safe_updates)

        self._emit(SessionEvent(
            event_type=SessionEventType.METADATA_UPDATED,
            session_id=session_id,
            metadata={'updates': list(safe_updates.keys())},
        ))
        return info

    def get(self, session_id: str) -> SessionInfo | None:
        """Get session info by ID."""
        return self._sessions.get(session_id)

    def get_children(self, parent_id: str) -> list[SessionInfo]:
        """Get all child sessions of a parent."""
        return [
            info
            for info in self._sessions.values()
            if info.parent_id == parent_id
        ]

    def get_by_state(self, state: SessionState) -> list[SessionInfo]:
        """Get all sessions in a given state."""
        return [
            info
            for info in self._sessions.values()
            if info.state == state
        ]

    def get_by_tag(self, tag: str) -> list[SessionInfo]:
        """Get all sessions with a specific tag."""
        return [
            info
            for info in self._sessions.values()
            if tag in info.tags
        ]

    def on_event(self, handler: Callable[[SessionEvent], None]) -> None:
        """Register a session event handler."""
        self._event_handlers.append(handler)

    def _get_session(self, session_id: str) -> SessionInfo:
        """Get a session or raise ValueError."""
        info = self._sessions.get(session_id)
        if info is None:
            raise ValueError(f'Session {session_id} not found')
        return info

    def _emit(self, event: SessionEvent) -> None:
        """Emit an event to all handlers."""
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f'Session event handler error for {event.event_type.value}: {e}'
                )

    def stats(self) -> dict[str, Any]:
        """Get session lifecycle statistics."""
        by_state: dict[str, int] = {}
        for info in self._sessions.values():
            state_name = info.state.value
            by_state[state_name] = by_state.get(state_name, 0) + 1

        return {
            'total_sessions': len(self._sessions),
            'by_state': by_state,
            'total_events': sum(len(info.events) for info in self._sessions.values()),
        }


def _state_to_event(state: SessionState) -> SessionEventType:
    """Map a session state to its corresponding event type."""
    mapping = {
        SessionState.CREATED: SessionEventType.CREATED,
        SessionState.RUNNING: SessionEventType.STARTED,
        SessionState.PAUSED: SessionEventType.PAUSED,
        SessionState.WAITING_FOR_USER: SessionEventType.WAITING,
        SessionState.COMPLETING: SessionEventType.COMPLETING,
        SessionState.COMPLETED: SessionEventType.COMPLETED,
        SessionState.FAILED: SessionEventType.FAILED,
        SessionState.CANCELLED: SessionEventType.CANCELLED,
        SessionState.TIMED_OUT: SessionEventType.TIMED_OUT,
    }
    return mapping.get(state, SessionEventType.STARTED)


def _validate_tags(tags: list[str]) -> list[str]:
    """Validate and sanitize tags."""
    result: list[str] = []
    for tag in tags[:MAX_SESSION_TAGS]:
        clean = str(tag).strip()
        if clean:
            result.append(clean[:MAX_TAG_LENGTH])
    return result


def _validate_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Validate metadata size."""
    if len(metadata) > MAX_METADATA_SIZE:
        logger.warning(
            f'Metadata has {len(metadata)} keys, truncating to {MAX_METADATA_SIZE}'
        )
        keys = list(metadata.keys())[:MAX_METADATA_SIZE]
        return {k: metadata[k] for k in keys}
    return dict(metadata)
