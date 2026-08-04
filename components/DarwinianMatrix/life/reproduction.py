"""Atomic deterministic asexual reproduction transaction."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .canonical import (
    payload_digest,
    require_sha256,
)
from .lifecycle import LifecycleState
from .lineage import (
    LineageIdentity,
    derive_mutation_seed,
)
from .mutation import (
    MutationPolicyV1,
    MutationResult,
    mutate_genotype,
)
from .organism import OrganismState


BIRTH_REQUEST_SCHEMA = (
    "darwinian.life.birth-request.v1"
)

REPRODUCTION_POLICY_SCHEMA = (
    "darwinian.life.reproduction-policy.v1"
)

REPRODUCTION_RESULT_SCHEMA = (
    "darwinian.life.reproduction-result.v1"
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


class ReproductionRejectionCode(str, Enum):
    STALE_PARENT_STATE = (
        "STALE_PARENT_STATE"
    )
    PARENT_DEAD = "PARENT_DEAD"
    PARENT_NOT_REPRODUCTIVE = (
        "PARENT_NOT_REPRODUCTIVE"
    )
    PARENT_TOO_YOUNG = (
        "PARENT_TOO_YOUNG"
    )
    OFFSPRING_LIMIT_REACHED = (
        "OFFSPRING_LIMIT_REACHED"
    )
    PARENT_ENERGY_BELOW_THRESHOLD = (
        "PARENT_ENERGY_BELOW_THRESHOLD"
    )
    PARENT_ENERGY_BELOW_DEBIT = (
        "PARENT_ENERGY_BELOW_DEBIT"
    )


@dataclass(frozen=True)
class BirthRequest:
    expected_parent_digest: str
    world_state_digest: str
    birth_tick: int
    birth_ordinal: int
    schema: str = BIRTH_REQUEST_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != BIRTH_REQUEST_SCHEMA:
            raise ValueError(
                "Unsupported birth-request schema."
            )

        require_sha256(
            self.expected_parent_digest,
            field_name=(
                "expected_parent_digest"
            ),
        )

        require_sha256(
            self.world_state_digest,
            field_name="world_state_digest",
        )

        _require_nonnegative_integer(
            self.birth_tick,
            field_name="birth_tick",
        )

        _require_nonnegative_integer(
            self.birth_ordinal,
            field_name="birth_ordinal",
        )

    @classmethod
    def for_parent(
        cls,
        *,
        parent: OrganismState,
        world_state_digest: str,
        birth_tick: int,
        birth_ordinal: int,
    ) -> "BirthRequest":
        if not isinstance(
            parent,
            OrganismState,
        ):
            raise TypeError(
                "parent must be an OrganismState."
            )

        return cls(
            expected_parent_digest=(
                parent.digest()
            ),
            world_state_digest=(
                world_state_digest
            ),
            birth_tick=birth_tick,
            birth_ordinal=birth_ordinal,
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "expected_parent_digest": (
                self.expected_parent_digest
            ),
            "world_state_digest": (
                self.world_state_digest
            ),
            "birth_tick": self.birth_tick,
            "birth_ordinal": (
                self.birth_ordinal
            ),
        }

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class ReproductionPolicyV1:
    minimum_parent_energy: int
    minimum_parent_age_ticks: int
    offspring_energy_endowment: int
    reproduction_energy_cost: int
    maximum_offspring: int
    schema: str = REPRODUCTION_POLICY_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REPRODUCTION_POLICY_SCHEMA:
            raise ValueError(
                "Unsupported reproduction-policy schema."
            )

        for field_name, value in (
            (
                "minimum_parent_energy",
                self.minimum_parent_energy,
            ),
            (
                "minimum_parent_age_ticks",
                self.minimum_parent_age_ticks,
            ),
            (
                "offspring_energy_endowment",
                self.offspring_energy_endowment,
            ),
            (
                "reproduction_energy_cost",
                self.reproduction_energy_cost,
            ),
            (
                "maximum_offspring",
                self.maximum_offspring,
            ),
        ):
            _require_nonnegative_integer(
                value,
                field_name=field_name,
            )

        if self.offspring_energy_endowment <= 0:
            raise ValueError(
                "Offspring energy endowment "
                "must be positive."
            )

        if self.maximum_offspring <= 0:
            raise ValueError(
                "maximum_offspring must be positive."
            )

    @property
    def total_parent_debit(self) -> int:
        return (
            self.offspring_energy_endowment
            + self.reproduction_energy_cost
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "minimum_parent_energy": (
                self.minimum_parent_energy
            ),
            "minimum_parent_age_ticks": (
                self.minimum_parent_age_ticks
            ),
            "offspring_energy_endowment": (
                self.offspring_energy_endowment
            ),
            "reproduction_energy_cost": (
                self.reproduction_energy_cost
            ),
            "maximum_offspring": (
                self.maximum_offspring
            ),
            "total_parent_debit": (
                self.total_parent_debit
            ),
            "reproduction_mode": (
                "ASEXUAL_V1"
            ),
        }

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


@dataclass(frozen=True)
class ReproductionResult:
    accepted: bool
    rejection_code: (
        ReproductionRejectionCode | None
    )
    request_digest: str
    reproduction_policy_digest: str
    mutation_policy_digest: str
    parent_before: OrganismState
    parent_after: OrganismState
    child: OrganismState | None
    mutation_result: MutationResult | None
    reproduction_energy_cost: int
    offspring_energy_endowment: int
    schema: str = REPRODUCTION_RESULT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REPRODUCTION_RESULT_SCHEMA:
            raise ValueError(
                "Unsupported reproduction-result schema."
            )

        for field_name, digest in (
            (
                "request_digest",
                self.request_digest,
            ),
            (
                "reproduction_policy_digest",
                self.reproduction_policy_digest,
            ),
            (
                "mutation_policy_digest",
                self.mutation_policy_digest,
            ),
        ):
            require_sha256(
                digest,
                field_name=field_name,
            )

        if not isinstance(
            self.parent_before,
            OrganismState,
        ):
            raise TypeError(
                "parent_before must be an OrganismState."
            )

        if not isinstance(
            self.parent_after,
            OrganismState,
        ):
            raise TypeError(
                "parent_after must be an OrganismState."
            )

        _require_nonnegative_integer(
            self.reproduction_energy_cost,
            field_name=(
                "reproduction_energy_cost"
            ),
        )

        _require_nonnegative_integer(
            self.offspring_energy_endowment,
            field_name=(
                "offspring_energy_endowment"
            ),
        )

        if self.accepted:
            if self.rejection_code is not None:
                raise ValueError(
                    "Accepted reproduction cannot "
                    "carry a rejection code."
                )

            if self.child is None:
                raise ValueError(
                    "Accepted reproduction requires "
                    "a child."
                )

            if self.mutation_result is None:
                raise ValueError(
                    "Accepted reproduction requires "
                    "a mutation result."
                )

            if (
                self.child.genotype.digest()
                != self.mutation_result
                .child_genotype_digest
            ):
                raise ValueError(
                    "Child genotype does not match "
                    "the mutation result."
                )

            if (
                self.parent_after.offspring_count
                != self.parent_before.offspring_count
                + 1
            ):
                raise ValueError(
                    "Accepted reproduction must increment "
                    "the parent offspring count once."
                )

            if (
                self.parent_after.state_revision
                != self.parent_before.state_revision
                + 1
            ):
                raise ValueError(
                    "Accepted reproduction must increment "
                    "the parent revision once."
                )

            conserved_total = (
                self.parent_after.energy
                + self.child.energy
                + self.reproduction_energy_cost
            )

            if conserved_total != self.parent_before.energy:
                raise ValueError(
                    "Accepted reproduction violates "
                    "energy conservation."
                )

            if (
                self.child.energy
                != self.offspring_energy_endowment
            ):
                raise ValueError(
                    "Child energy does not match "
                    "the declared endowment."
                )

        else:
            if not isinstance(
                self.rejection_code,
                ReproductionRejectionCode,
            ):
                raise ValueError(
                    "Rejected reproduction requires "
                    "a rejection code."
                )

            if self.child is not None:
                raise ValueError(
                    "Rejected reproduction cannot "
                    "produce a child."
                )

            if self.mutation_result is not None:
                raise ValueError(
                    "Rejected reproduction cannot "
                    "perform mutation."
                )

            if (
                self.parent_after
                != self.parent_before
            ):
                raise ValueError(
                    "Rejected reproduction must leave "
                    "the parent byte-semantically unchanged."
                )

            if (
                self.reproduction_energy_cost != 0
                or self.offspring_energy_endowment != 0
            ):
                raise ValueError(
                    "Rejected reproduction cannot "
                    "transfer or consume energy."
                )

    @property
    def energy_conserved(self) -> bool:
        if not self.accepted:
            return (
                self.parent_after
                == self.parent_before
            )

        assert self.child is not None

        return (
            self.parent_before.energy
            == self.parent_after.energy
            + self.child.energy
            + self.reproduction_energy_cost
        )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema": self.schema,
            "accepted": self.accepted,
            "rejection_code": (
                None
                if self.rejection_code is None
                else self.rejection_code.value
            ),
            "request_digest": (
                self.request_digest
            ),
            "reproduction_policy_digest": (
                self.reproduction_policy_digest
            ),
            "mutation_policy_digest": (
                self.mutation_policy_digest
            ),
            "parent_before": (
                self.parent_before.canonical_payload()
            ),
            "parent_after": (
                self.parent_after.canonical_payload()
            ),
            "child": (
                None
                if self.child is None
                else self.child.canonical_payload()
            ),
            "mutation_result": (
                None
                if self.mutation_result is None
                else self.mutation_result
                .canonical_payload()
            ),
            "reproduction_energy_cost": (
                self.reproduction_energy_cost
            ),
            "offspring_energy_endowment": (
                self.offspring_energy_endowment
            ),
            "energy_conserved": (
                self.energy_conserved
            ),
        }

    def digest(self) -> str:
        return payload_digest(
            self.canonical_payload()
        )


def _rejected(
    *,
    code: ReproductionRejectionCode,
    parent: OrganismState,
    request: BirthRequest,
    reproduction_policy: ReproductionPolicyV1,
    mutation_policy: MutationPolicyV1,
) -> ReproductionResult:
    return ReproductionResult(
        accepted=False,
        rejection_code=code,
        request_digest=request.digest(),
        reproduction_policy_digest=(
            reproduction_policy.digest()
        ),
        mutation_policy_digest=(
            mutation_policy.digest()
        ),
        parent_before=parent,
        parent_after=parent,
        child=None,
        mutation_result=None,
        reproduction_energy_cost=0,
        offspring_energy_endowment=0,
    )


def execute_reproduction(
    *,
    parent: OrganismState,
    request: BirthRequest,
    reproduction_policy: ReproductionPolicyV1,
    mutation_policy: MutationPolicyV1,
) -> ReproductionResult:
    """Execute one atomic, deterministic asexual birth transaction."""

    if not isinstance(
        parent,
        OrganismState,
    ):
        raise TypeError(
            "parent must be an OrganismState."
        )

    if not isinstance(
        request,
        BirthRequest,
    ):
        raise TypeError(
            "request must be a BirthRequest."
        )

    if not isinstance(
        reproduction_policy,
        ReproductionPolicyV1,
    ):
        raise TypeError(
            "reproduction_policy must be a "
            "ReproductionPolicyV1."
        )

    if not isinstance(
        mutation_policy,
        MutationPolicyV1,
    ):
        raise TypeError(
            "mutation_policy must be a "
            "MutationPolicyV1."
        )

    if (
        request.expected_parent_digest
        != parent.digest()
    ):
        return _rejected(
            code=(
                ReproductionRejectionCode
                .STALE_PARENT_STATE
            ),
            parent=parent,
            request=request,
            reproduction_policy=(
                reproduction_policy
            ),
            mutation_policy=mutation_policy,
        )

    if parent.lifecycle is LifecycleState.DEAD:
        return _rejected(
            code=(
                ReproductionRejectionCode
                .PARENT_DEAD
            ),
            parent=parent,
            request=request,
            reproduction_policy=(
                reproduction_policy
            ),
            mutation_policy=mutation_policy,
        )

    if (
        parent.lifecycle
        is not LifecycleState.REPRODUCTIVE
    ):
        return _rejected(
            code=(
                ReproductionRejectionCode
                .PARENT_NOT_REPRODUCTIVE
            ),
            parent=parent,
            request=request,
            reproduction_policy=(
                reproduction_policy
            ),
            mutation_policy=mutation_policy,
        )

    if (
        parent.age_ticks
        < reproduction_policy
        .minimum_parent_age_ticks
    ):
        return _rejected(
            code=(
                ReproductionRejectionCode
                .PARENT_TOO_YOUNG
            ),
            parent=parent,
            request=request,
            reproduction_policy=(
                reproduction_policy
            ),
            mutation_policy=mutation_policy,
        )

    if (
        parent.offspring_count
        >= reproduction_policy.maximum_offspring
    ):
        return _rejected(
            code=(
                ReproductionRejectionCode
                .OFFSPRING_LIMIT_REACHED
            ),
            parent=parent,
            request=request,
            reproduction_policy=(
                reproduction_policy
            ),
            mutation_policy=mutation_policy,
        )

    if (
        parent.energy
        < reproduction_policy
        .minimum_parent_energy
    ):
        return _rejected(
            code=(
                ReproductionRejectionCode
                .PARENT_ENERGY_BELOW_THRESHOLD
            ),
            parent=parent,
            request=request,
            reproduction_policy=(
                reproduction_policy
            ),
            mutation_policy=mutation_policy,
        )

    if (
        parent.energy
        < reproduction_policy.total_parent_debit
    ):
        return _rejected(
            code=(
                ReproductionRejectionCode
                .PARENT_ENERGY_BELOW_DEBIT
            ),
            parent=parent,
            request=request,
            reproduction_policy=(
                reproduction_policy
            ),
            mutation_policy=mutation_policy,
        )

    mutation_seed = derive_mutation_seed(
        world_state_digest=(
            request.world_state_digest
        ),
        parents=(
            parent.lineage.parent_reference(),
        ),
        birth_tick=request.birth_tick,
        birth_ordinal=request.birth_ordinal,
        mutation_policy_digest=(
            mutation_policy.digest()
        ),
    )

    mutation = mutate_genotype(
        parent=parent.genotype,
        mutation_seed_digest=mutation_seed,
        policy=mutation_policy,
    )

    child_lineage = (
        LineageIdentity.offspring(
            parents=(
                parent.lineage.parent_reference(),
            ),
            birth_tick=request.birth_tick,
            birth_ordinal=(
                request.birth_ordinal
            ),
            genotype_digest=(
                mutation.child_genotype_digest
            ),
            mutation_seed_digest=(
                mutation_seed
            ),
        )
    )

    child = OrganismState(
        lineage=child_lineage,
        genotype=mutation.child_genotype,
        energy=(
            reproduction_policy
            .offspring_energy_endowment
        ),
        resources=(),
        age_ticks=0,
        lifecycle=LifecycleState.EMBRYO,
        offspring_count=0,
        state_revision=0,
    )

    parent_after = replace(
        parent,
        energy=(
            parent.energy
            - reproduction_policy
            .total_parent_debit
        ),
        offspring_count=(
            parent.offspring_count + 1
        ),
        state_revision=(
            parent.state_revision + 1
        ),
    )

    return ReproductionResult(
        accepted=True,
        rejection_code=None,
        request_digest=request.digest(),
        reproduction_policy_digest=(
            reproduction_policy.digest()
        ),
        mutation_policy_digest=(
            mutation_policy.digest()
        ),
        parent_before=parent,
        parent_after=parent_after,
        child=child,
        mutation_result=mutation,
        reproduction_energy_cost=(
            reproduction_policy
            .reproduction_energy_cost
        ),
        offspring_energy_endowment=(
            reproduction_policy
            .offspring_energy_endowment
        ),
    )


__all__ = (
    "BirthRequest",
    "ReproductionPolicyV1",
    "ReproductionRejectionCode",
    "ReproductionResult",
    "execute_reproduction",
)
