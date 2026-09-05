from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable, Protocol, TypeVar

from agent.schemas import BookingState, Recommendation


@dataclass
class SessionRecord:
    state: BookingState = field(default_factory=BookingState)
    recommendations: list[Recommendation] = field(default_factory=list)


Result = TypeVar("Result")


class SessionRepository(Protocol):
    def get(self, session_id: str) -> SessionRecord: ...
    def save(self, session_id: str, record: SessionRecord) -> None: ...
    def transact(self, session_id: str, operation: Callable[[SessionRecord], Result]) -> Result: ...


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._records_lock = Lock()
        self._session_locks: dict[str, Lock] = {}

    def get(self, session_id: str) -> SessionRecord:
        with self._records_lock:
            return deepcopy(self._sessions.get(session_id, SessionRecord()))

    def save(self, session_id: str, record: SessionRecord) -> None:
        with self._records_lock:
            self._sessions[session_id] = deepcopy(record)

    def transact(self, session_id: str, operation: Callable[[SessionRecord], Result]) -> Result:
        """Serialize a complete turn per session without blocking other guests."""
        with self._records_lock:
            lock = self._session_locks.setdefault(session_id, Lock())
        with lock:
            with self._records_lock:
                record = deepcopy(self._sessions.get(session_id, SessionRecord()))
            result = operation(record)
            with self._records_lock:
                self._sessions[session_id] = deepcopy(record)
            return result
