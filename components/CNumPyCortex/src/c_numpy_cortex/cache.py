from __future__ import annotations

from dataclasses import dataclass, field
import threading

from .contracts import ObservedValue


@dataclass
class WorkerCache:
    """Immutable snapshot cache for slow workers.

    Workers replace the entire snapshot atomically.
    Readers get a reference to the current snapshot.
    """
    _data: dict[str, ObservedValue] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _version: int = field(default=0, init=False)

    def publish(self, updates: dict[str, ObservedValue]) -> int:
        """Atomically publish a set of updates. Returns new version."""
        with self._lock:
            merged = dict(self._data)
            merged.update(updates)
            self._data = merged
            self._version += 1
            return self._version

    def snapshot(self) -> tuple[dict[str, ObservedValue], int]:
        """Read the current snapshot without blocking the writer."""
        with self._lock:
            return dict(self._data), self._version

    def get(self, channel_id: str) -> tuple[ObservedValue | None, int]:
        """Get a single channel's latest value."""
        with self._lock:
            return self._data.get(channel_id), self._version

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
