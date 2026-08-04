from __future__ import annotations

from dataclasses import replace

import pytest

from DarwinianMatrix.life import (
    BirthRequest,
    Genotype,
    IntegerGene,
    LifecycleState,
    LineageIdentity,
    MutationPolicyV1,
    OrganismState,
    ReproductionPolicyV1,
    ReproductionRejectionCode,
    ResourceQuantity,
    execute_reproduction,
    transition_lifecycle,
)


WORLD_A = "a" * 64
WORLD_B = "b" * 64


def genotype() -> Genotype:
    return Genotype(
        genes=(
            IntegerGene(
                "basal_metabolism",
                value=12,
                minimum=2,
                maximum=40,
                step=2,
            ),
            IntegerGene(
                "defense",
                value=5,
                minimum=0,
                maximum=20,
                step=1,
            ),
            IntegerGene(
                "reproduction_threshold",
                value=80,
                minimum=20,
                maximum=200,
                step=10,
            ),
            IntegerGene(
                "uptake_rate",
                value=50,
                minimum=0,
                maximum=100,
                step=5,
            ),
        )
    )


def organism(
    *,
    energy: int = 120,
    age_ticks: int = 10,
    lifecycle: LifecycleState = (
        LifecycleState.REPRODUCTIVE
    ),
    offspring_count: int = 0,
    birth_ordinal: int = 0,
) -> OrganismState:
    genome = genotype()

    lineage = LineageIdentity.founder(
        birth_tick=0,
        birth_ordinal=birth_ordinal,
        genotype_digest=genome.digest(),
    )

    return OrganismState(
        lineage=lineage,
        genotype=genome,
        energy=energy,
        resources=(
            ResourceQuantity(
                "carbon",
                12,
            ),
            ResourceQuantity(
                "water",
                7,
            ),
        ),
        age_ticks=age_ticks,
        lifecycle=lifecycle,
        offspring_count=offspring_count,
        state_revision=0,
    )


def reproduction_policy(
    *,
    minimum_parent_energy: int = 80,
    minimum_parent_age_ticks: int = 5,
    offspring_energy_endowment: int = 30,
    reproduction_energy_cost: int = 10,
    maximum_offspring: int = 3,
) -> ReproductionPolicyV1:
    return ReproductionPolicyV1(
        minimum_parent_energy=(
            minimum_parent_energy
        ),
        minimum_parent_age_ticks=(
            minimum_parent_age_ticks
        ),
        offspring_energy_endowment=(
            offspring_energy_endowment
        ),
        reproduction_energy_cost=(
            reproduction_energy_cost
        ),
        maximum_offspring=(
            maximum_offspring
        ),
    )


def mutation_policy() -> MutationPolicyV1:
    return MutationPolicyV1(
        activation_probability_ppm=1_000_000,
        max_mutated_loci=2,
        max_step_multiple=2,
    )


def request(
    parent: OrganismState,
    *,
    world_digest: str = WORLD_A,
    birth_tick: int = 1,
    birth_ordinal: int = 0,
) -> BirthRequest:
    return BirthRequest.for_parent(
        parent=parent,
        world_state_digest=world_digest,
        birth_tick=birth_tick,
        birth_ordinal=birth_ordinal,
    )


def reproduce(
    parent: OrganismState,
    *,
    birth_ordinal: int = 0,
    world_digest: str = WORLD_A,
    policy: ReproductionPolicyV1 | None = None,
):
    return execute_reproduction(
        parent=parent,
        request=request(
            parent,
            world_digest=world_digest,
            birth_ordinal=birth_ordinal,
        ),
        reproduction_policy=(
            reproduction_policy()
            if policy is None
            else policy
        ),
        mutation_policy=mutation_policy(),
    )


def test_resource_inventory_is_canonical():
    parent = organism()

    reversed_state = replace(
        parent,
        resources=tuple(
            reversed(parent.resources)
        ),
    )

    assert (
        parent.canonical_payload()
        == reversed_state.canonical_payload()
    )
    assert parent.digest() == reversed_state.digest()


def test_lineage_must_bind_the_genotype():
    parent = organism()

    different = parent.genotype.replace_values(
        {
            "defense": 6,
        }
    )

    with pytest.raises(
        ValueError,
        match="Lineage genotype",
    ):
        OrganismState(
            lineage=parent.lineage,
            genotype=different,
            energy=parent.energy,
            age_ticks=parent.age_ticks,
            lifecycle=parent.lifecycle,
        )


def test_lifecycle_transition_is_immutable():
    embryo = organism(
        age_ticks=0,
        lifecycle=LifecycleState.EMBRYO,
    )

    alive = transition_lifecycle(
        embryo,
        LifecycleState.ALIVE,
    )

    assert embryo.lifecycle is LifecycleState.EMBRYO
    assert alive.lifecycle is LifecycleState.ALIVE
    assert (
        alive.state_revision
        == embryo.state_revision + 1
    )


def test_illegal_lifecycle_transition_is_rejected():
    parent = organism()

    with pytest.raises(
        ValueError,
        match="Illegal lifecycle",
    ):
        transition_lifecycle(
            parent,
            LifecycleState.DEAD,
        )


def test_death_is_irreversible():
    parent = organism()

    dying = transition_lifecycle(
        parent,
        LifecycleState.DYING,
    )

    dead = transition_lifecycle(
        dying,
        LifecycleState.DEAD,
    )

    with pytest.raises(
        ValueError,
        match="Illegal lifecycle",
    ):
        transition_lifecycle(
            dead,
            LifecycleState.ALIVE,
        )


def test_accepted_reproduction_is_deterministic():
    parent = organism()

    first = reproduce(parent)
    second = reproduce(parent)

    assert first.accepted is True
    assert second.accepted is True
    assert first.digest() == second.digest()
    assert first.child is not None
    assert second.child is not None
    assert (
        first.child.organism_id
        == second.child.organism_id
    )


def test_reproduction_conserves_energy():
    parent = organism()
    result = reproduce(parent)

    assert result.accepted is True
    assert result.child is not None
    assert result.energy_conserved is True

    assert parent.energy == (
        result.parent_after.energy
        + result.child.energy
        + result.reproduction_energy_cost
    )


def test_reproduction_does_not_mutate_parent_object():
    parent = organism()
    before_digest = parent.digest()

    result = reproduce(parent)

    assert parent.digest() == before_digest
    assert result.parent_before is parent
    assert result.parent_after is not parent
    assert result.parent_after.energy == 80
    assert result.parent_after.offspring_count == 1
    assert result.parent_after.state_revision == 1


def test_child_binds_mutation_and_lineage():
    parent = organism()
    result = reproduce(parent)

    assert result.child is not None
    assert result.mutation_result is not None

    child = result.child

    assert child.lifecycle is LifecycleState.EMBRYO
    assert child.age_ticks == 0
    assert child.energy == 30
    assert child.lineage.generation == 1
    assert child.lineage.parents == (
        parent.lineage.parent_reference(),
    )
    assert (
        child.genotype.digest()
        == result.mutation_result
        .child_genotype_digest
    )


def test_stale_parent_request_rejects_atomically():
    parent = organism()

    stale = BirthRequest(
        expected_parent_digest="f" * 64,
        world_state_digest=WORLD_A,
        birth_tick=1,
        birth_ordinal=0,
    )

    result = execute_reproduction(
        parent=parent,
        request=stale,
        reproduction_policy=(
            reproduction_policy()
        ),
        mutation_policy=mutation_policy(),
    )

    assert result.accepted is False
    assert result.rejection_code is (
        ReproductionRejectionCode
        .STALE_PARENT_STATE
    )
    assert result.parent_after == parent
    assert result.child is None
    assert result.mutation_result is None
    assert result.energy_conserved is True


def test_dead_parent_has_specific_rejection():
    dead_parent = replace(
        organism(),
        lifecycle=LifecycleState.DEAD,
    )

    result = reproduce(dead_parent)

    assert result.accepted is False
    assert result.rejection_code is (
        ReproductionRejectionCode
        .PARENT_DEAD
    )
    assert result.parent_after == dead_parent


def test_nonreproductive_parent_is_rejected():
    parent = organism(
        lifecycle=LifecycleState.ALIVE,
    )

    result = reproduce(parent)

    assert result.accepted is False
    assert result.rejection_code is (
        ReproductionRejectionCode
        .PARENT_NOT_REPRODUCTIVE
    )


def test_too_young_parent_is_rejected():
    parent = organism(
        age_ticks=4,
    )

    result = reproduce(parent)

    assert result.accepted is False
    assert result.rejection_code is (
        ReproductionRejectionCode
        .PARENT_TOO_YOUNG
    )


def test_offspring_limit_is_enforced():
    parent = organism(
        offspring_count=3,
    )

    result = reproduce(parent)

    assert result.accepted is False
    assert result.rejection_code is (
        ReproductionRejectionCode
        .OFFSPRING_LIMIT_REACHED
    )


def test_parent_energy_threshold_is_enforced():
    parent = organism(
        energy=79,
    )

    result = reproduce(parent)

    assert result.accepted is False
    assert result.rejection_code is (
        ReproductionRejectionCode
        .PARENT_ENERGY_BELOW_THRESHOLD
    )


def test_parent_debit_is_enforced_separately():
    parent = organism(
        energy=35,
    )

    result = reproduce(
        parent,
        policy=reproduction_policy(
            minimum_parent_energy=30,
            offspring_energy_endowment=30,
            reproduction_energy_cost=10,
        ),
    )

    assert result.accepted is False
    assert result.rejection_code is (
        ReproductionRejectionCode
        .PARENT_ENERGY_BELOW_DEBIT
    )


def test_birth_ordinal_changes_child_identity():
    parent = organism()

    first = reproduce(
        parent,
        birth_ordinal=0,
    )

    second = reproduce(
        parent,
        birth_ordinal=1,
    )

    assert first.child is not None
    assert second.child is not None
    assert (
        first.child.organism_id
        != second.child.organism_id
    )


def test_world_digest_changes_mutation_seed():
    parent = organism()

    first = reproduce(
        parent,
        world_digest=WORLD_A,
    )

    second = reproduce(
        parent,
        world_digest=WORLD_B,
    )

    assert first.mutation_result is not None
    assert second.mutation_result is not None

    assert (
        first.mutation_result
        .mutation_seed_digest
        != second.mutation_result
        .mutation_seed_digest
    )
