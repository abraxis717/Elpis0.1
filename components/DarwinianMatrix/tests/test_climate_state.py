from __future__ import annotations

import torch

from DarwinianMatrix.climate.state import (
    ClimateDynamicsState,
)
from DarwinianMatrix.geometry import (
    GRID_CELLS,
    MATRIX_CELLS,
    build_region_map,
    directed_transition_id,
)


GRID = torch.tensor([
    5,3,4,6,7,8,9,1,2,
    6,7,2,1,9,5,3,4,8,
    1,9,8,3,4,2,5,6,7,
    8,5,9,7,6,1,4,2,3,
    4,2,6,8,5,3,7,9,1,
    7,1,3,9,2,4,8,5,6,
    9,6,1,5,3,7,2,8,4,
    2,8,7,4,1,9,6,3,5,
    3,4,5,2,8,6,1,7,9,
])


def row_swapped_grid() -> torch.Tensor:
    matrix = GRID.reshape(9, 9)
    order = torch.tensor(
        [1, 0, 2, 3, 4, 5, 6, 7, 8]
    )
    return matrix[order].reshape(-1).clone()


def test_uninitialized_state_rejects_views() -> None:
    state = ClimateDynamicsState.empty()

    assert not state.initialized

    try:
        state.regional_read_view()
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "Uninitialized regional view was accepted."
        )

    try:
        state.lattice_read_view(
            build_region_map()
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "Uninitialized lattice view was accepted."
        )


def test_first_advance_initializes_without_shock() -> None:
    state = ClimateDynamicsState.empty()
    initialized = state.advance(GRID)

    assert not state.initialized
    assert initialized.initialized

    view = initialized.regional_read_view()

    assert torch.equal(
        view.previous.long(),
        GRID,
    )
    assert torch.equal(
        view.current.long(),
        GRID,
    )
    assert not bool(view.changed.any())
    assert int(view.transition_age.sum()) == 0

    expected_ids = directed_transition_id(
        GRID,
        GRID,
    )

    assert torch.equal(
        view.transition_ids,
        expected_ids,
    )


def test_same_grid_increments_all_transition_ages() -> None:
    first = ClimateDynamicsState.empty().advance(GRID)
    second = first.advance(GRID)
    third = second.advance(GRID)

    assert torch.equal(
        second.transition_age,
        torch.ones(
            GRID_CELLS,
            dtype=torch.int32,
        ),
    )

    assert torch.equal(
        third.transition_age,
        torch.full(
            (GRID_CELLS,),
            2,
            dtype=torch.int32,
        ),
    )

    assert not bool(second.changed.any())
    assert not bool(third.changed.any())


def test_changed_regions_reset_and_unchanged_regions_age() -> None:
    first = ClimateDynamicsState.empty().advance(GRID)
    second = first.advance(GRID)

    changed_grid = row_swapped_grid()
    third = second.advance(changed_grid)

    expected_changed = GRID.ne(changed_grid)

    assert int(expected_changed.sum()) == 18
    assert torch.equal(
        third.changed,
        expected_changed,
    )

    assert torch.all(
        third.transition_age[expected_changed] == 0
    )
    assert torch.all(
        third.transition_age[~expected_changed] == 2
    )

    assert torch.equal(
        third.previous.long(),
        GRID,
    )
    assert torch.equal(
        third.current.long(),
        changed_grid,
    )


def test_advance_does_not_mutate_source_state() -> None:
    first = ClimateDynamicsState.empty().advance(GRID)
    before = first.digest()

    second = first.advance(row_swapped_grid())

    assert first.digest() == before
    assert second.digest() != before
    assert torch.equal(first.current.long(), GRID)


def test_public_tensors_do_not_alias_internal_state() -> None:
    state = ClimateDynamicsState.empty().advance(GRID)

    leaked_current = state.current
    leaked_age = state.transition_age

    leaked_current[0] = 9
    leaked_age[0] = 717

    assert int(state.current[0]) == 5
    assert int(state.transition_age[0]) == 0


def test_lattice_view_expands_regions_and_age() -> None:
    state = ClimateDynamicsState.empty().advance(GRID)
    state = state.advance(GRID)

    region_map = build_region_map()
    lattice = state.lattice_read_view(region_map)

    assert lattice.current.shape == (MATRIX_CELLS,)
    assert lattice.transition_age.shape == (
        MATRIX_CELLS,
    )

    for region in range(GRID_CELLS):
        members = region_map.eq(region)

        assert torch.all(
            lattice.current[members]
            == int(GRID[region])
        )
        assert torch.all(
            lattice.transition_age[members] == 1
        )

    climate, age = lattice.ecology_inputs()

    assert climate.current.shape == (MATRIX_CELLS,)
    assert age.shape == (MATRIX_CELLS,)


def test_digest_is_deterministic_and_sensitive() -> None:
    first = ClimateDynamicsState.empty().advance(GRID)
    second = ClimateDynamicsState.empty().advance(GRID)
    changed = first.advance(row_swapped_grid())

    assert first.digest() == second.digest()
    assert first.digest() != changed.digest()


def test_invalid_grid_is_rejected_without_mutation() -> None:
    state = ClimateDynamicsState.empty().advance(GRID)
    before = state.digest()

    invalid = GRID.clone()
    invalid[0], invalid[1] = (
        invalid[1].clone(),
        invalid[0].clone(),
    )

    try:
        state.advance(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Invalid Grid81 was accepted."
        )

    assert state.digest() == before


def test_clone_is_exact_and_independent() -> None:
    state = ClimateDynamicsState.empty().advance(GRID)
    state = state.advance(row_swapped_grid())

    clone = state.clone()

    assert clone.digest() == state.digest()

    leaked = clone.current
    leaked[0] = 1

    assert clone.digest() == state.digest()
