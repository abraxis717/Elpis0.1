"""Elpis ECS M1A-R1 — deterministic local message envelope, watermark, mailbox.

Sender attribution (M1A-R1)
---------------------------
The kernel OWNS sender attribution. Entity-facing code holds an
entity-bound invocation port (``EntityPort``) issued by the trusted host API
``Kernel.entity_port(entity_id)``. The entity-facing call is
``port.propose(receiver_entity_id, payload)`` — it has NO sender parameter.
The trusted local kernel constructs and seals the envelope with the ACTUAL
bound entity ID, taken from the port, never from caller-supplied fields.
(Adjudication item 2; M1A-R1 repair of the caller-selectable sender defect.)

The port is process-local mechanical authority only. It is not a credential
and not cryptographic. M1A-R1 does NOT isolate hostile Python code that
already possesses the trusted Kernel/control object; the guarantee is
API-level attribution for entity-facing code, not same-address-space
adversarial sandboxing.

Envelope
--------
The canonical envelope binds: schema/version, message ID, sender entity ID,
receiver entity ID, per-sender sequence, payload bytes, payload digest, and
the envelope logical clock. There is NO security nonce: for deterministic
same-process M1A-R1, the per-sender monotonic sequence is sufficient for
uniqueness and replay ordering. The message ID identifies content/context; it
is NOT an authentication token.

Envelope clock semantics (M1A-R1, exact)
----------------------------------------
The envelope's ``logical_clock`` is the **commit clock** of the enqueue
event: the pre-transition kernel clock + 1, i.e. exactly the ``logical_clock``
of the committed ``MESSAGE_ENQUEUED`` event. It is NOT the pre-enqueue clock.
The message ID is ``f(sender, sequence, receiver, payload_digest)`` and does
NOT include the clock, so message identity does not depend on the clock; the
envelope clock is a consistency field that replay verifies
(``envelope.logical_clock == event.logical_clock``). This is deterministic,
documented, replayed identically, and tested across restart.

Delivery semantics (limited, exact — adjudication item 3)
---------------------------------------------------------
* durable enqueue is a recoverable framed append (length-framed record +
  fsync attempt; complete-frame recovery semantics — NOT a syscall-level
  atomic transaction; see persistence.py);
* each committed message has a monotonically scoped per-sender sequence;
* committed processing of a message is at most once;
* replay of committed history reproduces exactly the committed effects;
* transport-level at-least-once / exactly-once is NOT claimed.

Replay defense is a monotonic per-sender sequence watermark, NOT a bounded
sliding set of message IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from . import canonical
from .limits import MAX_INT, MAX_PAYLOAD_BYTES
from .errors import (
    EnvelopeError,
    ForgedSenderError,
    MailboxFullError,
    MissingReceiverError,
    SequenceRegressionError,
    TerminatedReceiverError,
)
from .entity import ACTIVE, DORMANT, TERMINATED

# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


def payload_digest(payload: bytes) -> str:
    """Digest of raw payload bytes (content identity, not authentication)."""
    if not isinstance(payload, (bytes, bytearray)):
        raise EnvelopeError("PAYLOAD_INVALID: must be bytes")
    return canonical.digest_bytes(bytes(payload))


def message_id(
    sender_entity_id: str,
    sequence: int,
    receiver_entity_id: str,
    payload: bytes,
) -> str:
    """Deterministic message ID.

    Identifies content/context. It is NOT an authentication token and NOT a
    credential. Uniqueness/replay ordering comes from the per-sender sequence,
    not from the ID being unforgeable.
    """
    return canonical.domain_digest(
        canonical.DOMAIN_MESSAGE,
        {
            "sender_entity_id": sender_entity_id,
            "sequence": sequence,
            "receiver_entity_id": receiver_entity_id,
            "payload_digest": payload_digest(payload),
        },
    )


@dataclass(frozen=True)
class Envelope:
    """Canonical local message envelope (kernel-sealed)."""

    schema: str
    message_id: str
    sender_entity_id: str
    receiver_entity_id: str
    sequence: int
    payload: bytes
    payload_digest: str
    logical_clock: int

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "message_id": self.message_id,
            "sender_entity_id": self.sender_entity_id,
            "receiver_entity_id": self.receiver_entity_id,
            "sequence": self.sequence,
            "payload_hex": self.payload.hex(),
            "payload_digest": self.payload_digest,
            "logical_clock": self.logical_clock,
        }

    def canonical_bytes(self) -> bytes:
        return canonical.canonical_bytes(self.to_dict())


def seal_envelope(
    sender_entity_id: str,
    receiver_entity_id: str,
    sequence: int,
    payload: bytes,
    logical_clock: int,
) -> Envelope:
    """Kernel-side envelope construction.

    ``sender_entity_id`` is the trusted kernel-attributed caller identity —
    it is NOT taken from any caller-supplied envelope field.
    """
    if not isinstance(sequence, int) or isinstance(sequence, bool) or not 1 <= sequence <= MAX_INT:
        raise EnvelopeError("SEQUENCE_INVALID: must be a positive int")
    if not isinstance(logical_clock, int) or isinstance(logical_clock, bool) \
            or not 0 <= logical_clock <= MAX_INT:
        raise EnvelopeError("LOGICAL_CLOCK_INVALID: must be a non-negative int")
    if not isinstance(payload, (bytes, bytearray)):
        raise EnvelopeError("PAYLOAD_INVALID: must be bytes")
    payload = bytes(payload)
    if not payload or len(payload) > MAX_PAYLOAD_BYTES:
        raise EnvelopeError("PAYLOAD_INVALID: empty payload")
    pd = payload_digest(payload)
    mid = message_id(sender_entity_id, sequence, receiver_entity_id, payload)
    return Envelope(
        schema=canonical.MESSAGE_SCHEMA,
        message_id=mid,
        sender_entity_id=sender_entity_id,
        receiver_entity_id=receiver_entity_id,
        sequence=sequence,
        payload=payload,
        payload_digest=pd,
        logical_clock=logical_clock,
    )


def verify_envelope(env: Envelope) -> None:
    """Fail-closed structural + content-integrity checks on an envelope.

    These checks verify CONTENT INTEGRITY (self-consistency of the sealed
    fields). They do NOT authenticate origin: the sender identity is bound by
    the kernel at seal time, not proven by these checks.
    """
    if env.schema != canonical.MESSAGE_SCHEMA:
        raise EnvelopeError(f"SCHEMA_MISMATCH: {env.schema!r}")
    if type(env.sequence) is not int or not 1 <= env.sequence <= MAX_INT:
        raise EnvelopeError("SEQUENCE_INVALID")
    if type(env.logical_clock) is not int or not 0 <= env.logical_clock <= MAX_INT:
        raise EnvelopeError("LOGICAL_CLOCK_INVALID")
    if type(env.payload) is not bytes or not 0 < len(env.payload) <= MAX_PAYLOAD_BYTES:
        raise EnvelopeError("PAYLOAD_INVALID: empty or non-bytes")
    # Content integrity: payload digest must match the payload bytes.
    if env.payload_digest != payload_digest(env.payload):
        raise EnvelopeError("PAYLOAD_DIGEST_MISMATCH")
    # Content identity: message ID must match the recomputed ID.
    expected_mid = message_id(
        env.sender_entity_id, env.sequence, env.receiver_entity_id, env.payload
    )
    if env.message_id != expected_mid:
        raise EnvelopeError("MESSAGE_ID_MISMATCH")


# ---------------------------------------------------------------------------
# Per-sender sequence watermark (bounded replay defense)
# ---------------------------------------------------------------------------


class SequenceWatermark:
    """Monotonic per-sender sequence watermark.

    ``watermark[sender]`` = the highest committed sequence observed from that
    sender. A new message is admitted only if its sequence == watermark+1.
    This is bounded (one int per sender) and strictly stronger than a sliding
    set of message IDs for local deterministic senders.
    """

    def __init__(self) -> None:
        self._wm: dict[str, int] = {}

    def next_expected(self, sender: str) -> int:
        return self._wm.get(sender, 0) + 1

    def admit(self, sender: str, sequence: int) -> None:
        """Admit a committed sequence; raise on regression/replay."""
        expected = self._wm.get(sender, 0) + 1
        if type(sequence) is not int or not 1 <= sequence <= MAX_INT or sequence != expected:
            raise SequenceRegressionError(
                f"SEQUENCE_VIOLATION: sender={sender} got seq={sequence} "
                f"expected={expected} (replay or regression rejected)"
            )
        self._wm[sender] = sequence

    def get(self, sender: str) -> int:
        return self._wm.get(sender, 0)

    def as_sorted_dict(self) -> dict[str, int]:
        return {k: self._wm[k] for k in sorted(self._wm)}


# ---------------------------------------------------------------------------
# Mailbox
# ---------------------------------------------------------------------------

DEFAULT_MAILBOX_CAPACITY = 16


@dataclass
class Mailbox:
    """Bounded FIFO mailbox for one receiver (materialized projection).

    Mailbox mutation is represented in committed history (ENQUEUE / DEQUEUE
    events). The in-memory queue is a projection, not an independent source of
    truth.
    """

    receiver_entity_id: str
    capacity: int
    _queue: list[Envelope] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self._queue)

    def is_full(self) -> bool:
        return len(self._queue) >= self.capacity

    def push(self, env: Envelope) -> None:
        if env.receiver_entity_id != self.receiver_entity_id:
            raise EnvelopeError("MAILBOX_RECEIVER_MISMATCH")
        if self.is_full():
            raise MailboxFullError(
                f"MAILBOX_FULL: receiver={self.receiver_entity_id} "
                f"capacity={self.capacity}"
            )
        self._queue.append(env)

    def pop(self) -> Envelope:
        if not self._queue:
            raise EnvelopeError("MAILBOX_EMPTY")
        return self._queue.pop(0)

    def peek(self) -> Envelope | None:
        return self._queue[0] if self._queue else None

    def contents_sorted(self) -> list[dict]:
        """Deterministic serialization for the state root (FIFO order)."""
        return [e.to_dict() for e in self._queue]


class MailboxSet:
    """All mailboxes (materialized projection of committed events)."""

    def __init__(self, capacity: int = DEFAULT_MAILBOX_CAPACITY) -> None:
        self.capacity = capacity
        self._boxes: dict[str, Mailbox] = {}

    def box(self, receiver: str) -> Mailbox:
        if receiver not in self._boxes:
            self._boxes[receiver] = Mailbox(receiver, self.capacity)
        return self._boxes[receiver]

    def has(self, receiver: str) -> bool:
        return receiver in self._boxes

    def as_sorted_list(self) -> list[dict]:
        out = []
        for rid in sorted(self._boxes):
            box = self._boxes[rid]
            out.append({
                "mailbox_key": rid,
                "receiver_entity_id": box.receiver_entity_id,
                "capacity": box.capacity,
                "contents": box.contents_sorted(),
            })
        return out


def check_receiver_deliverable(lifecycle: str) -> None:
    """Fail-closed delivery precondition on the receiver lifecycle."""
    if lifecycle == TERMINATED:
        raise TerminatedReceiverError("RECEIVER_TERMINATED: delivery rejected")
    if lifecycle not in (ACTIVE, DORMANT):
        raise MissingReceiverError(f"RECEIVER_NOT_FOUND_OR_ILLEGAL: {lifecycle}")
