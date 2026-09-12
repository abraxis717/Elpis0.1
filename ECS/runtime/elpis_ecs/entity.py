"""Elpis ECS M1A — deterministic entity identity, lifecycle, canonical state.

Entity identity
---------------
An entity ID is a domain-separated digest over a canonical founding record
containing only deterministic inputs (founding index, label, genesis digest).

The entity ID is a STABLE IDENTIFIER. It is NOT authentication and NOT a
credential: it does not prove possession or control of the entity. Within M1A,
entity-origin authenticity comes from the trusted local kernel invocation
context and registry, never from an entity self-asserting an ID inside an
envelope. (See ECS/design/04-entity-model.md, adjudication item 2.)

Lifecycle
---------
    FOUNDED -> ACTIVE -> DORMANT -> ACTIVE
    ACTIVE | DORMANT -> TERMINATED
TERMINATED is terminal. Every lifecycle transition is a committed event.
Terminated identities are never recycled.

State
-----
Entity state uses immutable logical versions. Every accepted entity transition
binds: entity ID, state version, previous state digest, new state digest, and
the causing event ID. Versions are monotonic. A failed transition produces no
partially visible state (the transition is all-or-nothing at commit).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from . import canonical
from .limits import MAX_INT, MAX_STRING_BYTES
from .errors import (
    DuplicateEntityError,
    EntityError,
    InvalidTransitionError,
    TerminatedEntityError,
)

# ---------------------------------------------------------------------------
# Lifecycle states
# ---------------------------------------------------------------------------

FOUNDED = "FOUNDED"
ACTIVE = "ACTIVE"
DORMANT = "DORMANT"
TERMINATED = "TERMINATED"

LIFECYCLE_STATES = (FOUNDED, ACTIVE, DORMANT, TERMINATED)

# Allowed transitions: (from, to)
ALLOWED_TRANSITIONS = frozenset({
    (FOUNDED, ACTIVE),
    (ACTIVE, DORMANT),
    (DORMANT, ACTIVE),
    (ACTIVE, TERMINATED),
    (DORMANT, TERMINATED),
})

# Event kind emitted for each transition.
TRANSITION_EVENT_KIND = {
    (FOUNDED, ACTIVE): "ENTITY_ACTIVATED",
    (ACTIVE, DORMANT): "ENTITY_DORMANT",
    (DORMANT, ACTIVE): "ENTITY_REACTIVATED",
    (ACTIVE, TERMINATED): "ENTITY_TERMINATED",
    (DORMANT, TERMINATED): "ENTITY_TERMINATED",
}


def validate_transition(current: str, target: str) -> str:
    """Return the event kind for a legal transition, else raise."""
    if current not in LIFECYCLE_STATES:
        raise InvalidTransitionError(f"UNKNOWN_LIFECYCLE: {current!r}")
    if target not in LIFECYCLE_STATES:
        raise InvalidTransitionError(f"UNKNOWN_LIFECYCLE_TARGET: {target!r}")
    if current == TERMINATED:
        raise TerminatedEntityError(
            "TERMINATED_IS_TERMINAL: no transition out of TERMINATED"
        )
    if (current, target) not in ALLOWED_TRANSITIONS:
        raise InvalidTransitionError(
            f"ILLEGAL_TRANSITION: {current} -> {target}"
        )
    return TRANSITION_EVENT_KIND[(current, target)]


# ---------------------------------------------------------------------------
# Founding record and entity identity
# ---------------------------------------------------------------------------

FOUNDING_SCHEMA = "ecs.entity.founding.v1"


def founding_record(founding_index: int, label: str, genesis_digest: str) -> dict:
    """Canonical founding record (deterministic inputs only)."""
    if not isinstance(founding_index, int) or isinstance(founding_index, bool) \
            or not 0 <= founding_index <= MAX_INT:
        raise EntityError("FOUNDING_INDEX_INVALID: must be a non-negative int")
    if not isinstance(label, str) or not label or len(label.encode("utf-8")) > MAX_STRING_BYTES:
        raise EntityError("LABEL_INVALID: must be a non-empty string")
    if not isinstance(genesis_digest, str) or len(genesis_digest) != 64:
        raise EntityError("GENESIS_DIGEST_INVALID: must be a 64-hex digest")
    return {
        "schema": FOUNDING_SCHEMA,
        "founding_index": founding_index,
        "label": label,
        "genesis_digest": genesis_digest,
    }


def entity_id_from_founding(record: Mapping[str, Any]) -> str:
    """Domain-separated digest over the canonical founding record.

    This is a stable IDENTIFIER, not a credential and not authentication.
    """
    return canonical.domain_digest(canonical.DOMAIN_ENTITY_FOUNDED, dict(record))


# ---------------------------------------------------------------------------
# Immutable logical state versions
# ---------------------------------------------------------------------------

STATE_SCHEMA = "ecs.entity.state.v1"


def _state_record(entity_id: str, version: int, payload: Mapping[str, Any]) -> dict:
    return {
        "schema": STATE_SCHEMA,
        "entity_id": entity_id,
        "version": version,
        "payload": dict(payload),
    }


def state_digest(entity_id: str, version: int, payload: Mapping[str, Any]) -> str:
    """Digest of an immutable logical state version."""
    return canonical.domain_digest(
        canonical.DOMAIN_ENTITY_STATE,
        _state_record(entity_id, version, payload),
    )


def initial_state_digest(entity_id: str) -> str:
    """Digest of the canonical version-0 (pre-founding) state."""
    return state_digest(entity_id, 0, {})


@dataclass(frozen=True)
class EntityStateVersion:
    """One immutable logical state version of an entity.

    Binds: entity ID, state version, previous state digest, new state digest,
    and the causing event ID. ``payload`` is intentionally generic and small
    (M1A keeps it to a mechanical delivery counter; no semantic cognition).
    """

    entity_id: str
    version: int
    prev_state_digest: str
    state_digest: str
    causing_event_id: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "version": self.version,
            "prev_state_digest": self.prev_state_digest,
            "state_digest": self.state_digest,
            "causing_event_id": self.causing_event_id,
            "payload": dict(self.payload),
        }


def make_state_version(
    entity_id: str,
    version: int,
    prev_state_digest: str,
    causing_event_id: str,
    payload: Mapping[str, Any],
) -> EntityStateVersion:
    """Construct and self-check an immutable state version."""
    if not isinstance(version, int) or isinstance(version, bool) or not 1 <= version <= MAX_INT:
        raise EntityError("STATE_VERSION_INVALID: must be a positive int")
    new_digest = state_digest(entity_id, version, payload)
    return EntityStateVersion(
        entity_id=entity_id,
        version=version,
        prev_state_digest=prev_state_digest,
        state_digest=new_digest,
        causing_event_id=causing_event_id,
        payload=dict(payload),
    )


# ---------------------------------------------------------------------------
# Registry entry
# ---------------------------------------------------------------------------

@dataclass
class EntityRecord:
    """Registry entry for one entity (materialized projection of events)."""

    entity_id: str
    label: str
    founding_index: int
    founding_digest: str
    lifecycle: str
    state: EntityStateVersion

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "label": self.label,
            "founding_index": self.founding_index,
            "founding_digest": self.founding_digest,
            "lifecycle": self.lifecycle,
            "state": self.state.to_dict(),
        }

    def state_root_projection(self) -> dict:
        """Behavior-affecting projection used in the state root.

        Binds every record field except causing_event_id. That digest is a
        derived output of the current event (binding it here would create a
        cycle). The root's history_digest commits all event inputs, and the
        after root determines that event's digest and hence this provenance.
        """
        return {
            "entity_id": self.entity_id,
            "label": self.label,
            "founding_index": self.founding_index,
            "founding_digest": self.founding_digest,
            "state_entity_id": self.state.entity_id,
            "prev_state_digest": self.state.prev_state_digest,
            "lifecycle": self.lifecycle,
            "state_version": self.state.version,
            "state_digest": self.state.state_digest,
            "payload": dict(self.state.payload),
        }


class EntityRegistry:
    """In-memory registry; a materialized projection of committed events.

    The registry is NOT an independent source of truth: it is fully
    reconstructable from the committed event history (see replay.py).
    """

    def __init__(self) -> None:
        self._by_id: dict[str, EntityRecord] = {}

    def __contains__(self, entity_id: str) -> bool:
        return entity_id in self._by_id

    def __len__(self) -> int:
        return len(self._by_id)

    def get(self, entity_id: str) -> EntityRecord:
        if type(entity_id) is not str:
            raise EntityError("ENTITY_ID_NOT_STRING")
        try:
            return self._by_id[entity_id]
        except KeyError:
            raise EntityError(f"ENTITY_NOT_FOUND: {entity_id}") from None

    def add(self, record: EntityRecord) -> None:
        if record.entity_id in self._by_id:
            raise DuplicateEntityError(
                f"DUPLICATE_ENTITY: {record.entity_id} already exists "
                f"(terminated identities are never recycled)"
            )
        self._by_id[record.entity_id] = record

    def replace(self, record: EntityRecord) -> None:
        if record.entity_id not in self._by_id:
            raise EntityError(f"ENTITY_NOT_FOUND: {record.entity_id}")
        self._by_id[record.entity_id] = record

    def ids_sorted(self) -> list[str]:
        return sorted(self._by_id)

    def as_sorted_list(self) -> list[dict]:
        """Deterministic full serialization (for cloning / debugging)."""
        return [self._by_id[eid].to_dict() for eid in self.ids_sorted()]

    def state_root_projection(self) -> list[dict]:
        """Deterministic behavior-affecting projection for the state root."""
        return [{"registry_key": eid, **self._by_id[eid].state_root_projection()}
                for eid in self.ids_sorted()]
