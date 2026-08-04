from __future__ import annotations

import torch

from DarwinianMatrix.climate.response import capacity, optimum, shock
from DarwinianMatrix.ecology.engine import (
    CONSUMER,
    EMPTY,
    PRODUCER,
    STRUCTURE,
    BirthCommand,
    CommandBuffer,
    EcologyBounds,
    EcologyState,
    diffuse,
    increment_age,
    metabolize,
    permeability_from_gradient,
    validate_climate_inputs_unchanged,
)
from DarwinianMatrix.geometry import (
    BOUNDARY_REFLECTIVE,
    MATRIX_CELLS,
    MATRIX_SIDE,
    STENCIL_MOORE_8,
    ClimateSidecar,
    build_neighbor_table,
    build_region_map,
    matrix_index,
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


def prepared_state() -> EcologyState:
    state = EcologyState()

    state.ctype[0] = PRODUCER
    state.genome[0] = 0.5
    state.energy[0] = 1.0
    state.lineage[0] = 10

    state.ctype[1] = CONSUMER
    state.genome[1] = 0.25
    state.energy[1] = 0.8
    state.lineage[1] = 11

    state.ctype[2] = STRUCTURE
    state.genome[2] = 0.75
    state.energy[2] = 0.4
    state.lineage[2] = 12

    return state


def climate_lattice():
    sidecar = ClimateSidecar()
    sidecar.trm_write(VALID_GRID)
    return sidecar, sidecar.lattice_read_view(build_region_map())


def test_state_uses_flat_non_aliasing_arrays() -> None:
    state = EcologyState()

    for field_name in (
        "ctype",
        "genome",
        "energy",
        "res_a",
        "res_b",
        "lineage",
        "age",
    ):
        assert getattr(state, field_name).shape == (MATRIX_CELLS,)

    assert state.res_a.data_ptr() != state.res_b.data_ptr()
    assert state.population == 0
    state.validate()


def test_state_digest_is_deterministic_and_sensitive() -> None:
    state = prepared_state()
    clone = state.clone()

    assert state.digest() == clone.digest()

    clone.energy[0] += 1.0
    assert state.digest() != clone.digest()


def test_uniform_resource_field_is_fixed_point() -> None:
    state = EcologyState()
    state.res_a.fill_(2.5)

    neighbors = build_neighbor_table(
        mode=BOUNDARY_REFLECTIVE,
        stencil=STENCIL_MOORE_8,
    )
    permeability = torch.ones(
        neighbors.shape,
        dtype=torch.float32,
    )

    diffuse(
        state,
        neighbors,
        permeability,
        rate=0.25,
    )

    assert torch.equal(
        state.res_a,
        torch.full_like(state.res_a, 2.5),
    )
    assert torch.equal(
        state.res_b,
        torch.full_like(state.res_b, 2.5),
    )


def test_diffusion_never_mutates_read_buffer() -> None:
    state = EcologyState()
    source_index = matrix_index(40, 40)
    state.res_a[source_index] = 8.0

    before = state.res_a.clone()

    neighbors = build_neighbor_table(
        mode=BOUNDARY_REFLECTIVE,
        stencil=STENCIL_MOORE_8,
    )
    permeability = torch.ones(
        neighbors.shape,
        dtype=torch.float32,
    )

    diffuse(
        state,
        neighbors,
        permeability,
        rate=0.15,
    )

    assert torch.equal(state.res_a, before)
    assert not torch.equal(state.res_b, before)

    state.swap_resource_buffers()

    assert not torch.equal(state.res_a, before)
    assert state.res_a.data_ptr() != state.res_b.data_ptr()


def test_diffusion_conserves_total_resource() -> None:
    torch.manual_seed(717)

    state = EcologyState()
    state.res_a.copy_(torch.rand(MATRIX_CELLS))

    neighbors = build_neighbor_table(
        mode=BOUNDARY_REFLECTIVE,
        stencil=STENCIL_MOORE_8,
    )
    permeability = torch.ones(
        neighbors.shape,
        dtype=torch.float32,
    )

    total_before = state.res_a.sum()

    diffuse(
        state,
        neighbors,
        permeability,
        rate=0.1,
    )

    total_after = state.res_b.sum()

    assert torch.isclose(
        total_before,
        total_after,
        rtol=1e-5,
        atol=1e-5,
    )


def test_climate_gradient_reduces_cross_border_permeability() -> None:
    _, climate = climate_lattice()

    neighbors = build_neighbor_table(
        mode=BOUNDARY_REFLECTIVE,
        stencil=STENCIL_MOORE_8,
    )
    permeability = permeability_from_gradient(
        climate.current,
        neighbors,
        alpha=0.5,
    )

    assert permeability.shape == neighbors.shape
    assert bool((permeability >= 0.0).all())
    assert bool((permeability <= 1.0).all())

    interior_index = matrix_index(4, 4)
    border_index = matrix_index(4, 8)

    interior_neighbors = neighbors[interior_index]
    border_neighbors = neighbors[border_index]

    interior_values = climate.current[
        interior_neighbors.long()
    ]
    border_values = climate.current[
        border_neighbors.long()
    ]

    interior_local = climate.current[interior_index]
    border_local = climate.current[border_index]

    same_interior = interior_values.eq(interior_local)
    different_border = border_values.ne(border_local)

    assert bool(same_interior.any())
    assert bool(different_border.any())

    assert torch.all(
        permeability[interior_index][same_interior] == 1.0
    )
    assert torch.all(
        permeability[border_index][different_border] < 1.0
    )


def test_command_buffer_defers_birth_until_flush() -> None:
    state = EcologyState()
    commands = CommandBuffer()

    commands.queue_birth(
        site_index=10,
        component_type=PRODUCER,
        genome=0.4,
        energy=0.5,
        lineage_id=99,
    )

    assert int(state.ctype[10]) == EMPTY

    summary = commands.flush(state)

    assert summary.births_committed == 1
    assert summary.deaths_committed == 0
    assert int(state.ctype[10]) == PRODUCER
    assert float(state.genome[10]) == pytest_approx(0.4)
    assert float(state.energy[10]) == pytest_approx(0.5)
    assert int(state.lineage[10]) == 99
    assert commands.births == []
    assert commands.deaths == []


def test_command_buffer_defers_death_until_flush() -> None:
    state = prepared_state()
    commands = CommandBuffer()

    commands.queue_death(0)

    assert int(state.ctype[0]) == PRODUCER

    summary = commands.flush(state)

    assert summary.births_committed == 0
    assert summary.deaths_committed == 1
    assert int(state.ctype[0]) == EMPTY
    assert float(state.energy[0]) == 0.0
    assert int(state.lineage[0]) == -1


def test_command_buffer_rejects_conflicting_commands_atomically() -> None:
    state = prepared_state()
    before = state.digest()
    commands = CommandBuffer()

    commands.queue_death(0)
    commands.queue_birth(
        site_index=0,
        component_type=CONSUMER,
        genome=0.1,
        energy=0.2,
        lineage_id=42,
    )

    try:
        commands.flush(state)
    except ValueError:
        pass
    else:
        raise AssertionError("Birth/death conflict was accepted.")

    assert state.digest() == before


def test_command_validation_rejects_duplicates() -> None:
    commands = CommandBuffer()

    commands.queue_birth(
        site_index=5,
        component_type=PRODUCER,
        genome=0.5,
        energy=1.0,
        lineage_id=1,
    )

    try:
        commands.queue_birth(
            site_index=5,
            component_type=CONSUMER,
            genome=0.5,
            energy=1.0,
            lineage_id=2,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate birth was accepted.")

    commands.queue_death(6)

    try:
        commands.queue_death(6)
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate death was accepted.")


def test_state_validation_catches_nan_inf_and_invalid_types() -> None:
    state = prepared_state()
    state.validate()

    state.energy[0] = float("nan")

    try:
        state.validate()
    except ValueError:
        pass
    else:
        raise AssertionError("NaN energy was accepted.")

    state = prepared_state()
    state.res_a[0] = float("inf")

    try:
        state.validate()
    except ValueError:
        pass
    else:
        raise AssertionError("Infinite resource was accepted.")

    state = prepared_state()
    state.ctype[0] = 77

    try:
        state.validate()
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid component type was accepted.")


def test_population_bound_is_enforced() -> None:
    state = prepared_state()

    try:
        state.validate(
            EcologyBounds(max_population=2)
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Population bound was not enforced.")


def test_metabolism_is_local_finite_and_does_not_mutate_climate() -> None:
    state = prepared_state()
    _, climate = climate_lattice()

    climate_before = (
        climate.current.clone(),
        climate.previous.clone(),
        climate.transition_ids.clone(),
        climate.changed.clone(),
    )

    mu = optimum(climate.current)
    capacity_field = capacity(climate.current)
    shock_field = shock(
        climate.previous,
        climate.current,
        torch.zeros_like(
            climate.current,
            dtype=torch.float32,
        ),
    )

    energy_before = state.energy.clone()

    metabolize(
        state,
        mu,
        capacity_field,
        shock_field,
        cost=0.02,
    )

    assert not torch.equal(state.energy, energy_before)
    assert bool(torch.isfinite(state.energy).all())

    validate_climate_inputs_unchanged(
        climate_before,
        (
            climate.current,
            climate.previous,
            climate.transition_ids,
            climate.changed,
        ),
    )


def test_age_increments_only_for_active_components() -> None:
    state = prepared_state()

    increment_age(state)

    assert state.age[:3].tolist() == [1, 1, 1]
    assert int(state.age[3:].sum()) == 0


def test_birth_command_order_is_deterministic() -> None:
    commands = [
        BirthCommand(
            site_index=20,
            component_type=PRODUCER,
            genome=0.2,
            energy=0.5,
            lineage_id=2,
        ),
        BirthCommand(
            site_index=10,
            component_type=CONSUMER,
            genome=0.7,
            energy=0.9,
            lineage_id=1,
        ),
    ]

    assert [command.site_index for command in sorted(commands)] == [
        10,
        20,
    ]


def pytest_approx(value: float, tolerance: float = 1e-6):
    """Tiny local approximation helper without importing pytest."""
    class Approx:
        def __eq__(self, other):
            return abs(float(other) - value) <= tolerance

    return Approx()
