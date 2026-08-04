from __future__ import annotations

import torch

from DarwinianMatrix.geometry import (
    BOUNDARY_REFLECTIVE,
    BOUNDARY_TOROIDAL,
    GRID_CELLS,
    GRID_SIDE,
    MATRIX_CELLS,
    MATRIX_SIDE,
    PATCH_RADIUS,
    PATCH_SIDE,
    STENCIL_MOORE_8,
    STENCIL_VON_NEUMANN_4,
    ClimateSidecar,
    build_epicenter_index,
    build_neighbor_table,
    build_region_map,
    diagnostic_epicenter_coordinate,
    directed_transition_id,
    grid_coordinate,
    grid_index,
    matrix_coordinate,
    matrix_index,
    patch_membership,
    region_index,
    validate_partial_grid81,
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


def naive_neighbors(
    row: int,
    col: int,
    *,
    mode: str,
    offsets: tuple[tuple[int, int], ...],
) -> list[int]:
    source = matrix_index(row, col)
    neighbors: list[int] = []

    for delta_row, delta_col in offsets:
        neighbor_row = row + delta_row
        neighbor_col = col + delta_col

        if mode == BOUNDARY_TOROIDAL:
            neighbor_row %= MATRIX_SIDE
            neighbor_col %= MATRIX_SIDE
            neighbors.append(
                matrix_index(neighbor_row, neighbor_col)
            )
            continue

        if not (
            0 <= neighbor_row < MATRIX_SIDE
            and 0 <= neighbor_col < MATRIX_SIDE
        ):
            neighbors.append(source)
        else:
            neighbors.append(
                matrix_index(neighbor_row, neighbor_col)
            )

    return neighbors


def test_geometry_constants() -> None:
    assert GRID_SIDE == 9
    assert GRID_CELLS == 81
    assert PATCH_RADIUS == 4
    assert PATCH_SIDE == 9
    assert MATRIX_SIDE == 81
    assert MATRIX_CELLS == 6561


def test_grid_index_round_trip_exhaustive() -> None:
    for index in range(GRID_CELLS):
        row, col = grid_coordinate(index)
        assert grid_index(row, col) == index


def test_matrix_index_round_trip_exhaustive() -> None:
    for index in range(MATRIX_CELLS):
        row, col = matrix_coordinate(index)
        assert matrix_index(row, col) == index


def test_region_map_is_complete_and_balanced() -> None:
    region_map = build_region_map()

    assert region_map.shape == (MATRIX_CELLS,)
    assert int(region_map.min()) == 0
    assert int(region_map.max()) == GRID_CELLS - 1

    counts = torch.bincount(
        region_map.long(),
        minlength=GRID_CELLS,
    )

    assert counts.shape == (GRID_CELLS,)
    assert torch.equal(
        counts,
        torch.full(
            (GRID_CELLS,),
            PATCH_SIDE * PATCH_SIDE,
            dtype=torch.int64,
        ),
    )


def test_patch_membership_matches_region_map() -> None:
    region_map = build_region_map()

    for index in range(MATRIX_CELLS):
        row, col = matrix_coordinate(index)
        region_row, region_col, local_row, local_col = (
            patch_membership(row, col)
        )

        assert 0 <= local_row < PATCH_SIDE
        assert 0 <= local_col < PATCH_SIDE

        expected_region = grid_index(region_row, region_col)

        assert region_index(row, col) == expected_region
        assert int(region_map[index]) == expected_region


def test_diagnostic_epicenters_are_unique_and_correct() -> None:
    epicenters = build_epicenter_index()

    assert epicenters.shape == (GRID_CELLS,)
    assert torch.unique(epicenters).numel() == GRID_CELLS

    for grid_row in range(GRID_SIDE):
        for grid_col in range(GRID_SIDE):
            source_index = grid_index(grid_row, grid_col)
            matrix_row, matrix_col = diagnostic_epicenter_coordinate(
                grid_row,
                grid_col,
            )
            destination_index = matrix_index(
                matrix_row,
                matrix_col,
            )

            assert int(epicenters[source_index]) == destination_index
            assert region_index(
                matrix_row,
                matrix_col,
            ) == source_index


def test_internal_patch_borders_are_contiguous() -> None:
    table = build_neighbor_table(
        mode=BOUNDARY_REFLECTIVE,
        stencil=STENCIL_VON_NEUMANN_4,
    )

    for boundary_col in range(8, MATRIX_SIDE - 1, PATCH_SIDE):
        for row in range(MATRIX_SIDE):
            left = matrix_index(row, boundary_col)
            right = matrix_index(row, boundary_col + 1)

            assert right in table[left].tolist()
            assert left in table[right].tolist()

    for boundary_row in range(8, MATRIX_SIDE - 1, PATCH_SIDE):
        for col in range(MATRIX_SIDE):
            top = matrix_index(boundary_row, col)
            bottom = matrix_index(boundary_row + 1, col)

            assert bottom in table[top].tolist()
            assert top in table[bottom].tolist()


def test_neighbor_tables_match_naive_reference() -> None:
    stencil_offsets = {
        STENCIL_VON_NEUMANN_4: (
            (-1, 0),
            (0, -1),
            (0, 1),
            (1, 0),
        ),
        STENCIL_MOORE_8: (
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        ),
    }

    for mode in (
        BOUNDARY_REFLECTIVE,
        BOUNDARY_TOROIDAL,
    ):
        for stencil, offsets in stencil_offsets.items():
            table = build_neighbor_table(
                mode=mode,
                stencil=stencil,
            )

            assert table.shape == (
                MATRIX_CELLS,
                len(offsets),
            )

            for row in range(MATRIX_SIDE):
                for col in range(MATRIX_SIDE):
                    index = matrix_index(row, col)

                    assert table[index].tolist() == naive_neighbors(
                        row,
                        col,
                        mode=mode,
                        offsets=offsets,
                    )


def test_exact_solved_grid_validation() -> None:
    assert validate_solved_grid81(VALID_GRID)

    invalid_same_sum = VALID_GRID.clone()
    invalid_same_sum[0], invalid_same_sum[1] = (
        invalid_same_sum[1].clone(),
        invalid_same_sum[0].clone(),
    )

    assert int(invalid_same_sum.sum()) == 405
    assert not validate_solved_grid81(invalid_same_sum)


def test_partial_grid_validation_is_separate() -> None:
    partial = VALID_GRID.clone()
    partial[0] = 0
    partial[10] = 0

    assert validate_partial_grid81(partial)
    assert not validate_solved_grid81(partial)

    contradiction = partial.clone()
    contradiction[0] = contradiction[1]

    assert not validate_partial_grid81(contradiction)


def test_transition_ids_are_bijective_and_directed() -> None:
    pairs = torch.tensor(
        [
            (previous, current)
            for previous in range(1, 10)
            for current in range(1, 10)
        ],
        dtype=torch.int64,
    )

    ids = directed_transition_id(
        pairs[:, 0],
        pairs[:, 1],
    )

    assert ids.shape == (81,)
    assert int(ids.min()) == 0
    assert int(ids.max()) == 80
    assert torch.unique(ids).numel() == 81

    forward = int(
        directed_transition_id(
            torch.tensor([2]),
            torch.tensor([7]),
        )[0]
    )
    reverse = int(
        directed_transition_id(
            torch.tensor([7]),
            torch.tensor([2]),
        )[0]
    )

    assert forward != reverse


def test_climate_sidecar_copies_inputs_and_outputs() -> None:
    sidecar = ClimateSidecar()
    source = VALID_GRID.clone()

    first = sidecar.trm_write(source)

    assert sidecar.initialized
    assert not bool(first.changed.any())
    assert torch.equal(first.current.long(), VALID_GRID)
    assert torch.equal(first.previous.long(), VALID_GRID)

    source[0] = 9
    assert int(sidecar.current[0]) == 5

    leaked = sidecar.current
    leaked[0] = 9
    assert int(sidecar.current[0]) == 5


def test_climate_sidecar_tracks_exact_changes() -> None:
    sidecar = ClimateSidecar()
    sidecar.trm_write(VALID_GRID)

    changed_grid = VALID_GRID.clone()

    # Swapping two values makes the grid invalid and must be rejected.
    changed_grid[0], changed_grid[1] = (
        changed_grid[1].clone(),
        changed_grid[0].clone(),
    )

    try:
        sidecar.trm_write(changed_grid)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid TRM grid was accepted.")

    alternate = torch.roll(
        VALID_GRID.reshape(9, 9),
        shifts=3,
        dims=0,
    ).reshape(-1)

    assert validate_solved_grid81(alternate)

    update = sidecar.trm_write(alternate)
    expected_changed = VALID_GRID.ne(alternate)

    assert torch.equal(update.changed.cpu(), expected_changed)
    assert torch.equal(update.previous.long().cpu(), VALID_GRID)
    assert torch.equal(update.current.long().cpu(), alternate)


def test_lattice_climate_view_is_detached() -> None:
    sidecar = ClimateSidecar()
    sidecar.trm_write(VALID_GRID)

    region_map = build_region_map()
    view = sidecar.lattice_read_view(region_map)

    assert view.current.shape == (MATRIX_CELLS,)
    assert view.previous.shape == (MATRIX_CELLS,)
    assert view.transition_ids.shape == (MATRIX_CELLS,)
    assert view.changed.shape == (MATRIX_CELLS,)

    for region in range(GRID_CELLS):
        members = region_map == region

        assert torch.all(
            view.current[members]
            == int(VALID_GRID[region])
        )

    view.current[0] = 9
    assert int(sidecar.current[0]) == 5


def test_sidecar_lock_blocks_upstream_write() -> None:
    sidecar = ClimateSidecar()
    sidecar.trm_write(VALID_GRID)
    sidecar.lock()

    try:
        sidecar.trm_write(VALID_GRID)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Locked climate sidecar accepted a write.")

    sidecar.unlock()
    sidecar.trm_write(VALID_GRID)
