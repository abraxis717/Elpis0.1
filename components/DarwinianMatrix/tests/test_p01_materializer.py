from __future__ import annotations

import json

import pytest
import torch

from DarwinianMatrix.trm.contract import (
    StructuralRefinementRequest,
)
from DarwinianMatrix.trm.p01_materializer import (
    DEFAULT_P01_MATERIALIZATION_POLICY,
    P01MaterializationMode,
    materialize_p01_input,
    validate_p01_givens,
)


SOLVED = (
    5, 3, 4, 6, 7, 8, 9, 1, 2,
    6, 7, 2, 1, 9, 5, 3, 4, 8,
    1, 9, 8, 3, 4, 2, 5, 6, 7,
    8, 5, 9, 7, 6, 1, 4, 2, 3,
    4, 2, 6, 8, 5, 3, 7, 9, 1,
    7, 1, 3, 9, 2, 4, 8, 5, 6,
    9, 6, 1, 5, 3, 7, 2, 8, 4,
    2, 8, 7, 4, 1, 9, 6, 3, 5,
    3, 4, 5, 2, 8, 6, 1, 7, 9,
)


def request(
    *,
    clamps: dict[int, int],
) -> StructuralRefinementRequest:
    values = [0] * 81
    mask = [False] * 81

    for index, value in clamps.items():
        values[index] = value
        mask[index] = True

    return StructuralRefinementRequest(
        episode_id="p01-materializer-test",
        frame_index=0,
        previous_grid=SOLVED,
        clamp_values=values,
        clamp_mask=mask,
    )


def test_no_clamps_preserves_previous_solution():
    result = materialize_p01_input(
        request(clamps={})
    )

    assert result.mode is (
        P01MaterializationMode
        .PRESERVE_PREVIOUS_SOLVED
    )
    assert result.active_clamp_count == 0
    assert result.changed_clamp_count == 0
    assert result.grid_values == SOLVED


def test_matching_clamps_preserve_previous_solution():
    result = materialize_p01_input(
        request(
            clamps={
                0: 5,
                10: 7,
                80: 9,
            }
        )
    )

    assert result.mode is (
        P01MaterializationMode
        .PRESERVE_PREVIOUS_SOLVED
    )
    assert result.active_clamp_count == 3
    assert result.changed_clamp_count == 0
    assert result.grid_values == SOLVED


def test_changed_clamp_blanks_every_nonclamped_cell():
    result = materialize_p01_input(
        request(
            clamps={
                0: 6,
            }
        )
    )

    assert result.mode is (
        P01MaterializationMode
        .ACTIVE_CLAMPS_AS_GIVENS
    )
    assert result.active_clamp_count == 1
    assert result.changed_clamp_count == 1
    assert result.grid_values[0] == 6
    assert sum(
        value != 0
        for value in result.grid_values
    ) == 1


def test_changed_request_keeps_all_active_clamps_as_givens():
    result = materialize_p01_input(
        request(
            clamps={
                0: 6,
                10: 7,
                80: 9,
            }
        )
    )

    assert result.active_clamp_count == 3
    assert result.changed_clamp_count == 1
    assert result.grid_values[0] == 6
    assert result.grid_values[10] == 7
    assert result.grid_values[80] == 9
    assert sum(
        value != 0
        for value in result.grid_values
    ) == 3


def test_materialized_tensor_is_training_native():
    result = materialize_p01_input(
        request(
            clamps={
                0: 6,
            }
        )
    )

    tensor = result.tensor()

    assert tensor.shape == (1, 81)
    assert tensor.dtype == torch.int64
    assert tensor.device.type == "cpu"
    assert tensor.requires_grad is False


def test_returned_tensor_cannot_mutate_canonical_values():
    result = materialize_p01_input(
        request(
            clamps={
                0: 6,
            }
        )
    )

    tensor = result.tensor()
    tensor[0, 0] = 1

    assert result.grid_values[0] == 6
    assert result.tensor()[0, 0].item() == 6


def test_materialization_digest_is_repeatable():
    first = materialize_p01_input(
        request(
            clamps={
                0: 6,
            }
        )
    )

    second = materialize_p01_input(
        request(
            clamps={
                0: 6,
            }
        )
    )

    assert first.digest() == second.digest()
    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )


def test_materialization_digest_changes_with_request():
    first = materialize_p01_input(
        request(
            clamps={
                0: 6,
            }
        )
    )

    second = materialize_p01_input(
        request(
            clamps={
                0: 7,
            }
        )
    )

    assert first.digest() != second.digest()


def test_policy_explicitly_excludes_ecological_inputs():
    payload = (
        DEFAULT_P01_MATERIALIZATION_POLICY
        .canonical_payload()
    )

    encoded = json.dumps(
        payload,
        sort_keys=True,
    ).lower()

    for forbidden in (
        "cascade",
        "ecology",
        "telemetry",
        "viability",
        "verdict",
    ):
        assert forbidden in encoded

    assert (
        payload["forbidden_inputs"]
        == [
            "cascade",
            "ecology",
            "telemetry",
            "viability",
            "verdict",
        ]
    )


def test_partial_sudoku_accepts_zero_blanks():
    values = [0] * 81
    values[0] = 5
    values[10] = 7
    values[80] = 9

    assert validate_p01_givens(values) == tuple(
        values
    )


@pytest.mark.parametrize(
    "indices",
    (
        (0, 1),
        (0, 9),
        (0, 10),
    ),
)
def test_partial_sudoku_rejects_duplicate_givens(
    indices,
):
    values = [0] * 81

    for index in indices:
        values[index] = 5

    with pytest.raises(
        ValueError,
        match="duplicate",
    ):
        validate_p01_givens(values)


@pytest.mark.parametrize(
    "invalid_value",
    (-1, 10),
)
def test_partial_sudoku_rejects_out_of_vocab_values(
    invalid_value,
):
    values = [0] * 81
    values[0] = invalid_value

    with pytest.raises(
        ValueError,
        match=r"\[0, 9\]",
    ):
        validate_p01_givens(values)
