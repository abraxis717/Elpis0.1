"""Token-local and epoch-window observation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from Artifacts.content_identity import IdentityTuple, identity_of_payload

from ._validation import (
    require_digest,
    require_finite_vector,
    require_nonnegative_int,
    require_optional_digest,
    require_probability,
)


class RoleSource(str, Enum):
    TEMPLATE = "TEMPLATE"
    PROBE = "PROBE"
    HYBRID = "HYBRID"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class TokenObservation:
    """Compact projection for one accepted target token.

    Grid81 columns are deliberately absent. They are assigned only when the
    complete ordered epoch window is reduced.
    """

    SCHEMA: ClassVar[str] = "elpis.header.token-observation.v1"
    ROLE_COUNT: ClassVar[int] = 9
    SEMANTIC_RESIDUAL_DIM: ClassVar[int] = 6

    epoch_ordinal: int
    within_epoch_ordinal: int
    accepted_target_position: int
    role_mass: tuple[float, ...]
    role_sources: tuple[RoleSource, ...]
    semantic_residual: tuple[float, ...]
    confidence: float
    source_token_digest: str
    source_hidden_digest: str
    observer_policy_digest: str
    semantic_basis_digest: str

    def __post_init__(self) -> None:
        require_nonnegative_int("epoch_ordinal", self.epoch_ordinal)
        require_nonnegative_int("within_epoch_ordinal", self.within_epoch_ordinal)
        require_nonnegative_int("accepted_target_position", self.accepted_target_position)

        role_mass = require_finite_vector(
            "role_mass", self.role_mass, length=self.ROLE_COUNT
        )
        if any(v < 0.0 or v > 1.0 for v in role_mass):
            raise ValueError("role_mass values must be within [0, 1]")
        if abs(sum(role_mass) - 1.0) > 1e-6:
            raise ValueError("role_mass must sum to 1 within tolerance 1e-6")
        object.__setattr__(self, "role_mass", role_mass)

        sources = tuple(
            value if isinstance(value, RoleSource) else RoleSource(value)
            for value in self.role_sources
        )
        if len(sources) != self.ROLE_COUNT:
            raise ValueError(f"role_sources must contain exactly {self.ROLE_COUNT} entries")
        object.__setattr__(self, "role_sources", sources)

        object.__setattr__(
            self,
            "semantic_residual",
            require_finite_vector(
                "semantic_residual",
                self.semantic_residual,
                length=self.SEMANTIC_RESIDUAL_DIM,
            ),
        )
        object.__setattr__(
            self, "confidence", require_probability("confidence", self.confidence)
        )

        for name in (
            "source_token_digest",
            "source_hidden_digest",
            "observer_policy_digest",
            "semantic_basis_digest",
        ):
            require_digest(name, getattr(self, name))

    def as_dict(self) -> dict[str, Any]:
        return {
            "__record__": "TokenObservation",
            "schema": self.SCHEMA,
            "epoch_ordinal": self.epoch_ordinal,
            "within_epoch_ordinal": self.within_epoch_ordinal,
            "accepted_target_position": self.accepted_target_position,
            "role_mass": list(self.role_mass),
            "role_sources": [source.value for source in self.role_sources],
            "semantic_residual": list(self.semantic_residual),
            "confidence": self.confidence,
            "source_token_digest": self.source_token_digest,
            "source_hidden_digest": self.source_hidden_digest,
            "observer_policy_digest": self.observer_policy_digest,
            "semantic_basis_digest": self.semantic_basis_digest,
        }

    def identity(self) -> IdentityTuple:
        return identity_of_payload(
            self.as_dict(),
            parent_primaries=(
                self.source_token_digest,
                self.source_hidden_digest,
                self.observer_policy_digest,
                self.semantic_basis_digest,
            ),
        )


@dataclass(frozen=True, slots=True)
class ObservationWindow:
    """Ordered token-local records closed at one Header Epoch boundary."""

    SCHEMA: ClassVar[str] = "elpis.header.observation-window.v1"

    epoch_ordinal: int
    host_identity_digest: str
    observer_policy_digest: str
    semantic_basis_digest: str
    records: tuple[TokenObservation, ...]
    previous_header_state_digest: str | None = None

    def __post_init__(self) -> None:
        require_nonnegative_int("epoch_ordinal", self.epoch_ordinal)
        require_digest("host_identity_digest", self.host_identity_digest)
        require_digest("observer_policy_digest", self.observer_policy_digest)
        require_digest("semantic_basis_digest", self.semantic_basis_digest)
        require_optional_digest(
            "previous_header_state_digest", self.previous_header_state_digest
        )

        records = tuple(self.records)
        if not records:
            raise ValueError("ObservationWindow requires at least one TokenObservation")

        if tuple(r.within_epoch_ordinal for r in records) != tuple(range(len(records))):
            raise ValueError(
                "TokenObservation within_epoch_ordinal values must be contiguous "
                "and ordered from zero"
            )

        positions = tuple(r.accepted_target_position for r in records)
        if any(right <= left for left, right in zip(positions, positions[1:])):
            raise ValueError("accepted_target_position values must be strictly increasing")

        for record in records:
            if record.epoch_ordinal != self.epoch_ordinal:
                raise ValueError("all records must belong to the window epoch")
            if record.observer_policy_digest != self.observer_policy_digest:
                raise ValueError("record observer policy differs from window policy")
            if record.semantic_basis_digest != self.semantic_basis_digest:
                raise ValueError("record semantic basis differs from window basis")

        object.__setattr__(self, "records", records)

    def as_dict(self) -> dict[str, Any]:
        return {
            "__record__": "ObservationWindow",
            "schema": self.SCHEMA,
            "epoch_ordinal": self.epoch_ordinal,
            "host_identity_digest": self.host_identity_digest,
            "observer_policy_digest": self.observer_policy_digest,
            "semantic_basis_digest": self.semantic_basis_digest,
            "previous_header_state_digest": self.previous_header_state_digest,
            "records": [record.as_dict() for record in self.records],
        }

    def identity(self) -> IdentityTuple:
        parents = [
            self.host_identity_digest,
            self.observer_policy_digest,
            self.semantic_basis_digest,
        ]
        if self.previous_header_state_digest is not None:
            parents.append(self.previous_header_state_digest)
        return identity_of_payload(self.as_dict(), parent_primaries=tuple(parents))
