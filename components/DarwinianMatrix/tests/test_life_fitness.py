from __future__ import annotations

from dataclasses import replace

import pytest

from DarwinianMatrix.life import (
    FitnessObservation,
    FitnessPolicyV1,
    Genotype,
    IntegerGene,
    LifecycleState,
    LineageIdentity,
    OrganismFitnessRecord,
    OrganismState,
)


def organism(
    *,
    lifecycle: LifecycleState = (
        LifecycleState.ALIVE
    ),
) -> OrganismState:
    genome = Genotype(
        genes=(
            IntegerGene(
                "trait",
                value=2,
                minimum=0,
                maximum=4,
            ),
        )
    )

    lineage = LineageIdentity.founder(
        birth_tick=0,
        birth_ordinal=0,
        genotype_digest=genome.digest(),
    )

    return OrganismState(
        lineage=lineage,
        genotype=genome,
        energy=100,
        age_ticks=10,
        lifecycle=lifecycle,
    )


def observation(
    *,
    energy_delta: int = 5,
) -> FitnessObservation:
    return FitnessObservation(
        window_start_tick=10,
        window_end_tick=20,
        energy_delta=energy_delta,
        survival_ticks=10,
        viable_offspring=2,
        resource_efficiency_ppm=500_000,
        ecological_damage=3,
        failed_actions=1,
    )


def policy() -> FitnessPolicyV1:
    return FitnessPolicyV1(
        energy_delta_weight=2,
        survival_tick_weight=1,
        viable_offspring_weight=10,
        resource_efficiency_weight=0,
        ecological_damage_weight=3,
        failed_action_weight=2,
    )


def test_observation_rejects_reversed_window():
    with pytest.raises(
        ValueError,
        match="precede",
    ):
        FitnessObservation(
            window_start_tick=10,
            window_end_tick=9,
            energy_delta=0,
            survival_ticks=0,
            viable_offspring=0,
            resource_efficiency_ppm=0,
            ecological_damage=0,
        )


def test_observation_rejects_negative_survival():
    with pytest.raises(
        ValueError,
        match="survival_ticks",
    ):
        FitnessObservation(
            window_start_tick=0,
            window_end_tick=10,
            energy_delta=0,
            survival_ticks=-1,
            viable_offspring=0,
            resource_efficiency_ppm=0,
            ecological_damage=0,
        )


def test_efficiency_must_be_ppm():
    with pytest.raises(
        ValueError,
        match="one million",
    ):
        FitnessObservation(
            window_start_tick=0,
            window_end_tick=10,
            energy_delta=0,
            survival_ticks=10,
            viable_offspring=0,
            resource_efficiency_ppm=1_000_001,
            ecological_damage=0,
        )


def test_policy_rejects_negative_weight():
    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        FitnessPolicyV1(
            ecological_damage_weight=-1,
        )


def test_policy_scores_exactly():
    assert policy().score(
        observation()
    ) == 29


def test_record_binds_organism_and_policy():
    subject = organism()

    record = OrganismFitnessRecord.evaluate(
        organism=subject,
        observation=observation(),
        policy=policy(),
    )

    assert record.validate_organism(
        subject
    ) is True
    assert (
        record.organism_id
        == subject.organism_id
    )
    assert record.scalar_fitness == 29


def test_record_rejects_stale_organism_digest():
    subject = organism()

    record = OrganismFitnessRecord.evaluate(
        organism=subject,
        observation=observation(),
        policy=policy(),
    )

    changed = replace(
        subject,
        energy=99,
        state_revision=1,
    )

    assert record.validate_organism(
        changed
    ) is False


def test_record_digest_changes_with_observation():
    subject = organism()

    first = OrganismFitnessRecord.evaluate(
        organism=subject,
        observation=observation(
            energy_delta=5,
        ),
        policy=policy(),
    )

    second = OrganismFitnessRecord.evaluate(
        organism=subject,
        observation=observation(
            energy_delta=4,
        ),
        policy=policy(),
    )

    assert first.digest() != second.digest()


def test_negative_energy_delta_reduces_fitness():
    positive = policy().score(
        observation(
            energy_delta=5,
        )
    )

    negative = policy().score(
        observation(
            energy_delta=-5,
        )
    )

    assert negative < positive


def test_dead_organism_can_have_historical_record():
    dead = organism(
        lifecycle=LifecycleState.DEAD,
    )

    record = OrganismFitnessRecord.evaluate(
        organism=dead,
        observation=observation(),
        policy=policy(),
    )

    assert record.lifecycle == "DEAD"
    assert record.validate_organism(dead)
