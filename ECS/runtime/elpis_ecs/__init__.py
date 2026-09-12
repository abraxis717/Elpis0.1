"""Elpis ECS M1A-R1 — smallest deterministic same-process ECS substrate.

Integration contract: ECS/design/15-integration-contract.md.

M1A scope:
  1. canonical serialization / domain-separated digest primitives
  2. deterministic entity identity + lifecycle
  3. canonical entity state (immutable logical versions)
  4. deterministic local message envelope (kernel-owned sender attribution
     via entity-bound invocation ports; the entity-facing API has no sender
     parameter)
  5. durable local mailbox semantics (bounded, monotonic watermark)
  6. deterministic scheduler (explicit ordering tuple, no semantic authority)
  7. one authoritative durable event history (recoverable framed append;
     complete-frame recovery semantics — NOT a syscall-level atomic
     transaction)
  8. deterministic replay + crash recovery (fresh-process); the logical
     clock is part of the canonical state root and is verified as exact
     progression during replay
  9. one process-local mutation lock serializing every state transition

DEFERRED (NOT implemented in M1A-R1): cross-process transport, cross-process
authority (UNRESOLVED / DEFERRED), federation, topology ledger, Structural R0
mutation execution, Projector/TRM/DarwinianMatrix integration, Semantic
IR/Grid81, health subsystem, external resource accounting, SAM, new science.

Digests in this package provide CONTENT IDENTITY / INTEGRITY only. They are
NOT authentication and NOT proof of issuer. See ECS/design/13-nonclaims.md.
"""

from __future__ import annotations

__version__ = "0.1.2"

__all__ = [
    "canonical",
    "errors",
    "entity",
    "bus",
    "port",
    "scheduler",
    "persistence",
    "replay",
    "kernel",
]
