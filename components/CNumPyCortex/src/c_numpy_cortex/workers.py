from __future__ import annotations

import threading
import time

from .cache import WorkerCache
from .contracts import (
    MISSING_CHANNEL,
    ObservedValue,
    ObservationValidity,
)


class Worker:
    """Base class for slow-source cache workers."""

    def __init__(
        self,
        name: str,
        interval_ns: int,
        cache: WorkerCache,
    ):
        self.name = name
        self.interval_ns = interval_ns
        self.cache = cache
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._source_seq = 0

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=self.name,
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        next_due = time.monotonic_ns()

        while not self._stop_event.is_set():
            now = time.monotonic_ns()

            if now >= next_due:
                self._tick()
                next_due = now + self.interval_ns

            sleep_s = max(
                0.0,
                (next_due - time.monotonic_ns()) / 1e9,
            )

            if sleep_s > 0:
                self._stop_event.wait(timeout=sleep_s)

    def _tick(self) -> None:
        raise NotImplementedError


class PsutilWorker:
    """Fast-path psutil reads are synchronous, not a worker.

    This class exists so the fast path can call the same interface.
    """

    def __init__(self):
        self._source_seq = 0

    def _next_seq(self) -> int:
        self._source_seq += 1
        return self._source_seq

    def start(self) -> None:
        pass

    def stop(self, timeout: float = 0.0) -> None:
        pass
