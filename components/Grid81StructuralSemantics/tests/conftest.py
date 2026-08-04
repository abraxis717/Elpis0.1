from __future__ import annotations

from copy import deepcopy

import pytest

from elpis_grid81_semantics import (
    ActionKindV1,
    D4PairPayloadV1,
    Grid81ActionV1,
)


@pytest.fixture
def asymmetric_grid() -> tuple[int, ...]:
    return tuple((index * 7 + index // 9) % 10 for index in range(81))


@pytest.fixture
def writable_mask() -> tuple[int, ...]:
    return tuple(1 if index in {0, 1, 2, 9, 10, 18, 40, 72, 80} else 0 for index in range(81))


@pytest.fixture
def noop_action() -> Grid81ActionV1:
    return Grid81ActionV1(ActionKindV1.NOOP, None, None)


@pytest.fixture
def edit_action() -> Grid81ActionV1:
    return Grid81ActionV1(ActionKindV1.EDIT, 40, 6)


@pytest.fixture
def valid_pair_payload(
    asymmetric_grid: tuple[int, ...],
    writable_mask: tuple[int, ...],
    edit_action: Grid81ActionV1,
) -> D4PairPayloadV1:
    return D4PairPayloadV1(
        grid81=asymmetric_grid,
        writable_mask81=writable_mask,
        action=edit_action,
        schema_id="elpis.d4_pair_payload.v1",
        schema_version="1.0",
    )


@pytest.fixture
def valid_pair_dict(valid_pair_payload: D4PairPayloadV1) -> dict:
    return valid_pair_payload.to_dict()


@pytest.fixture
def valid_corpus_row(asymmetric_grid: tuple[int, ...]) -> dict:
    row = {
        "case_id": "case-r1-1",
        "input_grid": list(asymmetric_grid),
        "input_mask": [0] * 81,
        "canonical_target_grid": list(asymmetric_grid),
        "expansion_targets": [{"cell": 40}],
        "rationale_codes": ["ACTIVE_EXPANSION"],
        "quiescence_target": False,
    }
    row["input_mask"][40] = 1
    row["canonical_target_grid"][40] = 6
    return row


@pytest.fixture
def deep_copy():
    return deepcopy
