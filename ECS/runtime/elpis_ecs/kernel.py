"""Elpis ECS M1A-R1 — kernel composition root.

The kernel is the trusted local authority. It:
  * owns sender attribution via entity-bound invocation ports (the
    entity-facing API has NO sender parameter; the sender is taken from the
    bound port, never from caller input);
  * performs committed transitions through ONE centralized transition
    boundary (``_commit``) that owns the before/after root computation, the
    logical-clock increment, the durable framed append, and the projection
    install;
  * maintains the in-memory projection of the committed history;
  * exposes deterministic replay and crash recovery;
  * serializes every state transition with one process-local mutation lock
    (same-process concurrent mutation cannot corrupt event ordering).

The kernel is SAME-PROCESS only (M1A-R1). There is no cross-process transport
or cross-process authority (UNRESOLVED / DEFERRED).

API boundary (M1A-R1)
---------------------
TRUSTED HOST / CONTROL API (called by trusted host code):
  Kernel.open(dir)            -> fresh or recovered kernel
  Kernel.entity_port(entity_id) -> EntityPort   (issues a bound port)
  Kernel.found_entity(label)  -> entity_id
  Kernel.activate(entity_id)
  Kernel.dormant(entity_id)
  Kernel.reactivate(entity_id)
  Kernel.terminate(entity_id)
  Kernel.step()               -> run one deterministic scheduler pass
  Kernel.run_until_quiescent(max_steps)
  Kernel.close()

ENTITY-FACING API (no sender parameter; sender is the bound port's entity):
  EntityPort.propose(receiver_entity_id, payload) -> message_id

READ-ONLY INTROSPECTION (serialized at a transition boundary):
  Kernel.state_root_digest()
  Kernel.events()
  Kernel.entity_ids()
  Kernel.mailbox_size(receiver)

Concurrency contract (M1A-R1)
-----------------------------
Every state transition (state read through durable append through projection
install) occurs under one process-local ``threading.RLock``. The deterministic
scheduler remains single-threaded. Read-only introspection uses the same lock.

Same-process security nonclaim (M1A-R1)
---------------------------------------
M1A-R1 does NOT isolate hostile Python code that already possesses the
trusted Kernel/control object or can arbitrarily introspect its internals.
The guarantee is API-level attribution for entity-facing code, not
same-address-space adversarial sandboxing.
"""

from __future__ import annotations

import os
import threading
from functools import wraps

from .limits import MAX_INT
from .persistence import AppendRolledBackError
from typing import Any, Mapping

from . import canonical
from .bus import (
    DEFAULT_MAILBOX_CAPACITY,
    Envelope,
    MailboxSet,
    SequenceWatermark,
    check_receiver_deliverable,
    seal_envelope,
    verify_envelope,
)
from .entity import (
    ACTIVE,
    DORMANT,
    FOUNDED,
    TERMINATED,
    EntityRecord,
    EntityRegistry,
    EntityStateVersion,
    entity_id_from_founding,
    founding_record,
    initial_state_digest,
    make_state_version,
    validate_transition,
)
from .errors import (
    DuplicateEntityError,
    EcsError,
    EntityError,
    MailboxFullError,
    MissingReceiverError,
    PersistenceError,
    TerminatedEntityError,
    TerminatedReceiverError,
    WrongAuthorityError,
)
from .persistence import (
    GENESIS_PREV_DIGEST,
    Checkpoint,
    CheckpointStore,
    EventLog,
    build_event,
    event_intent_digest,
    build_state_root,
    empty_state_root,
    genesis_descriptor_digest,
    state_root_digest,
)
from .port import EntityPort, _check_port_live, _check_sender_active
from .replay import KernelState, replay_from_events, replay_with_checkpoint
from .scheduler import ReadyItem, RANK_ACTIVATE, RANK_ENQUEUE, order_ready

LOG_FILENAME = "events.log"
CHECKPOINT_FILENAME = "checkpoint.bin"

# Event kinds that transition an entity's logical state (bump its state
# version). These are the kinds whose causing_event_id must be bound to the
# real event digest in the post-transition state. MESSAGE_ENQUEUED does NOT
# bump the receiver's version (it only mutates the mailbox + watermark), so it
# is excluded.
_STATE_TRANSITION_KINDS = frozenset({
    "ENTITY_FOUNDED",
    "ENTITY_ACTIVATED",
    "ENTITY_DORMANT",
    "ENTITY_REACTIVATED",
    "ENTITY_TERMINATED",
    "MESSAGE_PROCESSED",
})


def _serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._mutation_lock:
            return method(self, *args, **kwargs)
    return call


class Kernel:
    """The trusted same-process ECS kernel (M1A-R1)."""

    def __init__(
        self,
        storage_dir: str,
        genesis_label: str = "ecs-m1a-genesis",
        mailbox_capacity: int = DEFAULT_MAILBOX_CAPACITY,
    ) -> None:
        if isinstance(mailbox_capacity, bool) or not isinstance(
            mailbox_capacity, int
        ) or not 1 <= mailbox_capacity <= MAX_INT:
            raise PersistenceError(
                "MAILBOX_CAPACITY_INVALID: must be a positive int"
            )
        self.storage_dir = storage_dir
        self._genesis_label = genesis_label
        # Mailbox capacity is AUTHORITATIVE CONFIGURATION in M1A-R1: it is
        # immutable for the life of one durable history and is bound into the
        # state root. Opening an existing non-empty history with a different
        # capacity fails state-root/genesis authority reconciliation.
        self._mailbox_capacity = mailbox_capacity
        self.log_path = os.path.join(storage_dir, LOG_FILENAME)
        self.cp_path = os.path.join(storage_dir, CHECKPOINT_FILENAME)
        self._log = EventLog(self.log_path)
        self._checkpoints = CheckpointStore(self.cp_path)
        self._state: KernelState | None = None
        self._genesis_digest = genesis_descriptor_digest(genesis_label)
        # Kernel epoch: incremented on every successful open() and on close().
        # Entity ports bind to an epoch; a port from a previous epoch is stale.
        self._epoch = 0
        self._opened = False
        # One process-local mutation lock: every state transition (state read
        # through durable append through projection install) occurs under it.
        self._mutation_lock = threading.RLock()

    @property
    def mailbox_capacity(self):
        return self._mailbox_capacity

    @property
    def genesis_label(self):
        return self._genesis_label

    @property
    def state(self):
        """Detached snapshot; modifying it never changes the live kernel."""
        with self._mutation_lock:
            return _clone_state(self._require_state())

    # ------------------------------------------------------------------
    # Open / recover
    # ------------------------------------------------------------------

    def open(self) -> "Kernel":
        """Exclusively open, validate full history, then recover crash debris.

        Checkpoint markers never bypass validation. Any failure releases the
        file owner and leaves the kernel closed. Every open attempt changes
        the process-local epoch and invalidates previously issued ports.
        Nonempty history must match genesis and all behavior configuration.
        """
        with self._mutation_lock:
            # Bump the epoch up front: a failed open still invalidates ports
            # from any previous epoch.
            self._epoch += 1
            self._opened = False
            self._state = None
            try:
                self._log.close()
                self._log.open()
                events = self._log.read_events(recovery=True)
                cp = self._checkpoints.read()
                state = replay_with_checkpoint(
                    self._genesis_digest, events, cp.to_dict() if cp else None,
                    self.mailbox_capacity)
                # Only after ALL historical semantics validate may crash debris go.
                self._log.finish_recovery()
                self._state = state
                self._opened = True
                return self
            except BaseException:
                self._log.close()
                raise

    def close(self) -> None:
        """Close the kernel. Ports issued under the current epoch become
        stale; the kernel is closed (state=None) and mutation methods fail
        closed until a successful open()."""
        with self._mutation_lock:
            self._state = None
            self._opened = False
            self._epoch += 1
            self._log.close()

    def __enter__(self) -> "Kernel":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal: commit one transition (the centralized transition boundary)
    # ------------------------------------------------------------------

    def _require_state(self) -> KernelState:
        if self._state is None:
            raise EcsError("KERNEL_NOT_OPEN: call open() first")
        return self._state

    def _commit(
        self,
        event_kind: str,
        entity_id: str | None,
        payload: Mapping[str, Any],
        transaction_id: str,
        post_state: KernelState,
    ) -> dict:
        """Prepare the entire projection, append+fsync, then install it.

        Caller holds the transition lock. Event intent commits history into
        the root without a digest cycle. No fallible projection construction
        runs after the durability boundary. Ordinary append failures roll
        back durably; uncertain outcomes invalidate the kernel until reopen.
        """
        state = self._require_state()
        before_root = state.state_root_digest()
        # Logical clock increments by exactly one per committed event.
        new_clock = state.logical_clock + 1
        post_state.logical_clock = new_clock
        event = build_event(
            event_index=self._log.event_count(),
            logical_clock=new_clock,
            transaction_id=transaction_id,
            event_kind=event_kind,
            entity_id=entity_id,
            payload=payload,
            before_state_root=before_root,
            after_state_root=GENESIS_PREV_DIGEST,
            prev_event_digest=self._log.head_event_digest(),
        )
        post_state.history_digest = event_intent_digest(event)
        after_root = post_state.state_root_digest()
        event["after_state_root"] = after_root
        event["event_digest"] = canonical.domain_digest(canonical.DOMAIN_EVENT, {
            key: value for key, value in event.items() if key != "event_digest"})
        # Bind the real causing event ID into the post-transition state. The
        # state root does NOT depend on causing_event_id (it is provenance,
        # not behavior), so this does not change after_root. Only kinds that
        # transition an entity's logical state get a causing_event_id update.
        if entity_id is not None and event_kind in _STATE_TRANSITION_KINDS:
            rec = post_state.registry.get(entity_id)
            rec.state = EntityStateVersion(
                entity_id=rec.state.entity_id,
                version=rec.state.version,
                prev_state_digest=rec.state.prev_state_digest,
                state_digest=rec.state.state_digest,
                causing_event_id=event["event_digest"],
                payload=dict(rec.state.payload),
            )
            post_state.registry.replace(rec)
        # Internal transition-boundary assertions.
        assert before_root == state.state_root_digest(), (
            "COMMIT_INVARIANT: before_root drifted from the live state root"
        )
        assert after_root == post_state.state_root_digest(), (
            "COMMIT_INVARIANT: after_root drifted from the post-state root"
        )
        assert post_state.logical_clock == event["logical_clock"], (
            "COMMIT_INVARIANT: post-state clock != event clock"
        )
        # Finish every fallible projection computation before durable append.
        try:
            self._log.append_event(event)
            self._install(post_state)
        except AppendRolledBackError:
            raise
        except BaseException:
            # A full frame may already exist. Hide the projection and require
            # recovery rather than allowing further transitions on stale state.
            self.close()
            raise
        return event

    def _install(self, post_state):
        self._state = post_state

    # ------------------------------------------------------------------
    # Trusted host API: entity-bound invocation ports
    # ------------------------------------------------------------------

    def entity_port(self, entity_id: str) -> EntityPort:
        """TRUSTED HOST API: issue an entity-bound invocation port.

        This is a **trusted host/control API**: it is called by trusted host
        code (the same code that found the entity), NOT by entity-facing
        code. It issues an opaque, process-local :class:`EntityPort` bound to
        exactly one entity ID, exactly one live Kernel instance, and the
        current kernel epoch.

        The entity-facing messaging API is ``port.propose(receiver, payload)``
        — it has NO sender parameter. The sender is always the entity the
        port is bound to; it is taken from the bound port, never from caller
        input.

        The port is process-local mechanical authority only. It is not a
        credential and not cryptographic. No port token appears in canonical
        events and it does not affect deterministic replay.

        **Explicit nonclaim:** M1A-R1 does not isolate hostile Python code
        that already possesses the trusted Kernel/control object or can
        arbitrarily introspect its internals. The guarantee is API-level
        attribution for entity-facing code, not same-address-space
        adversarial sandboxing.
        """
        with self._mutation_lock:
            state = self._require_state()
            state.registry.get(entity_id)  # must exist (fail closed)
            return EntityPort._issue(self, self._epoch, entity_id)

    # ------------------------------------------------------------------
    # Entity-facing messaging (kernel-owned sender attribution)
    # ------------------------------------------------------------------

    def _propose_from_port(
        self,
        port: EntityPort,
        receiver_entity_id: str,
        payload: bytes,
    ) -> str:
        """Entity-facing propose, driven by a bound port (NO sender param).

        The sender is ALWAYS the entity the port is bound to. The kernel
        validates: port liveness (kernel identity + epoch), bound-sender
        lifecycle (must be ACTIVE), receiver deliverability, and mailbox
        capacity. The sender sequence is kernel-assigned (monotonic
        watermark+1). The envelope's logical_clock is the COMMIT clock of the
        enqueue event (pre-transition clock + 1) — see the bus module.

        Returns the message ID on successful durable enqueue.
        """
        with self._mutation_lock:
            _check_port_live(port, self)
            state = self._require_state()
            sender = port.entity_id
            _check_sender_active(self, sender)
            # Receiver must exist and be deliverable (ACTIVE or DORMANT).
            receiver = state.registry.get(receiver_entity_id)
            check_receiver_deliverable(receiver.lifecycle)

            # Kernel-assigned per-sender sequence (monotonic watermark+1).
            sequence = state.watermarks.next_expected(sender)
            # Envelope clock = COMMIT clock of the enqueue event
            # (pre-transition clock + 1). Deterministic, documented, and
            # replayed identically (replay verifies envelope clock == event
            # clock).
            env = seal_envelope(
                sender_entity_id=sender,
                receiver_entity_id=receiver_entity_id,
                sequence=sequence,
                payload=payload,
                logical_clock=state.logical_clock + 1,
            )
            verify_envelope(env)

            # All mailbox mutation happens on the scratch clone; the live
            # state is replaced by scratch only after the durable commit.
            scratch = _clone_state(state)
            box = scratch.mailboxes.box(receiver_entity_id)
            if box.is_full():
                raise MailboxFullError(
                    f"MAILBOX_FULL: receiver={receiver_entity_id} "
                    f"capacity={box.capacity}"
                )
            _apply_enqueued(scratch, env)
            self._commit(
                event_kind="MESSAGE_ENQUEUED",
                entity_id=receiver_entity_id,
                payload={"envelope": env.to_dict()},
                transaction_id=f"ENQ:{env.message_id}",
                post_state=scratch,
            )
            return env.message_id

    # ------------------------------------------------------------------
    # Entity lifecycle (trusted host API)
    # ------------------------------------------------------------------

    def found_entity(self, label: str) -> str:
        """Found a new entity. Returns its stable identifier.

        The founding index is kernel-assigned (monotonic) and is AUTHORITATIVE
        STATE (bound into the state root): the caller cannot choose a founding
        index or a duplicate identity.
        """
        with self._mutation_lock:
            state = self._require_state()
            record = founding_record(
                founding_index=state.next_founding_index,
                label=label,
                genesis_digest=self._genesis_digest,
            )
            eid = entity_id_from_founding(record)
            if eid in state.registry:
                raise DuplicateEntityError(f"DUPLICATE_ENTITY: {eid}")
            scratch = _clone_state(state)
            _apply_founded(scratch, eid, record)
            self._commit(
                event_kind="ENTITY_FOUNDED",
                entity_id=eid,
                payload={
                    "label": label,
                    "founding_index": record["founding_index"],
                    "founding_digest": eid,
                },
                transaction_id=f"FOUND:{eid}",
                post_state=scratch,
            )
            return eid

    @_serialized
    def _lifecycle(self, entity_id: str, target: str) -> None:
        state = self._require_state()
        rec = state.registry.get(entity_id)
        kind = validate_transition(rec.lifecycle, target)
        scratch = _clone_state(state)
        _apply_lifecycle(scratch, entity_id, target, kind)
        self._commit(
            event_kind=kind,
            entity_id=entity_id,
            payload={"from": rec.lifecycle, "to": target},
            transaction_id=f"{kind}:{entity_id}",
            post_state=scratch,
        )

    def activate(self, entity_id: str) -> None:
        with self._mutation_lock:
            self._lifecycle(entity_id, ACTIVE)

    def dormant(self, entity_id: str) -> None:
        with self._mutation_lock:
            self._lifecycle(entity_id, DORMANT)

    def reactivate(self, entity_id: str) -> None:
        with self._mutation_lock:
            self._lifecycle(entity_id, ACTIVE)

    def terminate(self, entity_id: str) -> None:
        with self._mutation_lock:
            self._lifecycle(entity_id, TERMINATED)

    # ------------------------------------------------------------------
    # Scheduler (deterministic, no semantic authority)
    # ------------------------------------------------------------------

    @_serialized
    def ready_items(self) -> list[ReadyItem]:
        """Build the finite ready set deterministically.

        Ready items:
          * PROCESS_MESSAGE: for each mailbox (sorted by receiver entity ID),
            each queued message (FIFO index).
          * LIFECYCLE: entities in FOUNDED state (rank ACTIVATE) — a FOUNDED
            entity is ready to be activated.
        """
        state = self._require_state()
        items: list[ReadyItem] = []
        # PROCESS_MESSAGE ready items (rank ENQUEUE).
        for receiver in sorted(state.mailboxes._boxes):
            box = state.mailboxes._boxes[receiver]
            if state.registry.get(receiver).lifecycle != ACTIVE:
                continue
            for idx, env in enumerate(box._queue):
                items.append(ReadyItem(
                    rank=RANK_ENQUEUE,
                    entity_id=receiver,
                    mailbox_index=idx,
                    message_id=env.message_id,
                    kind="PROCESS_MESSAGE",
                    ref=env.message_id,
                ))
        # LIFECYCLE ready items (rank ACTIVATE): FOUNDED entities.
        for eid in state.registry.ids_sorted():
            rec = state.registry.get(eid)
            if rec.lifecycle == FOUNDED:
                items.append(ReadyItem(
                    rank=RANK_ACTIVATE,
                    entity_id=eid,
                    mailbox_index=0,
                    message_id=eid,
                    kind="LIFECYCLE",
                    ref=eid,
                ))
        return order_ready(items)

    def step(self) -> int:
        """Commit exactly one deterministic transition (the ready-set head).

        Returns 1 if a transition was committed, 0 if the ready set is empty
        (quiescent). The head is chosen by the fully-specified ordering tuple,
        so the choice is deterministic. The ready-set selection and the commit
        occur under the same mutation lock (atomic step).
        """
        with self._mutation_lock:
            items = self.ready_items()
            if not items:
                return 0
            item = items[0]
            if item.kind == "PROCESS_MESSAGE":
                self._process_message(item.entity_id, item.ref)
            elif item.kind == "LIFECYCLE":
                self._lifecycle(item.entity_id, ACTIVE)
            else:
                raise EcsError(f"UNKNOWN_READY_KIND: {item.kind}")
            return 1

    def run_until_quiescent(self, max_steps: int = 10000) -> int:
        """Commit transitions until no ready item remains (or bound hit)."""
        if type(max_steps) is not int or not 0 <= max_steps <= MAX_INT:
            raise EcsError("MAX_STEPS_INVALID")
        total = 0
        while total < max_steps:
            committed = self.step()
            if committed == 0:
                break
            total += 1
        return total

    @_serialized
    def _process_message(self, receiver: str, message_id: str) -> None:
        state = self._require_state()
        box = state.mailboxes._boxes.get(receiver)
        head = box.peek() if box else None
        if head is None or head.message_id != message_id:
            raise EcsError("PROCESS_MISMATCH: head is not the requested message")
        scratch = _clone_state(state)
        _apply_processed(scratch, receiver, message_id)
        self._commit(
            event_kind="MESSAGE_PROCESSED",
            entity_id=receiver,
            payload={"message_id": message_id, "receiver_entity_id": receiver},
            transaction_id=f"PROC:{message_id}",
            post_state=scratch,
        )

    @_serialized
    def checkpoint(self) -> Checkpoint | None:
        """Write a coherent advisory marker at the current transition boundary."""
        state = self._require_state()
        if not state.logical_clock:
            return None
        cp = Checkpoint(self._log.event_count() - 1, self._log.head_event_digest(),
                        state.state_root_digest(), state.logical_clock)
        self._checkpoints.write(cp)
        return cp

    @_serialized
    def snapshot(self) -> dict:
        """Coherent state/history-head observation in one lock acquisition."""
        state = self._require_state()
        return {"state_root": state.state_root(), "state_root_digest": state.state_root_digest(),
                "event_count": self._log.event_count(), "event_digest": self._log.head_event_digest()}

    # ------------------------------------------------------------------
    # Introspection (read-only; serialized)
    # ------------------------------------------------------------------

    @_serialized
    def state_root_digest(self) -> str:
        return self._require_state().state_root_digest()

    @_serialized
    def events(self) -> list[dict]:
        self._require_state()
        try:
            return self._log.read_events()
        except BaseException:
            self.close()
            raise

    @_serialized
    def entity_ids(self) -> list[str]:
        return self._require_state().registry.ids_sorted()

    @_serialized
    def mailbox_size(self, receiver: str) -> int:
        # Read-only: does NOT create a mailbox (the original draft's box()
        # would mutate the live state outside the lock).
        boxes = self._require_state().mailboxes._boxes
        if receiver not in boxes:
            return 0
        return len(boxes[receiver]._queue)


# ---------------------------------------------------------------------------
# Scratch-state helpers (compute the post-transition state without mutating
# the live state)
# ---------------------------------------------------------------------------


def _clone_state(state: KernelState) -> KernelState:
    """Clone the entire projection, including future added dataclass fields."""
    from copy import deepcopy
    return deepcopy(state)


def _apply_founded(state: KernelState, eid: str, record: Mapping[str, Any]) -> None:
    from .replay import _apply_event
    # Build the event payload shape that _apply_event expects.
    ev = {
        "event_kind": "ENTITY_FOUNDED",
        "entity_id": eid,
        "payload": {
            "label": record["label"],
            "founding_index": record["founding_index"],
            "founding_digest": eid,
        },
        "event_digest": "scratch",
    }
    _apply_event(state, ev)


def _apply_lifecycle(state: KernelState, eid: str, target: str, kind: str) -> None:
    from .replay import _apply_event
    ev = {
        "event_kind": kind,
        "entity_id": eid,
        "payload": {"from": state.registry.get(eid).lifecycle, "to": target},
        "event_digest": "scratch",
    }
    _apply_event(state, ev)


def _apply_enqueued(state: KernelState, env: Envelope) -> None:
    from .replay import _apply_event
    # The scratch event carries the COMMIT clock (pre-transition + 1), which
    # is exactly the envelope's logical_clock (the envelope clock is the
    # commit clock of the enqueue event). This keeps the replay cross-check
    # (envelope clock == event clock) meaningful on the scratch path.
    ev = {
        "event_kind": "MESSAGE_ENQUEUED",
        "entity_id": env.receiver_entity_id,
        "payload": {"envelope": env.to_dict()},
        "logical_clock": state.logical_clock + 1,
        "event_digest": "scratch",
    }
    _apply_event(state, ev)


def _apply_processed(state: KernelState, receiver: str, message_id: str) -> None:
    from .replay import _apply_event
    ev = {
        "event_kind": "MESSAGE_PROCESSED",
        "entity_id": receiver,
        "payload": {"message_id": message_id, "receiver_entity_id": receiver},
        "event_digest": "scratch",
    }
    _apply_event(state, ev)
