from __future__ import annotations

import torch

from DarwinianMatrix.ecology.engine import (
    CONSUMER,
    PRODUCER,
    STRUCTURE,
    EcologyState,
)
from DarwinianMatrix.ecology.transaction import (
    EcologyTransactionConfig,
    advance_ecology_transaction,
)
from DarwinianMatrix.geometry import (
    MATRIX_CELLS,
    ClimateSidecar,
    LatticeClimateView,
    build_neighbor_table,
    build_region_map,
    directed_transition_id,
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


def stable_climate() -> LatticeClimateView:
    sidecar = ClimateSidecar()
    sidecar.trm_write(VALID_GRID)

    return sidecar.lattice_read_view(
        build_region_map()
    )


def direct_climate(
    *,
    previous_value: int,
    current_value: int,
) -> LatticeClimateView:
    previous = torch.full(
        (MATRIX_CELLS,),
        previous_value,
        dtype=torch.int8,
    )
    current = torch.full(
        (MATRIX_CELLS,),
        current_value,
        dtype=torch.int8,
    )

    return LatticeClimateView(
        previous=previous,
        current=current,
        transition_ids=directed_transition_id(
            previous.long(),
            current.long(),
        ),
        changed=previous.ne(current),
    )


def one_of_each_state() -> EcologyState:
    state = EcologyState()

    state.ctype[0] = PRODUCER
    state.genome[0] = 0.5
    state.energy[0] = 1.0
    state.lineage[0] = 100

    state.ctype[1] = CONSUMER
    state.genome[1] = 0.5
    state.energy[1] = 1.0
    state.lineage[1] = 101

    state.ctype[2] = STRUCTURE
    state.genome[2] = 0.5
    state.energy[2] = 1.0
    state.lineage[2] = 102

    state.res_a[1] = 1.0
    state.validate()

    return state


def test_transaction_does_not_mutate_inputs() -> None:
    state = one_of_each_state()
    climate = stable_climate()
    ages = torch.zeros(MATRIX_CELLS)
    neighbors = build_neighbor_table()

    state_before = state.digest()
    climate_before = (
        climate.previous.clone(),
        climate.current.clone(),
        climate.transition_ids.clone(),
        climate.changed.clone(),
    )
    ages_before = ages.clone()

    result, telemetry = advance_ecology_transaction(
        state=state,
        climate=climate,
        transition_age=ages,
        neighbors=neighbors,
    )

    assert state.digest() == state_before
    assert result.digest() != state_before
    assert telemetry.before_digest == state_before
    assert telemetry.after_digest == result.digest()

    assert torch.equal(
        climate.previous,
        climate_before[0],
    )
    assert torch.equal(
        climate.current,
        climate_before[1],
    )
    assert torch.equal(
        climate.transition_ids,
        climate_before[2],
    )
    assert torch.equal(
        climate.changed,
        climate_before[3],
    )
    assert torch.equal(ages, ages_before)


def test_transaction_is_deterministic() -> None:
    state = one_of_each_state()
    climate = stable_climate()
    ages = torch.zeros(MATRIX_CELLS)
    neighbors = build_neighbor_table()

    first_state, first_telemetry = (
        advance_ecology_transaction(
            state=state,
            climate=climate,
            transition_age=ages,
            neighbors=neighbors,
        )
    )
    second_state, second_telemetry = (
        advance_ecology_transaction(
            state=state,
            climate=climate,
            transition_age=ages,
            neighbors=neighbors,
        )
    )

    assert first_state.digest() == second_state.digest()
    assert (
        first_telemetry.digest()
        == second_telemetry.digest()
    )


def test_three_component_types_have_distinct_effects() -> None:
    result, _ = advance_ecology_transaction(
        state=one_of_each_state(),
        climate=stable_climate(),
        transition_age=torch.zeros(
            MATRIX_CELLS
        ),
        neighbors=build_neighbor_table(),
    )

    energies = {
        round(float(result.energy[index]), 8)
        for index in (0, 1, 2)
    }

    assert len(energies) == 3
    assert float(result.res_a.sum()) > 0.0


def test_rising_and_falling_shocks_are_directional() -> None:
    state = EcologyState()
    state.ctype[0] = PRODUCER
    state.genome[0] = 0.5
    state.energy[0] = 1.0
    state.lineage[0] = 1
    state.validate()

    neighbors = build_neighbor_table()
    ages = torch.zeros(MATRIX_CELLS)

    rising, _ = advance_ecology_transaction(
        state=state,
        climate=direct_climate(
            previous_value=2,
            current_value=8,
        ),
        transition_age=ages,
        neighbors=neighbors,
    )

    falling, _ = advance_ecology_transaction(
        state=state,
        climate=direct_climate(
            previous_value=8,
            current_value=2,
        ),
        transition_age=ages,
        neighbors=neighbors,
    )

    assert float(rising.energy[0]) > float(
        falling.energy[0]
    )
    assert float(rising.res_a[0]) > float(
        falling.res_a[0]
    )


def test_gradient_reduces_cross_border_resource_flux() -> None:
    state = EcologyState()

    source = matrix_index(4, 8)
    destination = matrix_index(4, 9)
    state.res_a[source] = 8.0

    neighbors = build_neighbor_table()
    ages = torch.zeros(MATRIX_CELLS)

    low_gradient = direct_climate(
        previous_value=5,
        current_value=5,
    )

    previous = torch.full(
        (MATRIX_CELLS,),
        1,
        dtype=torch.int8,
    )
    current = previous.clone()

    current[
        build_region_map().eq(1)
    ] = 9

    high_gradient = LatticeClimateView(
        previous=current.clone(),
        current=current,
        transition_ids=directed_transition_id(
            current.long(),
            current.long(),
        ),
        changed=torch.zeros(
            MATRIX_CELLS,
            dtype=torch.bool,
        ),
    )

    low_result, _ = advance_ecology_transaction(
        state=state,
        climate=low_gradient,
        transition_age=ages,
        neighbors=neighbors,
    )

    high_result, _ = advance_ecology_transaction(
        state=state,
        climate=high_gradient,
        transition_age=ages,
        neighbors=neighbors,
    )

    assert float(
        low_result.res_a[destination]
    ) > float(
        high_result.res_a[destination]
    )


def test_death_is_deferred_then_committed() -> None:
    state = EcologyState()
    state.ctype[10] = PRODUCER
    state.genome[10] = 0.5
    state.energy[10] = -0.24
    state.lineage[10] = 7
    state.validate()

    config = EcologyTransactionConfig(
        producer_cost=0.20,
        death_threshold=-0.25,
    )

    result, telemetry = advance_ecology_transaction(
        state=state,
        climate=stable_climate(),
        transition_age=torch.zeros(
            MATRIX_CELLS
        ),
        neighbors=build_neighbor_table(),
        config=config,
    )

    assert state.population == 1
    assert result.population == 0
    assert telemetry.deaths_committed == 1
    assert int(result.ctype[10]) == -1


def test_negative_transition_age_is_rejected() -> None:
    ages = torch.zeros(MATRIX_CELLS)
    ages[0] = -1.0

    try:
        advance_ecology_transaction(
            state=EcologyState(),
            climate=stable_climate(),
            transition_age=ages,
            neighbors=build_neighbor_table(),
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Negative transition age was accepted."
        )


def test_multi_step_sequence_remains_finite() -> None:
    state = one_of_each_state()
    climate = stable_climate()
    neighbors = build_neighbor_table()

    telemetry_digests = []

    for age in range(12):
        state, telemetry = advance_ecology_transaction(
            state=state,
            climate=climate,
            transition_age=torch.full(
                (MATRIX_CELLS,),
                float(age),
            ),
            neighbors=neighbors,
        )

        state.validate()
        telemetry_digests.append(
            telemetry.digest()
        )

    assert len(telemetry_digests) == 12
    assert all(
        len(value) == 64
        for value in telemetry_digests
    )


def test_invalid_climate_domain_is_rejected() -> None:
    climate = direct_climate(
        previous_value=5,
        current_value=5,
    )
    climate.current[0] = 0

    try:
        advance_ecology_transaction(
            state=EcologyState(),
            climate=climate,
            transition_age=torch.zeros(
                MATRIX_CELLS
            ),
            neighbors=build_neighbor_table(),
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Out-of-domain climate was accepted."
        )
