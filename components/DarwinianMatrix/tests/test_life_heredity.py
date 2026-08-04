from __future__ import annotations

import pytest

from DarwinianMatrix.life import (
    Genotype,
    IntegerGene,
    LineageIdentity,
    MutationPolicyV1,
    ParentLineageRef,
    derive_mutation_seed,
    mutate_genotype,
)


WORLD_DIGEST = "a" * 64
SECOND_WORLD_DIGEST = "b" * 64


def example_genotype() -> Genotype:
    return Genotype(
        genes=(
            IntegerGene(
                "uptake_rate",
                value=50,
                minimum=0,
                maximum=100,
                step=5,
            ),
            IntegerGene(
                "reproduction_threshold",
                value=80,
                minimum=20,
                maximum=200,
                step=10,
            ),
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
        )
    )


def test_gene_name_is_restricted():
    with pytest.raises(
        ValueError,
        match="Gene names",
    ):
        IntegerGene(
            "Bad Gene",
            value=1,
            minimum=0,
            maximum=2,
        )


def test_gene_value_must_lie_inside_bounds():
    with pytest.raises(
        ValueError,
        match="outside",
    ):
        IntegerGene(
            "energy",
            value=11,
            minimum=0,
            maximum=10,
        )


def test_gene_value_must_align_with_step():
    with pytest.raises(
        ValueError,
        match="align",
    ):
        IntegerGene(
            "energy",
            value=3,
            minimum=0,
            maximum=10,
            step=2,
        )


def test_genotype_order_is_canonical():
    genotype = example_genotype()

    assert genotype.gene_names == (
        "basal_metabolism",
        "defense",
        "reproduction_threshold",
        "uptake_rate",
    )


def test_genotype_digest_ignores_input_order():
    first = example_genotype()

    second = Genotype(
        genes=tuple(
            reversed(first.genes)
        )
    )

    assert first.digest() == second.digest()
    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )


def test_genotype_distance_is_step_normalized():
    first = example_genotype()

    second = first.replace_values(
        {
            "basal_metabolism": 16,
            "defense": 8,
            "uptake_rate": 60,
        }
    )

    assert first.distance(second) == 7


def test_genotype_distance_rejects_structure_change():
    first = example_genotype()

    second = Genotype(
        genes=(
            IntegerGene(
                "different_gene",
                value=1,
                minimum=0,
                maximum=2,
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="structures",
    ):
        first.distance(second)


def test_founder_identity_is_replayable():
    genotype = example_genotype()

    first = LineageIdentity.founder(
        birth_tick=0,
        birth_ordinal=0,
        genotype_digest=genotype.digest(),
    )

    second = LineageIdentity.founder(
        birth_tick=0,
        birth_ordinal=0,
        genotype_digest=genotype.digest(),
    )

    assert first.organism_id == second.organism_id
    assert first.generation == 0
    assert first.parents == ()
    assert first.mutation_seed_digest is None


def test_mutation_seed_ignores_parent_input_order():
    genotype = example_genotype()

    founder_a = LineageIdentity.founder(
        birth_tick=0,
        birth_ordinal=0,
        genotype_digest=genotype.digest(),
    )

    founder_b = LineageIdentity.founder(
        birth_tick=0,
        birth_ordinal=1,
        genotype_digest=genotype.digest(),
    )

    policy = MutationPolicyV1()

    first = derive_mutation_seed(
        world_state_digest=WORLD_DIGEST,
        parents=(
            founder_a.parent_reference(),
            founder_b.parent_reference(),
        ),
        birth_tick=1,
        birth_ordinal=0,
        mutation_policy_digest=(
            policy.digest()
        ),
    )

    second = derive_mutation_seed(
        world_state_digest=WORLD_DIGEST,
        parents=(
            founder_b.parent_reference(),
            founder_a.parent_reference(),
        ),
        birth_tick=1,
        birth_ordinal=0,
        mutation_policy_digest=(
            policy.digest()
        ),
    )

    assert first == second


def test_mutation_seed_changes_with_birth_ordinal():
    genotype = example_genotype()

    founder = LineageIdentity.founder(
        birth_tick=0,
        birth_ordinal=0,
        genotype_digest=genotype.digest(),
    )

    policy = MutationPolicyV1()

    first = derive_mutation_seed(
        world_state_digest=WORLD_DIGEST,
        parents=(founder.parent_reference(),),
        birth_tick=1,
        birth_ordinal=0,
        mutation_policy_digest=(
            policy.digest()
        ),
    )

    second = derive_mutation_seed(
        world_state_digest=WORLD_DIGEST,
        parents=(founder.parent_reference(),),
        birth_tick=1,
        birth_ordinal=1,
        mutation_policy_digest=(
            policy.digest()
        ),
    )

    assert first != second


def test_offspring_generation_and_parent_order():
    genotype = example_genotype()

    founder_a = LineageIdentity.founder(
        birth_tick=0,
        birth_ordinal=0,
        genotype_digest=genotype.digest(),
    )

    founder_b = LineageIdentity.founder(
        birth_tick=0,
        birth_ordinal=1,
        genotype_digest=genotype.digest(),
    )

    policy = MutationPolicyV1()

    seed = derive_mutation_seed(
        world_state_digest=WORLD_DIGEST,
        parents=(
            founder_b.parent_reference(),
            founder_a.parent_reference(),
        ),
        birth_tick=1,
        birth_ordinal=0,
        mutation_policy_digest=(
            policy.digest()
        ),
    )

    first = LineageIdentity.offspring(
        parents=(
            founder_a.parent_reference(),
            founder_b.parent_reference(),
        ),
        birth_tick=1,
        birth_ordinal=0,
        genotype_digest=genotype.digest(),
        mutation_seed_digest=seed,
    )

    second = LineageIdentity.offspring(
        parents=(
            founder_b.parent_reference(),
            founder_a.parent_reference(),
        ),
        birth_tick=1,
        birth_ordinal=0,
        genotype_digest=genotype.digest(),
        mutation_seed_digest=seed,
    )

    assert first.generation == 1
    assert first.organism_id == second.organism_id
    assert first.parents == second.parents


def test_mutation_is_deterministic():
    parent = example_genotype()

    policy = MutationPolicyV1(
        activation_probability_ppm=1_000_000,
        max_mutated_loci=2,
        max_step_multiple=3,
    )

    first = mutate_genotype(
        parent=parent,
        mutation_seed_digest=WORLD_DIGEST,
        policy=policy,
    )

    second = mutate_genotype(
        parent=parent,
        mutation_seed_digest=WORLD_DIGEST,
        policy=policy,
    )

    assert first.digest() == second.digest()
    assert first.events == second.events
    assert (
        first.child_genotype.digest()
        == second.child_genotype.digest()
    )


def test_mutation_is_bounded():
    parent = example_genotype()

    policy = MutationPolicyV1(
        activation_probability_ppm=1_000_000,
        max_mutated_loci=2,
        max_step_multiple=3,
    )

    result = mutate_genotype(
        parent=parent,
        mutation_seed_digest=WORLD_DIGEST,
        policy=policy,
    )

    assert 1 <= len(result.events) <= 2

    for event in result.events:
        gene = parent.gene(
            event.gene_name
        )

        assert abs(event.delta) <= (
            gene.step
            * policy.max_step_multiple
        )

        assert (
            gene.minimum
            <= event.new_value
            <= gene.maximum
        )


def test_mutation_does_not_modify_parent():
    parent = example_genotype()
    before = parent.digest()

    result = mutate_genotype(
        parent=parent,
        mutation_seed_digest=WORLD_DIGEST,
        policy=MutationPolicyV1(
            activation_probability_ppm=1_000_000,
            max_mutated_loci=2,
            max_step_multiple=2,
        ),
    )

    assert parent.digest() == before
    assert result.parent_genotype_digest == before
    assert result.child_genotype is not parent


def test_mutation_result_binds_seed():
    parent = example_genotype()

    policy = MutationPolicyV1(
        activation_probability_ppm=1_000_000,
        max_mutated_loci=2,
        max_step_multiple=2,
    )

    first = mutate_genotype(
        parent=parent,
        mutation_seed_digest=WORLD_DIGEST,
        policy=policy,
    )

    second = mutate_genotype(
        parent=parent,
        mutation_seed_digest=SECOND_WORLD_DIGEST,
        policy=policy,
    )

    assert first.digest() != second.digest()


def test_zero_probability_can_produce_no_mutation():
    parent = example_genotype()

    result = mutate_genotype(
        parent=parent,
        mutation_seed_digest=WORLD_DIGEST,
        policy=MutationPolicyV1(
            activation_probability_ppm=0,
            ensure_at_least_one=False,
        ),
    )

    assert result.mutated is False
    assert result.events == ()
    assert (
        result.child_genotype.digest()
        == parent.digest()
    )


def test_ensure_at_least_one_forces_mutation():
    parent = example_genotype()

    result = mutate_genotype(
        parent=parent,
        mutation_seed_digest=WORLD_DIGEST,
        policy=MutationPolicyV1(
            activation_probability_ppm=0,
            max_mutated_loci=1,
            max_step_multiple=1,
            ensure_at_least_one=True,
        ),
    )

    assert result.mutated is True
    assert len(result.events) == 1


def test_immovable_genotype_remains_unchanged():
    parent = Genotype(
        genes=(
            IntegerGene(
                "fixed",
                value=7,
                minimum=7,
                maximum=7,
            ),
        )
    )

    result = mutate_genotype(
        parent=parent,
        mutation_seed_digest=WORLD_DIGEST,
        policy=MutationPolicyV1(
            activation_probability_ppm=1_000_000,
            ensure_at_least_one=True,
        ),
    )

    assert result.mutated is False
    assert (
        result.child_genotype.digest()
        == parent.digest()
    )


def test_mutation_policy_rejects_invalid_probability():
    with pytest.raises(
        ValueError,
        match="probability",
    ):
        MutationPolicyV1(
            activation_probability_ppm=1_000_001,
        )
