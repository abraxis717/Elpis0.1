from __future__ import annotations

from dataclasses import replace

import pytest

from DarwinianMatrix.life import (
    Genotype,
    IntegerGene,
    LifecycleState,
    LineageIdentity,
    OrganismState,
    PopulationState,
    SelectionCandidateBinding,
    SelectionCommitPolicyV1,
    SelectionCommitRejectionCode,
    SelectionProposal,
    SelectionSolverKind,
    commit_selection,
)


WORLD_A = "a" * 64
WORLD_B = "b" * 64

PROBLEM_DIGEST = "1" * 64
COMPILATION_DIGEST = "2" * 64
QUBO_DIGEST = "3" * 64
SOLVER_DIGEST = "4" * 64


def organism(
    *,
    value: int,
    ordinal: int,
    lifecycle: LifecycleState = (
        LifecycleState.ALIVE
    ),
) -> OrganismState:
    genome = Genotype(
        genes=(
            IntegerGene(
                "trait",
                value=value,
                minimum=0,
                maximum=4,
            ),
        )
    )

    lineage = LineageIdentity.founder(
        birth_tick=0,
        birth_ordinal=ordinal,
        genotype_digest=genome.digest(),
    )

    return OrganismState(
        lineage=lineage,
        genotype=genome,
        energy=100,
        age_ticks=(
            0
            if lifecycle is LifecycleState.EMBRYO
            else 10
        ),
        lifecycle=lifecycle,
    )


def population() -> PopulationState:
    return PopulationState(
        source_world_state_digest=(
            WORLD_A
        ),
        revision=7,
        organisms=(
            organism(
                value=0,
                ordinal=0,
            ),
            organism(
                value=1,
                ordinal=1,
            ),
            organism(
                value=4,
                ordinal=2,
                lifecycle=(
                    LifecycleState.REPRODUCTIVE
                ),
            ),
            organism(
                value=2,
                ordinal=3,
                lifecycle=(
                    LifecycleState.EMBRYO
                ),
            ),
        ),
    )


def candidate_organisms(
    state: PopulationState,
):
    return tuple(
        organism
        for organism in state.organisms
        if organism.lifecycle
        in {
            LifecycleState.ALIVE,
            LifecycleState.REPRODUCTIVE,
        }
    )


def candidate_bindings(
    state: PopulationState,
):
    return tuple(
        SelectionCandidateBinding(
            organism_id=organism.organism_id,
            organism_state_digest=(
                organism.digest()
            ),
            genotype_digest=(
                organism.genotype.digest()
            ),
            fitness_record_digest=(
                str(index + 5) * 64
            ),
            scalar_fitness=(
                10 - index
            ),
            novelty=index,
            lifecycle=(
                organism.lifecycle.value
            ),
        )
        for index, organism in enumerate(
            candidate_organisms(state)
        )
    )


def proposal(
    state: PopulationState,
    *,
    selected_ids: set[str] | None = None,
    exact_energy: str = "-20",
    optimum_energy: str = "-20",
    bindings=None,
) -> SelectionProposal:
    candidates = candidate_organisms(
        state
    )

    variable_order = tuple(
        sorted(
            organism.organism_id
            for organism in candidates
        )
    )

    if selected_ids is None:
        selected_ids = {
            candidates[0].organism_id,
            candidates[2].organism_id,
        }

    bits = tuple(
        1
        if organism_id in selected_ids
        else 0
        for organism_id in variable_order
    )

    if bindings is None:
        bindings = candidate_bindings(
            state
        )

    return SelectionProposal.create_verified(
        population=state,
        problem_digest=PROBLEM_DIGEST,
        compilation_digest=(
            COMPILATION_DIGEST
        ),
        qubo_digest=QUBO_DIGEST,
        solver_kind=(
            SelectionSolverKind
            .EXACT_CLASSICAL_ORACLE_V1
        ),
        solver_artifact_digest=(
            SOLVER_DIGEST
        ),
        variable_order=variable_order,
        bits_variable_order=bits,
        candidate_bindings=bindings,
        survivor_count=2,
        exact_energy=exact_energy,
        reference_optimum_energy=(
            optimum_energy
        ),
    )


def test_population_order_is_canonical():
    first = population()

    second = PopulationState(
        source_world_state_digest=(
            first.source_world_state_digest
        ),
        revision=first.revision,
        organisms=tuple(
            reversed(first.organisms)
        ),
    )

    assert first.digest() == second.digest()
    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )


def test_population_rejects_duplicate_identity():
    state = population()

    with pytest.raises(
        ValueError,
        match="unique",
    ):
        PopulationState(
            source_world_state_digest=(
                WORLD_A
            ),
            revision=0,
            organisms=(
                state.organisms[0],
                state.organisms[0],
            ),
        )


def test_proposal_rejects_nonbinary_bits():
    state = population()
    bindings = candidate_bindings(state)

    variable_order = tuple(
        binding.organism_id
        for binding in bindings
    )

    with pytest.raises(
        ValueError,
        match="zero or one",
    ):
        SelectionProposal.create_verified(
            population=state,
            problem_digest=(
                PROBLEM_DIGEST
            ),
            compilation_digest=(
                COMPILATION_DIGEST
            ),
            qubo_digest=QUBO_DIGEST,
            solver_kind=(
                SelectionSolverKind
                .EXACT_CLASSICAL_ORACLE_V1
            ),
            solver_artifact_digest=(
                SOLVER_DIGEST
            ),
            variable_order=variable_order,
            bits_variable_order=(
                1,
                2,
                0,
            ),
            candidate_bindings=bindings,
            survivor_count=2,
            exact_energy="-20",
            reference_optimum_energy="-20",
        )


def test_proposal_detects_tampering():
    state = population()
    verified = proposal(state)

    with pytest.raises(
        ValueError,
        match="verification",
    ):
        replace(
            verified,
            solver_artifact_digest=(
                "f" * 64
            ),
        )


def test_accepted_commit_transitions_excluded_candidate():
    state = population()
    verified = proposal(state)

    result = commit_selection(
        population=state,
        proposal=verified,
    )

    assert result.accepted is True
    assert len(
        result.transitioned_to_dying
    ) == 1

    excluded_id = (
        result.transitioned_to_dying[0]
    )

    assert (
        result.population_after
        .organism(excluded_id)
        .lifecycle
        is LifecycleState.DYING
    )


def test_selected_organisms_remain_unchanged():
    state = population()
    verified = proposal(state)

    result = commit_selection(
        population=state,
        proposal=verified,
    )

    for organism_id in verified.selected_ids:
        assert (
            result.population_after
            .organism(organism_id)
            == state.organism(organism_id)
        )


def test_noncandidate_embryo_remains_unchanged():
    state = population()
    embryo = next(
        organism
        for organism in state.organisms
        if organism.lifecycle
        is LifecycleState.EMBRYO
    )

    result = commit_selection(
        population=state,
        proposal=proposal(state),
    )

    assert (
        result.population_after
        .organism(embryo.organism_id)
        == embryo
    )


def test_accepted_commit_increments_population_revision():
    state = population()

    result = commit_selection(
        population=state,
        proposal=proposal(state),
    )

    assert (
        result.population_after.revision
        == state.revision + 1
    )

    assert (
        result.population_after.digest()
        != state.digest()
    )


def test_world_state_mismatch_rejects_atomically():
    state = population()
    verified = proposal(state)

    changed = PopulationState(
        source_world_state_digest=(
            WORLD_B
        ),
        revision=state.revision,
        organisms=state.organisms,
    )

    result = commit_selection(
        population=changed,
        proposal=verified,
    )

    assert result.accepted is False
    assert result.rejection_code is (
        SelectionCommitRejectionCode
        .WORLD_STATE_MISMATCH
    )
    assert (
        result.population_after
        == changed
    )


def test_revision_mismatch_rejects_atomically():
    state = population()
    verified = proposal(state)

    changed = PopulationState(
        source_world_state_digest=(
            state.source_world_state_digest
        ),
        revision=state.revision + 1,
        organisms=state.organisms,
    )

    result = commit_selection(
        population=changed,
        proposal=verified,
    )

    assert result.accepted is False
    assert result.rejection_code is (
        SelectionCommitRejectionCode
        .POPULATION_REVISION_MISMATCH
    )
    assert result.population_after == changed


def test_stale_population_rejects_atomically():
    state = population()
    verified = proposal(state)

    changed_organism = replace(
        state.organisms[0],
        energy=99,
        state_revision=1,
    )

    changed = PopulationState(
        source_world_state_digest=(
            state.source_world_state_digest
        ),
        revision=state.revision,
        organisms=(
            changed_organism,
            *state.organisms[1:],
        ),
    )

    result = commit_selection(
        population=changed,
        proposal=verified,
    )

    assert result.accepted is False
    assert result.rejection_code is (
        SelectionCommitRejectionCode
        .STALE_POPULATION
    )
    assert result.population_after == changed


def test_stale_candidate_binding_rejects():
    state = population()
    bindings = list(
        candidate_bindings(state)
    )

    bindings[0] = replace(
        bindings[0],
        organism_state_digest=(
            "f" * 64
        ),
    )

    verified = proposal(
        state,
        bindings=tuple(bindings),
    )

    result = commit_selection(
        population=state,
        proposal=verified,
    )

    assert result.accepted is False
    assert result.rejection_code is (
        SelectionCommitRejectionCode
        .STALE_CANDIDATE_BINDING
    )
    assert result.population_after == state


def test_optimality_gap_policy_rejects():
    state = population()

    verified = proposal(
        state,
        exact_energy="-19",
        optimum_energy="-20",
    )

    result = commit_selection(
        population=state,
        proposal=verified,
        policy=SelectionCommitPolicyV1(
            maximum_optimality_gap=0,
        ),
    )

    assert result.accepted is False
    assert result.rejection_code is (
        SelectionCommitRejectionCode
        .OPTIMALITY_GAP_EXCEEDED
    )
    assert result.population_after == state
