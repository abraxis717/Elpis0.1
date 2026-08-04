# elpis/contracts/legacy/canary_telemetry.py — Wave-1 shadow soak telemetry.
# Structured event schema for Bridge→Spine envelope canary shadow soak.
#
# Events capture per-packet canary verification results, timing, and
# envelope metadata. Logging is optional-telemetry: failure must never
# affect the legacy production path.
#
# Schema version: 3 (extends v2 with occurrence identity + content checksum)
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Dedicated logger — external handler attachment controls actual file output.
logger = logging.getLogger("elpis.envelope_canary")


# ---------------------------------------------------------------------------
# Occurrence identity (§III Decision 3)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class EventOccurrence:
    """Occurrence identity for a telemetry event.

    iota_e = (run_id, process_nonce, process_id, sequence)

    Each emitted event gets a unique occurrence. Within one process:
      sequence strictly increases, no duplicates.
    Across processes:
      (process_nonce, process_id) disambiguates.
    """

    run_id: str
    process_nonce: str
    process_id: int
    sequence: int

    @property
    def event_id(self) -> str:
        """Dense, non-truncated encoding of the occurrence tuple.

        Format: run_id|process_nonce|process_id|sequence
        No hash truncation — the full tuple is preserved.
        """
        return f"{self.run_id}|{self.process_nonce}|{self.process_id}|{self.sequence}"


class EventSequencer:
    """Thread-safe atomic sequence generator.

    One instance per process. Generates monotonic sequences under a
    threading.Lock — thread safety guaranteed by Python's documented
    Lock semantics, not incidental GIL behaviour.
    """

    def __init__(self, run_id: str = ""):
        self._run_id = run_id
        self._process_nonce = uuid.uuid4().hex[:16]
        self._process_id = os.getpid()
        self._sequence: int = 0
        self._lock = threading.Lock()

    def next_occurrence(self, run_id: str = "") -> EventOccurrence:
        """Return the next occurrence identity with atomic sequence increment.

        s_{n+1} = s_n + 1,  and  s_i != s_j for i != j.
        """
        with self._lock:
            self._sequence += 1
            seq = self._sequence
        return EventOccurrence(
            run_id=run_id or self._run_id,
            process_nonce=self._process_nonce,
            process_id=self._process_id,
            sequence=seq,
        )


# ---------------------------------------------------------------------------
# Content checksum (§III Decision 3)
# ---------------------------------------------------------------------------

# Fields that form occurrence identity — excluded from content checksum.
_IDENTITY_FIELDS = frozenset({
    "run_id", "process_nonce", "process_id", "sequence",
    "event_id", "content_checksum",
})


def _compute_content_checksum(
    event_dict: Dict[str, Any], schema_version: int
) -> str:
    """Compute content checksum: chi_e = H(domain, schema_version, canon(E \\ {iota_e, chi_e})).

    The checksum excludes all occurrence-identity fields so that
    identical content produces identical checksums regardless of
    which run / process / sequence emitted them.
    """
    content = {
        k: v for k, v in event_dict.items()
        if k not in _IDENTITY_FIELDS
    }
    canon = json.dumps(content, sort_keys=True, separators=(",", ":"))
    header = f"elpis-canary-event|v{schema_version}"
    return hashlib.sha256(
        (header + canon).encode("utf-8")
    ).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Global state — lazily initialised, thread-safe
# ---------------------------------------------------------------------------

_sequencer: Optional[EventSequencer] = None
_event_queue: Optional[queue.Queue] = None


def _get_sequencer() -> EventSequencer:
    global _sequencer
    if _sequencer is None:
        _sequencer = EventSequencer()
    return _sequencer


def _get_queue() -> queue.Queue:
    global _event_queue
    if _event_queue is None:
        _event_queue = queue.Queue()
    return _event_queue


# ---------------------------------------------------------------------------
# CanaryEvent schema (v3)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CanaryEvent:
    """Versioned canary telemetry event for A1/W1S shadow soak.

    Captures one Bridge→Spine forward pass with canary shadow verification.
    All fields are JSON-serializable primitives or None.
    """

    # Schema
    schema_version: int = 3

    # Occurrence identity (iota_e) — assigned at emission
    process_nonce: str = ""
    process_id: int = 0
    sequence: int = 0

    # Derived identity
    event_id: str = ""

    # Content checksum (chi_e)
    content_checksum: str = ""

    # Identifiers
    run_id: str = ""
    event_index: int = 0
    monotonic_ns: int = 0
    thread_id: int = 0

    # Route
    route_raw: str = ""
    route_family: str = ""
    route_provenance: str = ""

    # Budget
    legacy_budget: int = 0
    budget_axes_granted: str = ""

    # Mask
    mask_mode: str = ""
    mask_active_count: int = 81

    # Latent statistics (finite aggregates only — never raw vectors)
    latent_min: float = 0.0
    latent_max: float = 0.0
    latent_mean: float = 0.0
    latent_std: float = 0.0

    # Checksums (hex prefixes, not full grids)
    original_checksum: str = ""
    envelope_checksum: str = ""
    reconstructed_checksum: str = ""

    # Verification results
    grid_bytes_match: bool = True
    dtype_match: bool = True
    shape_match: bool = True
    non_grid_fields_match: bool = True
    budget_correct: bool = True
    route_mapped: bool = True

    # Mutation
    original_packet_mutated: bool = False

    # Outcome
    canary_passed: bool = True
    reason_code: str = "OK"

    # Timing (nanoseconds, perf_counter_ns)
    baseline_elapsed_ns: int = 0
    shadow_elapsed_ns: int = 0
    shadow_overhead_ns: int = 0

    # ── JSON serialisation ──────────────────────────────────────────────

    _JSON_FIELDS = (
        "schema_version", "process_nonce", "process_id", "sequence",
        "event_id", "content_checksum",
        "run_id", "event_index", "monotonic_ns", "thread_id",
        "route_raw", "route_family", "route_provenance",
        "legacy_budget", "budget_axes_granted", "mask_mode",
        "mask_active_count", "latent_min", "latent_max",
        "latent_mean", "latent_std",
        "original_checksum", "envelope_checksum", "reconstructed_checksum",
        "grid_bytes_match", "dtype_match", "shape_match",
        "non_grid_fields_match", "budget_correct", "route_mapped",
        "original_packet_mutated", "canary_passed", "reason_code",
        "baseline_elapsed_ns", "shadow_elapsed_ns", "shadow_overhead_ns",
    )

    def to_json_dict(self) -> Dict[str, object]:
        """Convert to JSON-serializable dict. All values are primitives."""
        result: Dict[str, object] = {}
        for f_name in self._JSON_FIELDS:
            val = getattr(self, f_name)
            if isinstance(val, float) and not math.isfinite(val):
                val = 0.0
            result[f_name] = val
        return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_MAX_REASON_LEN = 256
_MAX_ERROR_LEN = 512


def _validate_event(event: CanaryEvent) -> bool:
    """Validate event fields. Returns True if valid."""
    if event.schema_version < 1:
        return False
    if event.process_id < 0:
        return False
    if event.sequence < 0:
        return False
    if len(event.reason_code) > _MAX_REASON_LEN:
        return False
    # Finite floats
    for f in ("latent_min", "latent_max", "latent_mean", "latent_std"):
        v = getattr(event, f)
        if isinstance(v, float) and not math.isfinite(v):
            return False
    return True


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

def emit_canary_event(event: CanaryEvent) -> None:
    """Emit a canary event to the logger and thread-safe queue.

    Assigns occurrence identity (process_nonce, process_id, sequence,
    event_id) and content checksum at emission time. The original
    event object is NOT mutated — a new frozen instance is produced.

    Logging / queuing failure is non-fatal (optional-telemetry).
    """
    try:
        # Validate input
        if not _validate_event(event):
            return

        # Assign occurrence identity
        sequencer = _get_sequencer()
        occurrence = sequencer.next_occurrence(run_id=event.run_id)

        # Compute content checksum from the event's content fields
        # (excluding identity fields). We use the original event's data
        # because identity fields are not yet set.
        pre = event.to_json_dict()
        # Remove placeholder identity fields so checksum is clean
        for k in _IDENTITY_FIELDS:
            pre.pop(k, None)
        content_checksum = _compute_content_checksum(pre, event.schema_version)

        # Build the enriched event (frozen — new instance)
        enriched = CanaryEvent(
            schema_version=event.schema_version,
            process_nonce=occurrence.process_nonce,
            process_id=occurrence.process_id,
            sequence=occurrence.sequence,
            event_id=occurrence.event_id,
            content_checksum=content_checksum,
            run_id=event.run_id,
            event_index=event.event_index,
            monotonic_ns=event.monotonic_ns,
            thread_id=event.thread_id,
            route_raw=event.route_raw,
            route_family=event.route_family,
            route_provenance=event.route_provenance,
            legacy_budget=event.legacy_budget,
            budget_axes_granted=event.budget_axes_granted,
            mask_mode=event.mask_mode,
            mask_active_count=event.mask_active_count,
            latent_min=event.latent_min,
            latent_max=event.latent_max,
            latent_mean=event.latent_mean,
            latent_std=event.latent_std,
            original_checksum=event.original_checksum,
            envelope_checksum=event.envelope_checksum,
            reconstructed_checksum=event.reconstructed_checksum,
            grid_bytes_match=event.grid_bytes_match,
            dtype_match=event.dtype_match,
            shape_match=event.shape_match,
            non_grid_fields_match=event.non_grid_fields_match,
            budget_correct=event.budget_correct,
            route_mapped=event.route_mapped,
            original_packet_mutated=event.original_packet_mutated,
            canary_passed=event.canary_passed,
            reason_code=event.reason_code,
            baseline_elapsed_ns=event.baseline_elapsed_ns,
            shadow_elapsed_ns=event.shadow_elapsed_ns,
            shadow_overhead_ns=event.shadow_overhead_ns,
        )

        # Log as structured dict
        try:
            logger.info("%s", enriched.to_json_dict())
        except Exception:
            pass

        # Enqueue — thread-safe, non-blocking
        try:
            q = _get_queue()
            q.put_nowait(enriched)
        except Exception:
            pass

    except Exception:
        # Top-level safety net — must never propagate
        pass


# ---------------------------------------------------------------------------
# Drain / drain helpers
# ---------------------------------------------------------------------------

def drain_events() -> List[CanaryEvent]:
    """Drain all pending events from the thread-safe queue.

    Atomic destructive drain: D(Q_n) = E_n, Q_{n+1} = empty
    (modulo events appended after the drain call begins).

    Each event is consumed exactly once — no duplication, no loss.
    """
    events: List[CanaryEvent] = []
    q = _get_queue()
    while True:
        try:
            events.append(q.get_nowait())
        except queue.Empty:
            break
    return events


def clear_events() -> None:
    """Clear all pending events without returning them."""
    q = _get_queue()
    while True:
        try:
            q.get_nowait()
        except queue.Empty:
            break


def event_count() -> int:
    """Current pending event count (approximate — queue size)."""
    q = _get_queue()
    return q.qsize()


# ---------------------------------------------------------------------------
# Enrichment helper (used by soak runner)
# ---------------------------------------------------------------------------

def enrich_event(
    event: CanaryEvent,
    *,
    run_id: str,
    event_index: int,
    thread_id: int = 0,
) -> CanaryEvent:
    """Enrich a drained event with soak-run metadata.

    Preserves occurrence identity (process_nonce, process_id, sequence)
    from emission time. Recomputes event_id for the new run_id.
    Content checksum is preserved — the enrichment does not change
    content fields (only run_id / event_index which are identity-level).
    """
    new_event_id = (
        f"{run_id}|{event.process_nonce}"
        f"|{event.process_id}|{event.sequence}"
    )
    return CanaryEvent(
        schema_version=event.schema_version,
        process_nonce=event.process_nonce,
        process_id=event.process_id,
        sequence=event.sequence,
        event_id=new_event_id,
        content_checksum=event.content_checksum,
        run_id=run_id,
        event_index=event_index,
        monotonic_ns=event.monotonic_ns,
        thread_id=thread_id,
        route_raw=event.route_raw,
        route_family=event.route_family,
        route_provenance=event.route_provenance,
        legacy_budget=event.legacy_budget,
        budget_axes_granted=event.budget_axes_granted,
        mask_mode=event.mask_mode,
        mask_active_count=event.mask_active_count,
        latent_min=event.latent_min,
        latent_max=event.latent_max,
        latent_mean=event.latent_mean,
        latent_std=event.latent_std,
        original_checksum=event.original_checksum,
        envelope_checksum=event.envelope_checksum,
        reconstructed_checksum=event.reconstructed_checksum,
        grid_bytes_match=event.grid_bytes_match,
        dtype_match=event.dtype_match,
        shape_match=event.shape_match,
        non_grid_fields_match=event.non_grid_fields_match,
        budget_correct=event.budget_correct,
        route_mapped=event.route_mapped,
        original_packet_mutated=event.original_packet_mutated,
        canary_passed=event.canary_passed,
        reason_code=event.reason_code,
        baseline_elapsed_ns=event.baseline_elapsed_ns,
        shadow_elapsed_ns=event.shadow_elapsed_ns,
        shadow_overhead_ns=event.shadow_overhead_ns,
    )


# ---------------------------------------------------------------------------
# Test helpers — reset global state for isolation
# ---------------------------------------------------------------------------

def reset_sequencer() -> None:
    """Reset the global sequencer (for test isolation)."""
    global _sequencer
    _sequencer = None


def reset_queue() -> None:
    """Reset the global event queue (for test isolation)."""
    global _event_queue
    _event_queue = None
