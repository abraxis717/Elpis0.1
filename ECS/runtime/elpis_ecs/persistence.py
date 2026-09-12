"""Elpis ECS M1A-R1 — one authoritative durable event history.

Design (per adjudication item 4 and the persistence specialist):
  * ONE canonical commit history is the single source of truth.
  * Every other piece of kernel state (entity registry, mailboxes, watermarks,
    scheduler state) is a MATERIALIZED PROJECTION of that history, fully
    reconstructable by replay. No independent durable mutable state.
  * One logical transition = ONE event record = ONE durable framed append.

Recoverable framed append (M1A-R1 terminology correction)
---------------------------------------------------------
The M1A draft documentation described the append as a single syscall-level
atomic write/transaction. That overclaims: the append performs a length-framed
write loop (``os.write`` may return a short count) followed by ``fsync``, and
ordinary regular-file writes + fsync do NOT provide a universal atomic
transaction primitive under all crashes/power failures.

The property M1A-R1 actually has, and the only one claimed:

  * **length-framed append**: 8-byte big-endian uint64 length prefix +
    canonical JSON payload;
  * **durability boundary**: the framed record is written (looping until all
    bytes are written or the write fails closed) and then ``fsync`` must
    succeed before a successful mutation return;
  * **complete-frame recovery semantics**: on recovery, the log is parsed
    frame by frame. A complete valid frame is replayed. An incomplete
    trailing frame (crash mid-append) is detectable and is recoverably
    truncated, yielding the last complete valid event prefix. A complete
    frame whose JSON is malformed or whose event fails integrity
    verification fails closed.

Consequences (stated precisely, no syscall-atomicity claim):
  * **process crash**: recovery yields the last complete valid event prefix;
    it never produces a hybrid logical transition;
  * a crash between completion of the write and return from ``fsync`` may
    legitimately observe either the old prefix or the new complete frame,
    depending on the underlying filesystem/kernel state. No stronger claim
    is made.
  * physical power-loss semantics beyond the tested filesystem contract
    remain a nonclaim.

Integrity / tamper evidence (NOT authentication — adjudication item 1):
  * each event binds event_index, logical_clock, prev_event_digest,
    before/after state roots, and a self event_digest;
  * the chain verifies position, exact clock progression, and effect
    relative to its trusted genesis authority;
  * this is integrity/tamper evidence, NOT cryptographic authentication of
    issuer. Stated explicitly.
"""

from __future__ import annotations

import json
import os
import struct
import threading
import fcntl
from functools import wraps

from .limits import MAX_INT, MAX_FRAME_BYTES, MAX_PAYLOAD_BYTES, MAX_STRING_BYTES, PROTOCOL
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from . import canonical
from .errors import (
    BrokenChainError,
    CorruptCheckpointError,
    CorruptEventError,
    PersistenceError,
    TruncatedLogError,
    WrongAuthorityError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LENGTH_PREFIX = struct.Struct(">Q")  # 8-byte big-endian uint64
GENESIS_PREV_DIGEST = "0" * 64  # sentinel prev digest for the genesis event
GENESIS_TRANSACTION_ID = "GENESIS"
GENESIS_KIND = "GENESIS"

# v3 also binds event-history inputs, full identity metadata and mailbox
# defaults. Older v1/v2 histories are intentionally rejected, never reinterpreted.
STATE_ROOT_SCHEMA = "ecs.state_root.v3"


# ---------------------------------------------------------------------------
# State root
# ---------------------------------------------------------------------------


def build_state_root(
    genesis_digest: str,
    logical_clock: int,
    entities: list[dict],
    mailboxes: list[dict],
    watermarks: Mapping[str, int],
    next_founding_index: int,
    mailbox_capacity: int,
    scheduler_state: Mapping[str, Any] | None = None,
    history_digest: str = GENESIS_PREV_DIGEST,
    mailbox_default_capacity: int | None = None,
) -> dict:
    """Build the deterministic kernel-state root record (integration v3).

    Covers ALL M1A-R1 logical state that affects future behavior:
      * the trusted genesis authority (``genesis_digest``) — constant across
        all events; binds the state to its starting authority (wrong genesis
        -> wrong initial root -> replay fails closed);
      * the current ``logical_clock`` — a transition is EXPECTED to change
        before_root -> after_root; roots are not required to remain equal
        across a transition;
      * ``next_founding_index`` — determines the next entity identity;
      * ``mailbox_capacity`` — changes future enqueue acceptance; immutable
        for the life of one durable history (see Kernel.open);
      * entity registry/lifecycle + canonical states (``entities``);
      * mailbox contents (``mailboxes``);
      * sender sequence/watermark state (``watermarks``);
      * scheduler-relevant deterministic state (``scheduler_state``; empty in
        M1A-R1 because the scheduler is a pure function of the mailboxes).

    No non-semantic / logging noise is included.
    """
    if scheduler_state is None:
        scheduler_state = {}
    return {
        "schema": STATE_ROOT_SCHEMA,
        "history_digest": history_digest,
        "mailbox_default_capacity": mailbox_capacity if mailbox_default_capacity is None else mailbox_default_capacity,
        "genesis_digest": genesis_digest,
        "logical_clock": logical_clock,
        "next_founding_index": next_founding_index,
        "mailbox_capacity": mailbox_capacity,
        "entities": entities,
        "mailboxes": mailboxes,
        "watermarks": {k: watermarks[k] for k in sorted(watermarks)},
        "scheduler_state": dict(scheduler_state),
    }


def state_root_digest(root: Mapping[str, Any]) -> str:
    """Digest of the state root record (content identity, not auth)."""
    return canonical.domain_digest(canonical.DOMAIN_STATE_ROOT, dict(root))


def empty_state_root(
    genesis_digest: str,
    mailbox_capacity: int,
) -> dict:
    """The initial (pre-founding) state root for a given genesis authority.

    The mailbox capacity is bound: opening an empty new kernel with capacity
    1 versus capacity 64 produces different initial state roots.
    """
    return build_state_root(
        genesis_digest=genesis_digest,
        logical_clock=0,
        entities=[],
        mailboxes=[],
        watermarks={},
        next_founding_index=0,
        mailbox_capacity=mailbox_capacity,
    )


# ---------------------------------------------------------------------------
# Event record
# ---------------------------------------------------------------------------


def genesis_descriptor_digest(genesis_label: str) -> str:
    """Domain-separated digest of the genesis descriptor (trusted authority)."""
    if not isinstance(genesis_label, str) or not genesis_label or len(genesis_label.encode("utf-8")) > MAX_STRING_BYTES:
        raise PersistenceError("GENESIS_LABEL_INVALID")
    return canonical.domain_digest(
        canonical.DOMAIN_GENESIS,
        {"schema_version": canonical.SCHEMA_VERSION, "genesis_label": genesis_label, "protocol": PROTOCOL},
    )


def build_event(
    event_index: int,
    logical_clock: int,
    transaction_id: str,
    event_kind: str,
    entity_id: str | None,
    payload: Mapping[str, Any],
    before_state_root: str,
    after_state_root: str,
    prev_event_digest: str,
) -> dict:
    """Build a committed event record and compute its self digest.

    The event carries the full ``payload`` (canonical JSON) so that replay can
    reconstruct state without any side channel. ``payload_digest`` is bound for
    content integrity; the chain is integrity/tamper evidence, NOT
    authentication.
    """
    payload_digest = canonical.digest(dict(payload))
    body = {
        "schema": canonical.EVENT_SCHEMA,
        "event_index": event_index,
        "logical_clock": logical_clock,
        "transaction_id": transaction_id,
        "event_kind": event_kind,
        "entity_id": entity_id,
        "payload": dict(payload),
        "payload_digest": payload_digest,
        "before_state_root": before_state_root,
        "after_state_root": after_state_root,
        "prev_event_digest": prev_event_digest,
    }
    event_digest = canonical.domain_digest(canonical.DOMAIN_EVENT, body)
    return {**body, "event_digest": event_digest}


def event_intent_digest(event):
    """Bind the complete history without a state-root/event-digest cycle.

    The current event's after root and self digest are outputs. All its inputs
    (including previous event digest and before root) enter this commitment.
    The after root binds this commitment; the self digest then binds both.
    """
    return canonical.domain_digest("ecs.event.intent.v1", {
        key: value for key, value in event.items()
        if key not in {"event_digest", "after_state_root"}
    })


def verify_event_self_digest(event: Mapping[str, Any]) -> None:
    """Recompute and check an event's self digest (content integrity)."""
    body = {k: v for k, v in event.items() if k != "event_digest"}
    expected = canonical.domain_digest(canonical.DOMAIN_EVENT, body)
    if event.get("event_digest") != expected:
        raise CorruptEventError("EVENT_DIGEST_MISMATCH")


def _require_int(value: Any, field: str, minimum: int = 0) -> int:
    """Bounded deterministic integer check.

    Rejects Python ``bool`` where integer semantics are intended (bool is a
    subclass of int in Python and would otherwise masquerade as 0/1).
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise CorruptEventError(
            f"EVENT_FIELD_TYPE: {field} must be an int, got {type(value).__name__}"
        )
    if value < minimum or value > MAX_INT:
        raise CorruptEventError(
            f"EVENT_FIELD_RANGE: {field} must be >= {minimum}, got {value}"
        )
    return value


def _require_digest(value: Any, field: str) -> str:
    """Bounded deterministic 64-hex digest check."""
    if not isinstance(value, str) or len(value) != 64:
        raise CorruptEventError(
            f"EVENT_FIELD_TYPE: {field} must be a 64-hex digest string"
        )
    if any(c not in "0123456789abcdef" for c in value):
        raise CorruptEventError(f"NONCANONICAL_DIGEST: {field}")
    return value


def verify_event_fields(event: Mapping[str, Any], index: int) -> None:
    """Bounded deterministic type/range validation of one event record.

    Validates (M1A-R1 hardening):
      * schema (exact string);
      * event_index (int, non-bool, == position);
      * logical_clock (int, non-bool, non-negative; exact progression is
        checked by verify_event_chain);
      * transaction_id (non-empty str);
      * event_kind (non-empty str);
      * entity_id (None or str — the nullable/string contract);
      * payload (dict);
      * payload_digest (64-hex, and must equal the recomputed digest);
      * before_state_root / after_state_root (64-hex);
      * prev_event_digest (64-hex);
      * event_digest (64-hex, self-consistent).
    """
    expected_fields = {"schema", "event_index", "logical_clock", "transaction_id",
                       "event_kind", "entity_id", "payload", "payload_digest",
                       "before_state_root", "after_state_root", "prev_event_digest", "event_digest"}
    if type(event) is not dict or set(event) != expected_fields:
        raise CorruptEventError("EVENT_FIELDS_MISMATCH")
    if len(canonical.canonical_bytes(event)) > MAX_FRAME_BYTES:
        raise CorruptEventError("EVENT_TOO_LARGE")
    validate_payload(event)
    if event.get("schema") != canonical.EVENT_SCHEMA:
        raise CorruptEventError(f"EVENT_SCHEMA_MISMATCH: index={index}")
    _require_int(event.get("event_index"), "event_index")
    if event.get("event_index") != index:
        raise BrokenChainError(
            f"EVENT_INDEX_MISMATCH: expected={index} got={event.get('event_index')}"
        )
    _require_int(event.get("logical_clock"), "logical_clock")
    if not isinstance(event.get("transaction_id"), str) or not event.get("transaction_id"):
        raise CorruptEventError("EVENT_FIELD_TYPE: transaction_id must be a non-empty str")
    if not isinstance(event.get("event_kind"), str) or not event.get("event_kind"):
        raise CorruptEventError("EVENT_FIELD_TYPE: event_kind must be a non-empty str")
    entity_id = event.get("entity_id")
    if entity_id is not None and not isinstance(entity_id, str):
        raise CorruptEventError("EVENT_FIELD_TYPE: entity_id must be None or str")
    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise CorruptEventError("EVENT_FIELD_TYPE: payload must be a mapping")
    # payload_digest must be a 64-hex string AND match the recomputed digest.
    _require_digest(event.get("payload_digest"), "payload_digest")
    if event.get("payload_digest") != canonical.digest(payload):
        raise CorruptEventError("PAYLOAD_DIGEST_MISMATCH")
    _require_digest(event.get("before_state_root"), "before_state_root")
    _require_digest(event.get("after_state_root"), "after_state_root")
    _require_digest(event.get("prev_event_digest"), "prev_event_digest")
    _require_digest(event.get("event_digest"), "event_digest")
    verify_event_self_digest(event)


def verify_event_link(event, index, previous_digest=GENESIS_PREV_DIGEST,
                      previous_after_root=None):
    """Shared authoritative structural/chain validator, also used on append."""
    verify_event_fields(event, index)
    if event["logical_clock"] != index + 1:
        raise BrokenChainError("CLOCK_PROGRESSION_VIOLATION")
    if event["prev_event_digest"] != previous_digest:
        raise BrokenChainError("BROKEN_PREV_DIGEST")
    if previous_after_root is not None and event["before_state_root"] != previous_after_root:
        raise BrokenChainError("STATE_ROOT_DISCONTINUITY")


def verify_event_chain(events: Sequence[Mapping[str, Any]]) -> None:
    """Verify every event's exact schema, index, clock, digests and root link."""
    previous_digest, previous_root = GENESIS_PREV_DIGEST, None
    for index, event in enumerate(events):
        verify_event_link(event, index, previous_digest, previous_root)
        previous_digest, previous_root = event["event_digest"], event["after_state_root"]


def _keys(obj, expected):
    if type(obj) is not dict or set(obj) != set(expected):
        raise CorruptEventError("SEMANTIC_FIELDS_MISMATCH")


def _string(value):
    if type(value) is not str or not value:
        raise CorruptEventError("STRING_INVALID")
    try:
        if len(value.encode("utf-8")) <= MAX_STRING_BYTES:
            return
    except UnicodeError:
        pass
    raise CorruptEventError("STRING_TOO_LARGE_OR_INVALID")


def validate_payload(ev):
    kind, payload, eid = ev["event_kind"], ev["payload"], ev["entity_id"]
    _string(kind)
    _require_digest(eid, "entity_id")
    _string(ev["transaction_id"])
    if kind == "ENTITY_FOUNDED":
        _keys(payload, ["label", "founding_index", "founding_digest"])
        _string(payload["label"])
        _require_int(payload["founding_index"], "founding_index")
        _require_digest(payload["founding_digest"], "founding_digest")
        tx = f"FOUND:{eid}"
    elif kind in {"ENTITY_ACTIVATED", "ENTITY_DORMANT", "ENTITY_REACTIVATED", "ENTITY_TERMINATED"}:
        _keys(payload, ["from", "to"])
        if payload["from"] not in ("FOUNDED", "ACTIVE", "DORMANT") or payload["to"] not in ("ACTIVE", "DORMANT", "TERMINATED"):
            raise CorruptEventError("LIFECYCLE_INVALID")
        tx = f"{kind}:{eid}"
    elif kind == "MESSAGE_ENQUEUED":
        _keys(payload, ["envelope"])
        env = payload["envelope"]
        _keys(env, ["schema", "message_id", "sender_entity_id", "receiver_entity_id", "sequence", "payload_hex", "payload_digest", "logical_clock"])
        if env["schema"] != canonical.MESSAGE_SCHEMA:
            raise CorruptEventError("ENVELOPE_SCHEMA")
        for field in ("message_id", "sender_entity_id", "receiver_entity_id", "payload_digest"):
            _require_digest(env[field], field)
        _require_int(env["sequence"], "sequence", 1)
        _require_int(env["logical_clock"], "envelope.clock", 1)
        raw = env["payload_hex"]
        if type(raw) is not str or not 0 < len(raw) <= 2 * MAX_PAYLOAD_BYTES or len(raw) % 2 or any(c not in "0123456789abcdef" for c in raw):
            raise CorruptEventError("PAYLOAD_HEX_INVALID")
        tx = f"ENQ:{env['message_id']}"
    elif kind == "MESSAGE_PROCESSED":
        _keys(payload, ["message_id", "receiver_entity_id"])
        for field in payload:
            _require_digest(payload[field], field)
        tx = f"PROC:{payload['message_id']}"
    else:
        raise CorruptEventError("UNKNOWN_EVENT_KIND")
    if ev["transaction_id"] != tx:
        raise CorruptEventError("TRANSACTION_ID_MISMATCH")


def _locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


def _fsync(fd):
    while True:
        try:
            os.fsync(fd)
            return
        except InterruptedError:
            continue


def _sync_directory(path):
    fd = os.open(path or ".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        _fsync(fd)
    finally:
        os.close(fd)


def _pread_exact(fd, count, offset):
    chunks = []
    while count:
        try:
            chunk = os.pread(fd, count, offset)
        except InterruptedError:
            continue
        if not chunk:
            raise CorruptEventError("UNEXPECTED_EOF_DURING_READ")
        chunks.append(chunk)
        count -= len(chunk)
        offset += len(chunk)
    return b"".join(chunks)


def _write_all(fd, data):
    view = memoryview(data)
    while view:
        try:
            n = os.write(fd, view)
        except InterruptedError:
            continue
        if n <= 0:
            raise PersistenceError("WRITE_STALLED")
        view = view[n:]


class AppendRolledBackError(PersistenceError):
    """Append failed; old file length was restored and fsynced."""


class EventLog:
    """Exclusive file owner. Lock order: Kernel -> EventLog; no upward calls.

    Recovery is explicit and only available before finish_recovery(). Live
    inspection never truncates. flock prevents a second open file owner,
    including aliases; it supplies exclusion, not cross-process identity.
    """
    def __init__(self, path):
        self.path = path
        self._fd = None
        self._lock = threading.RLock()
        self._recovering = False
        self._tail = None
        self._count = 0
        self._head = GENESIS_PREV_DIGEST
        self._after_root = None
        self._size = 0
        self._scanned = False

    @_locked
    def open(self):
        if self._fd is not None:
            return self._fd
        directory = os.path.dirname(os.path.abspath(self.path))
        # Persist newly-created directory entries from child through existing parent.
        missing = []
        current = directory
        while not os.path.exists(current):
            missing.append(current)
            current = os.path.dirname(current)
        os.makedirs(directory, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _sync_directory(directory)
            for entry in missing:
                _sync_directory(os.path.dirname(entry))
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        self._recovering = True
        self._scanned = False
        return fd

    @_locked
    def close(self):
        if self._fd is not None:
            fd, self._fd = self._fd, None
            os.close(fd)
        self._recovering = False

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()

    @_locked
    def read_events(self, *, recovery=False):
        if self._fd is None:
            raise PersistenceError("LOG_NOT_OPEN")
        if recovery and not self._recovering:
            raise PersistenceError("RECOVERY_NOT_ALLOWED_LIVE")
        # Stream bounded frames. Memory use scales with valid history, never
        # with an untrusted length prefix or concatenated whole-file buffer.
        events = []
        offset = 0
        size = os.fstat(self._fd).st_size
        while offset < size:
            header = _pread_exact(self._fd, min(8, size - offset), offset)
            if len(header) < 8:
                _validate_partial_header(header)
                break
            length = LENGTH_PREFIX.unpack(header)[0]
            _validate_length(length)
            if size - offset - 8 < length:
                break
            payload = _pread_exact(self._fd, length, offset + 8)
            if len(payload) != length:
                raise CorruptEventError("FILE_CHANGED_DURING_READ")
            event = _decode_record(payload)
            verify_event_link(event, len(events),
                              events[-1]["event_digest"] if events else GENESIS_PREV_DIGEST,
                              events[-1]["after_state_root"] if events else None)
            events.append(event)
            offset += 8 + length
        if offset != size and not recovery:
            raise TruncatedLogError("INCOMPLETE_LIVE_TAIL")
        if recovery:
            self._tail = offset if offset != size else None
            self._count = len(events)
            self._after_root = events[-1]["after_state_root"] if events else None
            self._size = offset
            self._scanned = True
            self._head = events[-1]["event_digest"] if events else GENESIS_PREV_DIGEST
        elif len(events) != self._count or (events[-1]["event_digest"] if events else GENESIS_PREV_DIGEST) != self._head:
            raise CorruptEventError("LOG_CHANGED_OUTSIDE_OWNER")
        return events

    @_locked
    def finish_recovery(self):
        if not self._recovering or not self._scanned:
            raise PersistenceError("RECOVERY_SCAN_REQUIRED")
        if self._tail is not None:
            self._truncate_to(self._fd, self._tail)
        self._recovering = False
        self._tail = None

    @_locked
    def append_event(self, event):
        """Durable recoverable framed append; no syscall-atomicity claim.

        On ordinary I/O failure restore and fsync the previous file length.
        If rollback fails the outcome is indeterminate; the owner must close.
        """
        if self._fd is None or self._recovering:
            raise PersistenceError("LOG_NOT_READY")
        verify_event_link(event, self._count, self._head, self._after_root)
        payload = canonical.canonical_bytes(event)
        start = os.fstat(self._fd).st_size
        if start != self._size:
            raise CorruptEventError("LOG_SIZE_CHANGED_OUTSIDE_OWNER")
        try:
            _write_all(self._fd, LENGTH_PREFIX.pack(len(payload)) + payload)
            _fsync(self._fd)
        except Exception as exc:
            try:
                self._truncate_to(self._fd, start)
            except BaseException:
                self.close()
                raise PersistenceError("APPEND_OUTCOME_INDETERMINATE: reopen required") from exc
            raise AppendRolledBackError("APPEND_ROLLED_BACK") from exc
        except BaseException:
            self.close()
            raise
        self._count += 1
        self._head = event["event_digest"]
        self._after_root = event["after_state_root"]
        self._size = start + 8 + len(payload)

    def _truncate_to(self, fd, offset):
        os.ftruncate(fd, offset)
        _fsync(fd)

    @_locked
    def head_event_digest(self):
        return self._head

    @_locked
    def event_count(self):
        return self._count


def _validate_length(length):
    if not 1 <= length <= MAX_FRAME_BYTES:
        raise CorruptEventError("FRAME_LENGTH_INVALID")


def _validate_partial_header(header):
    # A partial prefix is residue only if some legal frame length completes it.
    low = int.from_bytes(header + bytes(8 - len(header)), "big")
    high = low + (1 << (8 * (8 - len(header)))) - 1
    if low > MAX_FRAME_BYTES or high < 1:
        raise CorruptEventError("IMPOSSIBLE_PARTIAL_LENGTH")


def _decode_record(payload):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    try:
        obj = json.loads(payload.decode("utf-8"), object_pairs_hook=pairs)
        if type(obj) is not dict or canonical.canonical_bytes(obj) != payload:
            raise ValueError("noncanonical record")
        return obj
    except (ValueError, UnicodeError, RecursionError, canonical.CanonicalError) as exc:
        raise CorruptEventError("CORRUPT_RECORD") from exc


def _parse_records(data):
    events, offset = [], 0
    while offset < len(data):
        if len(data) - offset < 8:
            _validate_partial_header(data[offset:])
            break
        length = LENGTH_PREFIX.unpack_from(data, offset)[0]
        _validate_length(length)
        if len(data) - offset - 8 < length:
            break
        events.append(_decode_record(data[offset + 8:offset + 8 + length]))
        offset += 8 + length
    return events, offset


# ---------------------------------------------------------------------------
# Checkpoint (optimization, NOT an alternate authority)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Checkpoint:
    """Advisory history marker, never a projection or alternate authority.

    v1 contains no state snapshot and offers no replay acceleration. It remains
    accepted for compatibility with local tooling; full replay always runs.
    """

    event_index: int
    event_digest: str
    state_root_digest: str
    logical_clock: int

    def to_dict(self) -> dict:
        return {
            "schema": "ecs.checkpoint.v1",
            "event_index": self.event_index,
            "event_digest": self.event_digest,
            "state_root_digest": self.state_root_digest,
            "logical_clock": self.logical_clock,
        }


def checkpoint_digest(cp: Mapping[str, Any]) -> str:
    return canonical.domain_digest(canonical.DOMAIN_CHECKPOINT, dict(cp))


def verify_checkpoint_fields(cp: Mapping[str, Any]) -> None:
    """Bounded deterministic type/range validation of a checkpoint record.

    M1A-R1: the checkpoint's fields must be mutually consistent in type. The
    cross-field agreement with the replayed state (root, clock, event digest)
    is checked by the replay layer (replay.py); this function checks the
    record's own field types so a malformed checkpoint is rejected cleanly.
    """
    _keys(cp, ["schema", "event_index", "logical_clock", "event_digest", "state_root_digest", "checkpoint_digest"])
    if cp.get("schema") != "ecs.checkpoint.v1":
        raise CorruptCheckpointError("CHECKPOINT_SCHEMA_MISMATCH")
    _require_int(cp.get("event_index"), "checkpoint.event_index")
    _require_int(cp.get("logical_clock"), "checkpoint.logical_clock")
    _require_digest(cp.get("event_digest"), "checkpoint.event_digest")
    _require_digest(cp.get("state_root_digest"), "checkpoint.state_root_digest")


class CheckpointStore:
    """Writes/reads a single checkpoint file (optimization only)."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.RLock()

    @_locked
    def write(self, cp: Checkpoint) -> None:
        record = cp.to_dict()
        record["checkpoint_digest"] = checkpoint_digest(record)
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        payload = canonical.canonical_bytes(record)
        framed = LENGTH_PREFIX.pack(len(payload)) + payload
        verify_checkpoint_fields(record)
        tmp = self.path + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            _write_all(fd, framed)
            _fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, self.path)
        _sync_directory(directory)

    @_locked
    def read(self) -> Checkpoint | None:
        """Read and verify the checkpoint; return None if absent/corrupt.

        A corrupt checkpoint is rejected (returns None) so the caller falls
        back to full replay. This is explicit and deterministic.
        """
        if not os.path.exists(self.path):
            return None
        try:
            with open(self.path, "rb") as fh:
                data = fh.read(MAX_FRAME_BYTES + 9)
            events, consumed = _parse_records(data)
            if len(events) != 1 or consumed != len(data):
                return None
            record = events[0]
            if record.get("schema") != "ecs.checkpoint.v1":
                return None
            body = {k: v for k, v in record.items() if k != "checkpoint_digest"}
            if record.get("checkpoint_digest") != checkpoint_digest(body):
                return None
            verify_checkpoint_fields(record)
            return Checkpoint(
                event_index=record["event_index"],
                event_digest=record["event_digest"],
                state_root_digest=record["state_root_digest"],
                logical_clock=record["logical_clock"],
            )
        except (OSError, CorruptEventError, CorruptCheckpointError,
                KeyError, ValueError):
            return None
