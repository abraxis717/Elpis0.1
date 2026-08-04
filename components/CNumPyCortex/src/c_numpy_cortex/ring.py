from __future__ import annotations

import threading

import numpy as np

from .contracts import (
    ObservedValue,
    ObservationValidity,
    ChannelSchema,
)


# ─── Legacy backward compatibility ──────────────────────────────────────

class NumPyRingBuffer:
    """Legacy ring buffer for backward compatibility."""

    def __init__(
        self,
        capacity: int,
        channel_names: tuple[str, ...],
    ):
        if capacity < 2:
            raise ValueError("capacity must be >= 2")
        if not channel_names:
            raise ValueError("at least one channel is required")

        self.capacity = int(capacity)
        self.channel_names = tuple(channel_names)
        self._index = {
            name: index
            for index, name in enumerate(self.channel_names)
        }
        self._values = np.full(
            (capacity, len(channel_names)),
            np.nan,
            dtype=np.float32,
        )
        self._wall_time_ns = np.zeros(capacity, dtype=np.int64)
        self._monotonic_ns = np.zeros(capacity, dtype=np.int64)
        self._write = 0
        self._size = 0
        self._lock = threading.Lock()

    def append(
        self,
        wall_time_ns: int,
        monotonic_ns: int,
        values: dict[str, float],
    ) -> None:
        row = np.full(
            len(self.channel_names),
            np.nan,
            dtype=np.float32,
        )
        for name, value in values.items():
            index = self._index.get(name)
            if index is None:
                continue
            try:
                row[index] = float(value)
            except (TypeError, ValueError):
                row[index] = np.nan

        with self._lock:
            index = self._write
            self._values[index] = row
            self._wall_time_ns[index] = int(wall_time_ns)
            self._monotonic_ns[index] = int(monotonic_ns)
            self._write = (index + 1) % self.capacity
            self._size = min(self._size + 1, self.capacity)

    def snapshot(
        self,
        max_rows: int | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        with self._lock:
            if max_rows is None:
                size = self._size
            else:
                size = min(self._size, int(max_rows))

            if size == 0:
                return (
                    np.empty(0, dtype=np.int64),
                    np.empty(0, dtype=np.int64),
                    np.empty(
                        (0, len(self.channel_names)),
                        dtype=np.float32,
                    ),
                )

            start = (self._write - size) % self.capacity
            indices = (start + np.arange(size)) % self.capacity

            return (
                self._wall_time_ns[indices].copy(),
                self._monotonic_ns[indices].copy(),
                self._values[indices].copy(),
            )

    def __len__(self) -> int:
        with self._lock:
            return self._size


class ChronologicalRing:
    """Per-channel chronological observation ring.

    Each channel row maintains its own sequence of ObservedValue entries
    ordered by monotonic_ns. Supports deterministic replay via
    source_sequence and observed_monotonic_ns.
    """

    def __init__(
        self,
        schema: ChannelSchema,
        capacity: int = 1024,
    ):
        self.schema = schema
        self.capacity = capacity

        self._channels: dict[str, list[ObservedValue]] = {
            r.channel_id: [] for r in schema.rows
        }

        self._lock = threading.Lock()

    def append_for(
        self,
        channel_id: str,
        value: ObservedValue,
    ) -> None:
        with self._lock:
            ch_list = self._channels.get(channel_id)

            if ch_list is None:
                return

            ch_list.append(value)

            if len(ch_list) > self.capacity:
                ch_list.pop(0)

    def get_chronological(
        self,
        channel_id: str,
        count: int = 9,
    ) -> tuple[ObservedValue, ...]:
        """Get the last N observations ordered by monotonic_ns."""
        with self._lock:
            ch_list = self._channels.get(channel_id, [])

        sorted_vals = sorted(
            ch_list,
            key=lambda v: v.observed_monotonic_ns,
        )

        return tuple(sorted_vals[-count:])

    def sample_count(self, channel_id: str) -> int:
        with self._lock:
            return len(self._channels.get(channel_id, []))

    def snapshot_all(self) -> dict[str, tuple[ObservedValue, ...]]:
        with self._lock:
            result = {}

            for ch_id, ch_list in self._channels.items():
                sorted_vals = sorted(
                    list(ch_list),
                    key=lambda v: v.observed_monotonic_ns,
                )
                result[ch_id] = tuple(sorted_vals)

            return result

    def get_valid_history(
        self,
        channel_id: str,
        max_count: int = 256,
    ) -> tuple[float, ...]:
        """Get valid numerical history for quantization."""
        with self._lock:
            ch_list = self._channels.get(channel_id, [])

        valid: list[float] = []

        for v in ch_list:
            if (
                v.validity == ObservationValidity.FRESH
                and v.value is not None
                and np.isfinite(v.value)
            ):
                valid.append(v.value)

        return tuple(valid[-max_count:])
