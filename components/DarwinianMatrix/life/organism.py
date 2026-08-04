"""Canonical persistent organism state."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Sequence

from .canonical import payload_digest
from .genotype import Genotype
from .lineage import LineageIdentity
from .lifecycle import LifecycleState


ORGANISM_STATE_SCHEMA = (
    "darwinian.life.organism-state.v1"
)

RESOURCE_QUANTITY_SCHEMA = (
    "darwinian.life.resource-quantity.v1"
)

_RESOURCE_NAME_PATTERN = re.compile(
    r"[a-z][a-z0-9_]{0,63}"
)


def _require_nonnegative_integer(
    value: object,
    *,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(
        value,
        int,
    ):
        raise TypeError(
            field_name + " must be an integer."
        )

    if value < 0:
        raise ValueError(
            field_name + " cannot be negative."
        )

    return value


@dataclass(frozen=True)
class ResourceQuantity:
    name: str
    amount: int
    schema: str = RESOURCE_QUANTITY_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != RESOURCE_QUANTITY_SCHEMA:
            raise ValueError(
                "Unsupported resource-quantity schema."
            )

        if (
            not isinstance(self.name, str)
            or _RESOURCE_NAME_PATTERN.fullmatch(
                self.name
            )
            is None
        ):
            raise ValueError(
                "Resource names must match "
                "[a-z][a-z0-9_]{0,63}."
            )

        _require_nonnegative_integer(
            self.amount,
            field_name=self.name + ".amount",
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "name": self.name,
            "amount": self.amount,
        }


@dataclass(frozen=True)
class OrganismState:
    """Immutable authoritative state for one artificial organism."""

    lineage: LineageIdentity
    genotype: Genotype
    energy: int
    resources: tuple[ResourceQuantity, ...] = ()
    age_ticks: int = 0
    lifecycle: LifecycleState = (
        LifecycleState.EMBRYO
    )
    offspring_count: int = 0
    state_revision: int = 0
    schema: str = ORGANISM_STATE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != ORGANISM_STATE_SCHEMA:
            raise ValueError(
                "Unsupported organism-state schema."
            )

        if not isinstance(
            self.lineage,
            LineageIdentity,
        ):
            raise TypeError(
                "lineage must be a LineageIdentity."
            )

        if not isinstance(
            self.genotype,
            Genotype,
        ):
            raise TypeError(
                "genotype must be a Genotype."
            )

        if (
            self.lineage.genotype_digest
            != self.genotype.digest()
        ):
            raise ValueError(
                "Lineage genotype digest does not "
                "match the organism genotype."
            )

        _require_nonnegative_integer(
            self.energy,
            field_name="energy",
        )

        _require_nonnegative_integer(
            self.age_ticks,
            field_name="age_ticks",
        )

        _require_nonnegative_integer(
            self.offspring_count,
            field_name="offspring_count",
        )

        _require_nonnegative_integer(
            self.state_revision,
            field_name="state_revision",
        )

        if not isinstance(
            self.lifecycle,
            LifecycleState,
        ):
            raise TypeError(
                "lifecycle must be a LifecycleState."
            )

        resources = tuple(self.resources)

        if any(
            not isinstance(
                resource,
                ResourceQuantity,
            )
            for resource in resources
        ):
            raise TypeError(
                "resources must contain "
                "ResourceQuantity objects."
            )

        ordered = tuple(
            sorted(
                resources,
                key=lambda resource: resource.name,
            )
        )

        names = tuple(
            resource.name
            for resource in ordered
        )

        if len(names) != len(set(names)):
            raise ValueError(
                "Resource names must be unique."
            )

        if (
            self.lifecycle
            is LifecycleState.EMBRYO
            and self.age_ticks != 0
        ):
            raise ValueError(
                "An embryo must have age zero."
            )

        object.__setattr__(
            self,
            "resources",
            ordered,
        )

    @property
    def organism_id(self) -> str:
        return self.lineage.organism_id

    def resource_amount(
        self,
        name: str,
    ) -> int:
        for resource in self.resources:
            if resource.name == name:
                return resource.amount

        return 0

    def replace_resources(
        self,
        replacements: Mapping[str, int],
    ) -> tuple[ResourceQuantity, ...]:
        existing = {
            resource.name: resource.amount
            for resource in self.resources
        }

        for name, amount in replacements.items():
            ResourceQuantity(
                name=name,
                amount=amount,
            )
            existing[name] = amount

        return tuple(
            ResourceQuantity(
                name=name,
                amount=amount,
            )
            for name, amount in sorted(
                existing.items()
            )
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "organism_id": self.organism_id,
            "lineage": (
                self.lineage.canonical_payload()
            ),
            "genotype": (
                self.genotype.canonical_payload()
            ),
            "genotype_digest": (
                self.genotype.digest()
            ),
            "energy": self.energy,
            "resources": [
                resource.canonical_payload()
                for resource in self.resources
            ],
            "age_ticks": self.age_ticks,
            "lifecycle": self.lifecycle.value,
            "offspring_count": (
                self.offspring_count
            ),
            "state_revision": (
                self.state_revision
            ),
        }

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


__all__ = (
    "ORGANISM_STATE_SCHEMA",
    "OrganismState",
    "ResourceQuantity",
)
