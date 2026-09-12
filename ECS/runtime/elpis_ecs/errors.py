"""Elpis ECS M1A — error hierarchy.

Validation rejection leaves the committed state unchanged. AppendRolledBackError
means the previous file length was restored and fsynced. Other persistence
failures or cancellation may have an indeterminate outcome: the kernel closes,
invalidates ports, and requires recovery. A checkpoint failure does not change
history. Recovery never invents a partially applied transition.
"""

from __future__ import annotations


class EcsError(Exception):
    """Base class for all Elpis ECS M1A errors."""


class CanonicalError(EcsError):
    """Canonical serialization / digest failure (non-serializable, malformed)."""


class EntityError(EcsError):
    """Entity identity / lifecycle / state failure."""


class DuplicateEntityError(EntityError):
    """A duplicate active (or existing) entity identity was founded."""


class InvalidTransitionError(EntityError):
    """An illegal lifecycle transition was attempted."""


class TerminatedEntityError(EntityError):
    """An operation targeted a TERMINATED (terminal) entity."""


class EnvelopeError(EcsError):
    """Message envelope construction / validation failure."""


class ForgedSenderError(EnvelopeError):
    """A sender identity was not the trusted kernel-attributed caller."""


class PortError(EcsError):
    """Entity invocation port failure (stale, cross-kernel, closed kernel)."""


class StalePortError(PortError):
    """A port issued by a previous kernel epoch (close/reopen) was used."""


class PortKernelMismatchError(PortError):
    """A port was used against a kernel instance other than its issuer."""


class SequenceRegressionError(EnvelopeError):
    """A per-sender sequence regressed or replayed (not watermark+1)."""


class MailboxError(EcsError):
    """Mailbox capacity / delivery failure."""


class MailboxFullError(MailboxError):
    """The receiver mailbox is at hard capacity; enqueue rejected."""


class MissingReceiverError(MailboxError):
    """The receiver entity does not exist in the registry."""


class TerminatedReceiverError(MailboxError):
    """The receiver entity is TERMINATED; delivery rejected."""


class SchedulerError(EcsError):
    """Scheduler failure (should not occur for a well-formed ready set)."""


class PersistenceError(EcsError):
    """Event-log / checkpoint I/O or integrity failure."""


class CorruptEventError(PersistenceError):
    """A committed event record failed integrity verification."""


class BrokenChainError(PersistenceError):
    """prev_event_digest / event_index chain is broken."""


class TruncatedLogError(PersistenceError):
    """The event log has an incomplete trailing record (pre-commit crash)."""


class CorruptCheckpointError(PersistenceError):
    """A checkpoint failed verification and was rejected."""


class ReplayError(EcsError):
    """Replay could not reconstruct a consistent state."""


class WrongAuthorityError(ReplayError):
    """Replay was given a wrong genesis / authority input."""
