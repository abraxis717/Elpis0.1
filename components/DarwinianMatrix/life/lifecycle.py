"""Deterministic lifecycle law for Darwinian organisms."""

from __future__ import annotations

from dataclasses import replace
from enum import Enum


class LifecycleState(str, Enum):
    EMBRYO = "EMBRYO"
    ALIVE = "ALIVE"
    REPRODUCTIVE = "REPRODUCTIVE"
    DYING = "DYING"
    DEAD = "DEAD"


_ALLOWED_TRANSITIONS = {
    LifecycleState.EMBRYO: frozenset(
        {
            LifecycleState.ALIVE,
            LifecycleState.DYING,
        }
    ),
    LifecycleState.ALIVE: frozenset(
        {
            LifecycleState.REPRODUCTIVE,
            LifecycleState.DYING,
        }
    ),
    LifecycleState.REPRODUCTIVE: frozenset(
        {
            LifecycleState.ALIVE,
            LifecycleState.DYING,
        }
    ),
    LifecycleState.DYING: frozenset(
        {
            LifecycleState.DEAD,
        }
    ),
    LifecycleState.DEAD: frozenset(),
}


def can_transition(
    source: LifecycleState,
    target: LifecycleState,
) -> bool:
    if not isinstance(source, LifecycleState):
        raise TypeError(
            "source must be a LifecycleState."
        )

    if not isinstance(target, LifecycleState):
        raise TypeError(
            "target must be a LifecycleState."
        )

    return target in _ALLOWED_TRANSITIONS[source]


def transition_lifecycle(
    organism,
    target: LifecycleState,
):
    """Return a new state after one legal lifecycle transition."""

    from .organism import OrganismState

    if not isinstance(organism, OrganismState):
        raise TypeError(
            "organism must be an OrganismState."
        )

    if not isinstance(target, LifecycleState):
        raise TypeError(
            "target must be a LifecycleState."
        )

    if not can_transition(
        organism.lifecycle,
        target,
    ):
        raise ValueError(
            "Illegal lifecycle transition: "
            + organism.lifecycle.value
            + " -> "
            + target.value
            + "."
        )

    return replace(
        organism,
        lifecycle=target,
        state_revision=(
            organism.state_revision + 1
        ),
    )


__all__ = (
    "LifecycleState",
    "can_transition",
    "transition_lifecycle",
)
