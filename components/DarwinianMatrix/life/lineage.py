"""Content-addressed lineage and ledger-derived mutation seeds."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .canonical import (
    payload_digest,
    require_sha256,
)


LINEAGE_SCHEMA = (
    "darwinian.life.lineage.v1"
)

PARENT_REFERENCE_SCHEMA = (
    "darwinian.life.parent-reference.v1"
)

MUTATION_SEED_SCHEMA = (
    "darwinian.life.mutation-seed.v1"
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
class ParentLineageRef:
    organism_id: str
    generation: int
    schema: str = PARENT_REFERENCE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != PARENT_REFERENCE_SCHEMA:
            raise ValueError(
                "Unsupported parent-reference schema."
            )

        require_sha256(
            self.organism_id,
            field_name="organism_id",
        )

        _require_nonnegative_integer(
            self.generation,
            field_name="generation",
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "organism_id": self.organism_id,
            "generation": self.generation,
        }


def derive_mutation_seed(
    *,
    world_state_digest: str,
    parents: Sequence[ParentLineageRef],
    birth_tick: int,
    birth_ordinal: int,
    mutation_policy_digest: str,
) -> str:
    """Derive mutation entropy solely from authoritative state."""

    require_sha256(
        world_state_digest,
        field_name="world_state_digest",
    )

    require_sha256(
        mutation_policy_digest,
        field_name="mutation_policy_digest",
    )

    birth_tick = _require_nonnegative_integer(
        birth_tick,
        field_name="birth_tick",
    )

    birth_ordinal = _require_nonnegative_integer(
        birth_ordinal,
        field_name="birth_ordinal",
    )

    parent_tuple = tuple(parents)

    if len(parent_tuple) not in (1, 2):
        raise ValueError(
            "Mutation seed derivation requires "
            "one or two parents."
        )

    if any(
        not isinstance(
            parent,
            ParentLineageRef,
        )
        for parent in parent_tuple
    ):
        raise TypeError(
            "parents must contain ParentLineageRef objects."
        )

    ordered = tuple(
        sorted(
            parent_tuple,
            key=lambda parent: (
                parent.organism_id,
                parent.generation,
            ),
        )
    )

    if len(
        {
            parent.organism_id
            for parent in ordered
        }
    ) != len(ordered):
        raise ValueError(
            "A parent cannot appear twice."
        )

    return payload_digest(
        {
            "schema": MUTATION_SEED_SCHEMA,
            "world_state_digest": (
                world_state_digest
            ),
            "parents": [
                parent.canonical_payload()
                for parent in ordered
            ],
            "birth_tick": birth_tick,
            "birth_ordinal": birth_ordinal,
            "mutation_policy_digest": (
                mutation_policy_digest
            ),
        }
    )


@dataclass(frozen=True)
class LineageIdentity:
    """Replayable founder or offspring identity."""

    parents: tuple[ParentLineageRef, ...]
    generation: int
    birth_tick: int
    birth_ordinal: int
    genotype_digest: str
    mutation_seed_digest: str | None
    schema: str = LINEAGE_SCHEMA
    organism_id: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema != LINEAGE_SCHEMA:
            raise ValueError(
                "Unsupported lineage schema."
            )

        generation = _require_nonnegative_integer(
            self.generation,
            field_name="generation",
        )

        _require_nonnegative_integer(
            self.birth_tick,
            field_name="birth_tick",
        )

        _require_nonnegative_integer(
            self.birth_ordinal,
            field_name="birth_ordinal",
        )

        require_sha256(
            self.genotype_digest,
            field_name="genotype_digest",
        )

        parents = tuple(self.parents)

        if any(
            not isinstance(
                parent,
                ParentLineageRef,
            )
            for parent in parents
        ):
            raise TypeError(
                "parents must contain ParentLineageRef objects."
            )

        ordered = tuple(
            sorted(
                parents,
                key=lambda parent: (
                    parent.organism_id,
                    parent.generation,
                ),
            )
        )

        if len(
            {
                parent.organism_id
                for parent in ordered
            }
        ) != len(ordered):
            raise ValueError(
                "Duplicate parent identity."
            )

        if not ordered:
            if generation != 0:
                raise ValueError(
                    "A founder must have generation zero."
                )

            if self.mutation_seed_digest is not None:
                raise ValueError(
                    "A founder cannot carry a mutation seed."
                )

        else:
            if len(ordered) not in (1, 2):
                raise ValueError(
                    "Offspring must have one or two parents."
                )

            expected_generation = (
                max(
                    parent.generation
                    for parent in ordered
                )
                + 1
            )

            if generation != expected_generation:
                raise ValueError(
                    "Offspring generation does not follow "
                    "its parent generation."
                )

            if self.mutation_seed_digest is None:
                raise ValueError(
                    "Offspring require a mutation seed."
                )

            require_sha256(
                self.mutation_seed_digest,
                field_name="mutation_seed_digest",
            )

        object.__setattr__(
            self,
            "parents",
            ordered,
        )

        object.__setattr__(
            self,
            "organism_id",
            payload_digest(
                self.canonical_core()
            ),
        )

    @classmethod
    def founder(
        cls,
        *,
        birth_tick: int,
        birth_ordinal: int,
        genotype_digest: str,
    ) -> "LineageIdentity":
        return cls(
            parents=(),
            generation=0,
            birth_tick=birth_tick,
            birth_ordinal=birth_ordinal,
            genotype_digest=genotype_digest,
            mutation_seed_digest=None,
        )

    @classmethod
    def offspring(
        cls,
        *,
        parents: Sequence[ParentLineageRef],
        birth_tick: int,
        birth_ordinal: int,
        genotype_digest: str,
        mutation_seed_digest: str,
    ) -> "LineageIdentity":
        parent_tuple = tuple(parents)

        if not parent_tuple:
            raise ValueError(
                "Offspring require at least one parent."
            )

        generation = (
            max(
                parent.generation
                for parent in parent_tuple
            )
            + 1
        )

        return cls(
            parents=parent_tuple,
            generation=generation,
            birth_tick=birth_tick,
            birth_ordinal=birth_ordinal,
            genotype_digest=genotype_digest,
            mutation_seed_digest=(
                mutation_seed_digest
            ),
        )

    def parent_reference(
        self,
    ) -> ParentLineageRef:
        return ParentLineageRef(
            organism_id=self.organism_id,
            generation=self.generation,
        )

    def canonical_core(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "parents": [
                parent.canonical_payload()
                for parent in self.parents
            ],
            "generation": self.generation,
            "birth_tick": self.birth_tick,
            "birth_ordinal": self.birth_ordinal,
            "genotype_digest": (
                self.genotype_digest
            ),
            "mutation_seed_digest": (
                self.mutation_seed_digest
            ),
        }

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        payload = self.canonical_core()
        payload["organism_id"] = self.organism_id
        return payload

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


__all__ = (
    "LINEAGE_SCHEMA",
    "MUTATION_SEED_SCHEMA",
    "LineageIdentity",
    "ParentLineageRef",
    "derive_mutation_seed",
)
