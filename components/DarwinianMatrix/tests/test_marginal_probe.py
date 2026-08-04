from __future__ import annotations

import torch

from DarwinianMatrix.ecology.engine import (
    PRODUCER,
    EcologyState,
)
from DarwinianMatrix.evaluation.marginal_probe import (
    DIAGONAL_REGION_EDGES,
    ORTHOGONAL_REGION_EDGES,
    climate_marginals,
    edge_metrics,
    instantaneous_suitability,
    probe_digest,
    run_arrangement_probe,
    valid_arrangements,
)
from DarwinianMatrix.geometry import (
    MATRIX_CELLS,
    build_region_map,
    validate_solved_grid81,
)


VALID_GRID = torch.tensor(
    [
        5, 3, 4, 6, 7, 8, 9, 1, 2,
        6, 7, 2, 1, 9, 5, 3, 4, 8,
        1, 9, 8, 3, 4, 2, 5, 6, 7,
        8, 5, 9, 7, 6, 1, 4, 2, 3,
        4, 2, 6, 8, 5, 3, 7, 9, 1,
        7, 1, 3, 9, 2, 4, 8, 5, 6,
        9, 6, 1, 5, 3, 7, 2, 8, 4,
        2, 8, 7, 4, 1, 9, 6, 3, 5,
        3, 4, 5, 2, 8, 6, 1, 7, 9,
    ],
    dtype=torch.int64,
)


def homogeneous_state(genome: float = 0.5) -> EcologyState:
    state = EcologyState()
    state.ctype.fill_(PRODUCER)
    state.genome.fill_(genome)
    state.energy.fill_(1.0)
    state.lineage.copy_(
        torch.arange(
            MATRIX_CELLS,
            dtype=torch.int32,
        )
    )
    state.validate()
    return state


def heterogeneous_state() -> EcologyState:
    state = EcologyState()
    state.ctype.fill_(PRODUCER)
    state.energy.fill_(1.0)
    state.lineage.copy_(
        torch.arange(
            MATRIX_CELLS,
            dtype=torch.int32,
        )
    )

    indices = torch.arange(
        MATRIX_CELLS,
        dtype=torch.int64,
    )
    rows = indices // 81
    cols = indices % 81

    state.genome.copy_(
        (
            0.65 * cols.float() / 80.0
            + 0.35 * rows.float() / 80.0
        ).clamp(0.0, 1.0)
    )

    state.validate()
    return state


def test_arrangement_transforms_remain_valid() -> None:
    variants = valid_arrangements(VALID_GRID)

    assert len(variants) == 8

    digests = set()

    for candidate in variants.values():
        assert validate_solved_grid81(candidate)
        digests.add(
            candidate.numpy().tobytes()
        )

    assert len(digests) >= 6


def test_climate_marginals_are_arrangement_invariant() -> None:
    variants = valid_arrangements(VALID_GRID)
    reference = climate_marginals(VALID_GRID)

    assert reference.digit_counts == (9,) * 9
    assert reference.digit_sum == 405

    for candidate in variants.values():
        assert climate_marginals(candidate) == reference


def test_orthogonal_gradients_never_zero_for_valid_sudoku() -> None:
    for candidate in valid_arrangements(VALID_GRID).values():
        metrics = edge_metrics(
            candidate,
            include_diagonal=False,
        )

        assert metrics.edge_count == len(
            ORTHOGONAL_REGION_EDGES
        )
        assert metrics.zero_gradient_edges == 0


def test_diagonal_gradients_may_be_zero() -> None:
    metrics = edge_metrics(
        VALID_GRID,
        include_diagonal=True,
    )

    assert len(DIAGONAL_REGION_EDGES) > 0
    assert metrics.edge_count > len(
        ORTHOGONAL_REGION_EDGES
    )
    assert metrics.zero_gradient_edges >= 0


def test_edge_geometry_depends_on_arrangement() -> None:
    values = {
        (
            edge_metrics(
                candidate,
                include_diagonal=False,
            ).total_abs_gradient,
            edge_metrics(
                candidate,
                include_diagonal=False,
            ).mean_permeability,
        )
        for candidate in valid_arrangements(
            VALID_GRID
        ).values()
    }

    assert len(values) > 1


def test_homogeneous_ecology_is_arrangement_invariant() -> None:
    state = homogeneous_state(genome=0.5)

    values = [
        instantaneous_suitability(
            state,
            candidate,
        )
        for candidate in valid_arrangements(
            VALID_GRID
        ).values()
    ]

    reference = values[0]

    for value in values[1:]:
        assert abs(value - reference) <= 1e-9


def test_heterogeneous_ecology_is_arrangement_sensitive() -> None:
    state = heterogeneous_state()

    values = [
        instantaneous_suitability(
            state,
            candidate,
        )
        for candidate in valid_arrangements(
            VALID_GRID
        ).values()
    ]

    assert max(values) - min(values) > 1.0


def test_probe_does_not_mutate_ecology() -> None:
    state = heterogeneous_state()
    before = state.digest()

    run_arrangement_probe(
        state,
        VALID_GRID,
    )

    assert state.digest() == before


def test_probe_is_deterministic() -> None:
    state = heterogeneous_state()

    first = run_arrangement_probe(
        state,
        VALID_GRID,
    )
    second = run_arrangement_probe(
        state,
        VALID_GRID,
    )

    assert probe_digest(first) == probe_digest(second)


def test_probe_preserves_marginals_but_not_all_metrics() -> None:
    records = run_arrangement_probe(
        heterogeneous_state(),
        VALID_GRID,
    )

    marginal_payloads = {
        str(record.marginals.canonical_payload())
        for record in records
    }
    suitability_values = {
        round(record.instantaneous_suitability, 6)
        for record in records
    }
    gradient_values = {
        round(
            record.orthogonal_edges.total_abs_gradient,
            6,
        )
        for record in records
    }

    assert len(marginal_payloads) == 1
    assert len(suitability_values) > 1
    assert len(gradient_values) > 1


def test_region_map_remains_balanced() -> None:
    region_map = build_region_map()
    counts = torch.bincount(
        region_map.long(),
        minlength=81,
    )

    assert torch.equal(
        counts,
        torch.full(
            (81,),
            81,
            dtype=torch.int64,
        ),
    )
