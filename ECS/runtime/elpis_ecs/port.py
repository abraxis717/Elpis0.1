"""Elpis ECS M1A-R1 — entity-bound invocation port (trusted host API).

Sender attribution (M1A-R1 repair)
----------------------------------
The M1A draft exposed ``Kernel.propose(sender_entity_id, receiver, payload)``,
which let any caller with access to the kernel select an arbitrary ACTIVE
entity ID as the sender. That contradicted the "kernel-owned sender
attribution" claim.

M1A-R1 separates the **trusted host/control API** from the **entity-facing
messaging API**:

* ``Kernel.entity_port(entity_id)`` is the **trusted host API**. It is called
  by trusted host/control code (the same code that found the entity). It
  issues an opaque, process-local :class:`EntityPort` bound to exactly one
  entity ID, exactly one live ``Kernel`` instance, and one kernel epoch.

* ``EntityPort.propose(receiver_entity_id, payload)`` is the **entity-facing
  API**. It has **no sender parameter**. The sender is always the entity the
  port is bound to; it is taken from the bound port, never from caller input.

Authority model (explicit, bounded)
-----------------------------------
The port is **process-local mechanical authority only**. It is a Python
object held in the same address space as the kernel. It is NOT a credential,
NOT a token, and NOT cryptographic. No port token appears in canonical events
and it does not affect deterministic replay.

**Explicit nonclaim:** M1A-R1 does NOT isolate hostile Python code that
already possesses the trusted ``Kernel``/control object or can arbitrarily
introspect its internals. The guarantee is API-level attribution for
entity-facing code, not same-address-space adversarial sandboxing.

Rejection semantics
-------------------
* a port used against a kernel instance other than its issuer is rejected
  (``PortKernelMismatchError``);
* a port issued by a previous kernel epoch (after ``close()``/``open()``) is
  rejected (``StalePortError``);
* a port whose bound entity is not ACTIVE at send time is rejected
  (``TerminatedEntityError``);
* the receiver remains an explicit parameter and is validated as before.
"""

from __future__ import annotations

from .errors import (
    PortKernelMismatchError,
    StalePortError,
    TerminatedEntityError,
)
from .entity import ACTIVE


class EntityPort:
    """Opaque process-local entity-bound invocation context.

    Issued ONLY by the trusted host API ``Kernel.entity_port(entity_id)``.
    The port binds exactly one entity ID, exactly one live ``Kernel``
    instance, and one kernel epoch. The entity-facing :meth:`propose` has no
    sender parameter: the sender is always the bound entity.

    This object is process-local mechanical authority only. It is not a
    credential and not cryptographic. See the module docstring for the
    explicit nonclaim about same-address-space adversarial code.
    """

    __slots__ = ("_kernel", "_epoch", "_entity_id")

    def __init__(self, *args, **kwargs):
        raise TypeError("Ports are issued by Kernel.entity_port()")

    @classmethod
    def _issue(cls, kernel, epoch, entity_id):
        port = object.__new__(cls)
        object.__setattr__(port, "_kernel", kernel)
        object.__setattr__(port, "_epoch", epoch)
        object.__setattr__(port, "_entity_id", entity_id)
        return port

    def __setattr__(self, name, value):
        raise AttributeError("EntityPort binding is immutable")

    def __delattr__(self, name):
        raise AttributeError("EntityPort binding is immutable")

    # -- introspection (read-only) ----------------------------------------

    @property
    def entity_id(self) -> str:
        """The entity ID this port is bound to (the only possible sender)."""
        return self._entity_id

    @property
    def epoch(self) -> int:
        """The kernel epoch this port was issued under."""
        return self._epoch

    # -- entity-facing messaging API (NO sender parameter) ---------------

    def propose(self, receiver_entity_id: str, payload: bytes) -> str:
        """Propose ``payload`` to ``receiver_entity_id`` as the bound entity.

        There is **no sender parameter**: the sender is always the entity
        this port is bound to. The kernel validates the bound sender's
        lifecycle (must be ACTIVE), the receiver's deliverability, and the
        mailbox capacity, then durably commits the enqueue.

        Returns the message ID on successful durable enqueue.

        Raises:
            PortKernelMismatchError: port used against a non-issuing kernel.
            StalePortError: port issued by a previous kernel epoch.
            TerminatedEntityError: bound sender is not ACTIVE.
            (plus the usual receiver/mailbox errors)
        """
        return self._kernel._propose_from_port(
            self, receiver_entity_id, payload
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"EntityPort(entity_id={self._entity_id[:12]}..., "
            f"epoch={self._epoch})"
        )


def _check_port_live(port: "EntityPort", kernel) -> None:
    """Shared port liveness checks (kernel identity + epoch).

    Kept here (not on the kernel) so the rejection logic is testable in one
    place. The kernel calls this at the top of every port-driven transition.
    """
    if type(port) is not EntityPort or port._kernel is not kernel:
        raise PortKernelMismatchError(
            "PORT_KERNEL_MISMATCH: port was issued by a different kernel "
            "instance; cross-kernel ports are rejected"
        )
    if port._epoch != kernel._epoch:
        raise StalePortError(
            "STALE_PORT: port was issued by a previous kernel epoch "
            f"(port epoch={port._epoch}, live epoch={kernel._epoch}); "
            "the kernel was closed/reopened"
        )


def _check_sender_active(kernel, entity_id: str) -> None:
    """The bound sender must be ACTIVE at send time."""
    state = kernel._require_state()
    rec = state.registry.get(entity_id)
    if rec.lifecycle != ACTIVE:
        raise TerminatedEntityError(
            f"SENDER_NOT_ACTIVE: {entity_id} (lifecycle={rec.lifecycle})"
        )
