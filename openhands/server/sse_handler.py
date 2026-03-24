"""SSE (Server-Sent Events) handler — lightweight server-to-client event streaming.

Provides SSE endpoints for real-time event delivery as an alternative to WebSocket.
SSE is simpler, HTTP-based, and works through proxies/load balancers that may
block WebSocket connections.

Ported from OpenClaw's gateway SSE patterns.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator

from openhands.core.logger import openhands_logger as logger

# SSE configuration
SSE_KEEPALIVE_INTERVAL_S = 15.0  # Send keepalive comment every 15s
SSE_MAX_CONNECTIONS = 100  # Max concurrent SSE connections
SSE_BUFFER_SIZE = 1000  # Max events buffered per connection


class SSEEventType(Enum):
    """Types of SSE events."""

    # Agent lifecycle
    AGENT_STEP = 'agent_step'
    AGENT_STATUS = 'agent_status'
    AGENT_ERROR = 'agent_error'

    # Task progress
    TASK_PROGRESS = 'task_progress'
    TASK_COMPLETE = 'task_complete'

    # System events
    HEARTBEAT = 'heartbeat'
    HEALTH_STATUS = 'health_status'
    QUEUE_STATUS = 'queue_status'

    # Memory events
    MEMORY_UPDATED = 'memory_updated'
    CONTEXT_COMPACTED = 'context_compacted'

    # Session events
    SESSION_STARTED = 'session_started'
    SESSION_ENDED = 'session_ended'
    SESSION_PAUSED = 'session_paused'

    # Sub-agent events
    SUBAGENT_SPAWNED = 'subagent_spawned'
    SUBAGENT_COMPLETED = 'subagent_completed'
    SUBAGENT_FAILED = 'subagent_failed'

    # Generic
    MESSAGE = 'message'
    ERROR = 'error'
    KEEPALIVE = 'keepalive'


@dataclass
class SSEEvent:
    """A single SSE event."""

    event_type: SSEEventType
    data: dict[str, Any]
    event_id: str = ''
    retry_ms: int | None = None
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if not self.event_id:
            self.event_id = f'{int(self.timestamp * 1000)}'

    def to_sse_string(self) -> str:
        """Format as SSE wire protocol string."""
        lines: list[str] = []

        if self.event_id:
            lines.append(f'id: {self.event_id}')

        lines.append(f'event: {self.event_type.value}')

        if self.retry_ms is not None:
            lines.append(f'retry: {self.retry_ms}')

        # Data must be on its own line(s) — multi-line data needs multiple "data:" prefixes
        data_str = json.dumps(self.data)
        for data_line in data_str.split('\n'):
            lines.append(f'data: {data_line}')

        lines.append('')  # Empty line terminates the event
        return '\n'.join(lines) + '\n'


class SSEConnection:
    """A single SSE client connection with its own event buffer."""

    def __init__(self, connection_id: str, session_id: str = ''):
        self.connection_id = connection_id
        self.session_id = session_id
        self.created_at = time.time()
        self.last_event_id = ''
        self._queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue(
            maxsize=SSE_BUFFER_SIZE
        )
        self._closed = False

    @property
    def is_closed(self) -> bool:
        return self._closed

    def send(self, event: SSEEvent) -> bool:
        """Send an event to this connection.

        Returns False if the buffer is full (event dropped).
        """
        if self._closed:
            return False
        try:
            self._queue.put_nowait(event)
            return True
        except asyncio.QueueFull:
            logger.warning(
                f'SSE connection {self.connection_id} buffer full, dropping event'
            )
            return False

    async def events(self) -> AsyncIterator[SSEEvent]:
        """Async iterator over events for this connection."""
        while not self._closed:
            try:
                event = await asyncio.wait_for(
                    self._queue.get(), timeout=SSE_KEEPALIVE_INTERVAL_S
                )
                if event is None:
                    # Poison pill — connection closed
                    break
                self.last_event_id = event.event_id
                yield event
            except asyncio.TimeoutError:
                # Send keepalive
                yield SSEEvent(
                    event_type=SSEEventType.KEEPALIVE,
                    data={'ts': time.time()},
                )

    def close(self) -> None:
        """Close this connection."""
        self._closed = True
        try:
            self._queue.put_nowait(None)  # Poison pill
        except asyncio.QueueFull:
            pass


class SSEManager:
    """Manages SSE connections and broadcasts events.

    Provides:
    - Connection registration/deregistration
    - Broadcast to all connections
    - Targeted send to specific sessions
    - Connection monitoring and cleanup
    """

    def __init__(self, max_connections: int = SSE_MAX_CONNECTIONS):
        self._connections: dict[str, SSEConnection] = {}
        self._max_connections = max_connections
        self._event_counter = 0

    def connect(
        self, connection_id: str, session_id: str = ''
    ) -> SSEConnection | None:
        """Register a new SSE connection.

        Returns the connection or None if max connections reached.
        """
        # Cleanup stale connections first
        self._cleanup_stale()

        if len(self._connections) >= self._max_connections:
            logger.warning(
                f'SSE max connections reached ({self._max_connections}), rejecting'
            )
            return None

        conn = SSEConnection(connection_id, session_id)
        self._connections[connection_id] = conn
        logger.debug(f'SSE connection registered: {connection_id}')
        return conn

    def disconnect(self, connection_id: str) -> None:
        """Remove an SSE connection."""
        conn = self._connections.pop(connection_id, None)
        if conn is not None:
            conn.close()
            logger.debug(f'SSE connection removed: {connection_id}')

    def broadcast(self, event: SSEEvent) -> int:
        """Broadcast an event to all connections.

        Returns the number of connections that received the event.
        """
        sent_count = 0
        for conn in list(self._connections.values()):
            if conn.is_closed:
                continue
            if conn.send(event):
                sent_count += 1
        return sent_count

    def send_to_session(self, session_id: str, event: SSEEvent) -> int:
        """Send an event to all connections for a specific session."""
        sent_count = 0
        for conn in list(self._connections.values()):
            if conn.is_closed:
                continue
            if conn.session_id == session_id:
                if conn.send(event):
                    sent_count += 1
        return sent_count

    def emit(
        self,
        event_type: SSEEventType,
        data: dict[str, Any],
        session_id: str | None = None,
    ) -> int:
        """Convenience method to create and send an SSE event.

        Args:
            event_type: Type of event
            data: Event payload
            session_id: If provided, send only to that session's connections

        Returns:
            Number of connections that received the event
        """
        self._event_counter += 1
        event = SSEEvent(
            event_type=event_type,
            data=data,
            event_id=str(self._event_counter),
        )

        if session_id is not None:
            return self.send_to_session(session_id, event)
        return self.broadcast(event)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    def stats(self) -> dict[str, Any]:
        """Get SSE manager statistics."""
        return {
            'total_connections': len(self._connections),
            'max_connections': self._max_connections,
            'total_events': self._event_counter,
            'sessions': list(
                {c.session_id for c in self._connections.values() if c.session_id}
            ),
        }

    def _cleanup_stale(self) -> None:
        """Remove closed connections."""
        stale = [
            cid for cid, conn in self._connections.items() if conn.is_closed
        ]
        for cid in stale:
            del self._connections[cid]

    def close_all(self) -> None:
        """Close all connections."""
        for conn in self._connections.values():
            conn.close()
        self._connections.clear()
