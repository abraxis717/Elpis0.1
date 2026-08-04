"""Content-addressed Header state contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from Artifacts.content_identity import IdentityTuple, identity_of_payload

from ._validation import (
    require_digest,
    require_nonnegative_int,
    require_optional_digest,
)


@dataclass(frozen=True, slots=True)
class Grid81StateReference:
    """Reference to a canonical Grid81 payload owned by existing Grid81 code."""

    SCHEMA: ClassVar[str] = "elpis.header.grid81-state-reference.v1"
    GRID81_SCHEMA: ClassVar[str] = "grid81.structural.v1"
    SHAPE: ClassVar[tuple[int, int]] = (81, 10)

    payload_digest: str
    observation_window_digest: str
    trm_refinement_digest: str | None = None

    def __post_init__(self) -> None:
        require_digest("payload_digest", self.payload_digest)
        require_digest("observation_window_digest", self.observation_window_digest)
        require_optional_digest("trm_refinement_digest", self.trm_refinement_digest)

    def as_dict(self) -> dict[str, Any]:
        return {
            "__record__": "Grid81StateReference",
            "schema": self.SCHEMA,
            "grid81_schema": self.GRID81_SCHEMA,
            "shape": list(self.SHAPE),
            "payload_digest": self.payload_digest,
            "observation_window_digest": self.observation_window_digest,
            "trm_refinement_digest": self.trm_refinement_digest,
        }

    def identity(self) -> IdentityTuple:
        parents = [self.payload_digest, self.observation_window_digest]
        if self.trm_refinement_digest is not None:
            parents.append(self.trm_refinement_digest)
        return identity_of_payload(self.as_dict(), parent_primaries=tuple(parents))


@dataclass(frozen=True, slots=True)
class SealedHeaderState:
    """One immutable Markovian Header state.

    Host token positions belong to DraftStateLease, not this state.
    """

    SCHEMA: ClassVar[str] = "elpis.header.state.v1"

    epoch_ordinal: int
    grid81_state_digest: str
    observation_window_digest: str
    previous_state_digest: str | None

    core_config_digest: str
    semantic_basis_digest: str
    refresh_policy_digest: str
    lease_policy_digest: str
    boundary_detector_policy_digest: str
    inner_recursion_policy_digest: str
    outer_stability_policy_digest: str

    population_digest: str
    selection_receipt_digest: str

    def __post_init__(self) -> None:
        require_nonnegative_int("epoch_ordinal", self.epoch_ordinal)
        require_optional_digest("previous_state_digest", self.previous_state_digest)
        for name in (
            "grid81_state_digest",
            "observation_window_digest",
            "core_config_digest",
            "semantic_basis_digest",
            "refresh_policy_digest",
            "lease_policy_digest",
            "boundary_detector_policy_digest",
            "inner_recursion_policy_digest",
            "outer_stability_policy_digest",
            "population_digest",
            "selection_receipt_digest",
        ):
            require_digest(name, getattr(self, name))

    def as_dict(self) -> dict[str, Any]:
        return {
            "__record__": "SealedHeaderState",
            "schema": self.SCHEMA,
            "epoch_ordinal": self.epoch_ordinal,
            "grid81_state_digest": self.grid81_state_digest,
            "observation_window_digest": self.observation_window_digest,
            "previous_state_digest": self.previous_state_digest,
            "core_config_digest": self.core_config_digest,
            "semantic_basis_digest": self.semantic_basis_digest,
            "refresh_policy_digest": self.refresh_policy_digest,
            "lease_policy_digest": self.lease_policy_digest,
            "boundary_detector_policy_digest": self.boundary_detector_policy_digest,
            "inner_recursion_policy_digest": self.inner_recursion_policy_digest,
            "outer_stability_policy_digest": self.outer_stability_policy_digest,
            "population_digest": self.population_digest,
            "selection_receipt_digest": self.selection_receipt_digest,
        }

    def identity(self) -> IdentityTuple:
        parents = [
            self.grid81_state_digest,
            self.observation_window_digest,
            self.core_config_digest,
            self.semantic_basis_digest,
            self.refresh_policy_digest,
            self.lease_policy_digest,
            self.boundary_detector_policy_digest,
            self.inner_recursion_policy_digest,
            self.outer_stability_policy_digest,
            self.population_digest,
            self.selection_receipt_digest,
        ]
        if self.previous_state_digest is not None:
            parents.append(self.previous_state_digest)
        return identity_of_payload(self.as_dict(), parent_primaries=tuple(parents))
