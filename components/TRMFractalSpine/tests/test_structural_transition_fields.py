"""CPU-only tests for StructuralTransitionFieldsV1 (P3 Patch 1)."""
from __future__ import annotations

import inspect
import json
import os
import re
import subprocess
import sys
from dataclasses import fields as dataclass_fields
from dataclasses import replace
from pathlib import Path

import pytest

from elpis_fractal_spine.structural_identity import (
    oracle_next_state_identity,
    oracle_transition_identity,
    structural_state_identity,
)
from elpis_fractal_spine.structural_oracle import (
    OracleTransition,
    StructuralOracle,
)
from elpis_fractal_spine.structural_semantics import (
    GRID_SIZE,
    ParentProvenance,
    StructuralGrid,
    StructuralState,
)
from elpis_fractal_spine.structural_transition_fields import (
    SCHEMA,
    StructuralTransitionFieldsError,
    StructuralTransitionFieldsV1,
    compute_transition_fields,
    encode_transition_fields,
    validate_transition_fields,
)

HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")


def _grid(**overrides: int) -> StructuralGrid:
    tokens = [0] * GRID_SIZE
    for key, value in overrides.items():
        tokens[int(key.lstrip("c"))] = value
    return StructuralGrid(tokens=tuple(tokens))


@pytest.fixture(scope="module")
def oracle() -> StructuralOracle:
    return StructuralOracle()


@pytest.fixture(scope="module")
def terminal_state() -> StructuralState:
    return StructuralState.root(StructuralGrid(tokens=(1,) * GRID_SIZE))


@pytest.fixture(scope="module")
def terminal_transition(oracle, terminal_state):
    return oracle.evaluate(terminal_state)


@pytest.fixture(scope="module")
def one_cell_state() -> StructuralState:
    mask = [0] * GRID_SIZE
    mask[0] = 1
    return StructuralState.root(_grid(), mask=tuple(mask))


@pytest.fixture(scope="module")
def one_cell_transition(oracle, one_cell_state):
    return oracle.evaluate(one_cell_state)


@pytest.fixture(scope="module")
def one_cell_fields(one_cell_state, one_cell_transition):
    return compute_transition_fields(one_cell_state, one_cell_transition)


def test_quiescent_transition(terminal_state, terminal_transition):
    record = compute_transition_fields(terminal_state, terminal_transition)
    assert record.valid_next_state_count == 1
    assert record.canonical_delta81 == (0,) * GRID_SIZE
    assert record.branch_modify_count81 == (0,) * GRID_SIZE
    assert record.branch_distinct_value_count81 == (1,) * GRID_SIZE
    validate_transition_fields(record)


def test_single_candidate_transition(terminal_state, terminal_transition):
    assert len(terminal_transition.valid_next_states) == 1
    record = compute_transition_fields(terminal_state, terminal_transition)
    assert record.canonical_target_identity == oracle_next_state_identity(
        terminal_transition.canonical_next_state
    )
    assert record.oracle_transition_identity == oracle_transition_identity(
        terminal_transition
    )


def test_multiple_candidate_transition(one_cell_state, one_cell_transition):
    record = compute_transition_fields(one_cell_state, one_cell_transition)
    assert len(one_cell_transition.valid_next_states) == 9
    assert record.valid_next_state_count == 9
    assert len({oracle_next_state_identity(item) for item in one_cell_transition.valid_next_states}) == 9


def test_canonical_delta_exact(one_cell_state, one_cell_transition, one_cell_fields):
    expected = tuple(
        int(
            one_cell_transition.canonical_next_state.grid.tokens[index]
            != one_cell_state.grid.tokens[index]
        )
        for index in range(GRID_SIZE)
    )
    assert one_cell_fields.canonical_delta81 == expected
    assert sum(expected) == 1
    assert expected[0] == 1


def test_modify_count_exact(one_cell_fields):
    assert one_cell_fields.branch_modify_count81[0] == 9
    assert one_cell_fields.branch_modify_count81[1:] == (0,) * (GRID_SIZE - 1)


def test_distinct_value_count_exact(one_cell_fields):
    assert one_cell_fields.branch_distinct_value_count81[0] == 9
    assert one_cell_fields.branch_distinct_value_count81[1:] == (1,) * (
        GRID_SIZE - 1
    )


def test_candidate_order_invariance(one_cell_state, one_cell_transition):
    reversed_transition = replace(
        one_cell_transition,
        valid_next_states=tuple(reversed(one_cell_transition.valid_next_states)),
    )
    rotated = one_cell_transition.valid_next_states[3:] + one_cell_transition.valid_next_states[:3]
    rotated_transition = replace(one_cell_transition, valid_next_states=rotated)

    original = compute_transition_fields(one_cell_state, one_cell_transition)
    reversed_record = compute_transition_fields(one_cell_state, reversed_transition)
    rotated_record = compute_transition_fields(one_cell_state, rotated_transition)

    assert reversed_record == original
    assert rotated_record == original
    assert encode_transition_fields(reversed_record) == encode_transition_fields(original)


def test_full_state_identity_binding(oracle, one_cell_state):
    mask = list(one_cell_state.mask)
    mask[1] = 1
    changed = replace(one_cell_state, mask=tuple(mask))
    left = compute_transition_fields(one_cell_state, oracle.evaluate(one_cell_state))
    right = compute_transition_fields(changed, oracle.evaluate(changed))
    assert left.source_state_identity == structural_state_identity(one_cell_state)
    assert right.source_state_identity == structural_state_identity(changed)
    assert left.source_state_identity != right.source_state_identity


def test_same_grid_different_mask_changes_source_identity(oracle, one_cell_state):
    changed = replace(one_cell_state, mask=(0,) * GRID_SIZE)
    assert changed.grid == one_cell_state.grid
    left = compute_transition_fields(one_cell_state, oracle.evaluate(one_cell_state))
    right = compute_transition_fields(changed, oracle.evaluate(changed))
    assert left.source_state_identity != right.source_state_identity


def test_depth_change_changes_source_identity(oracle, one_cell_state):
    changed = replace(one_cell_state, depth=2)
    left = compute_transition_fields(one_cell_state, oracle.evaluate(one_cell_state))
    right = compute_transition_fields(changed, oracle.evaluate(changed))
    assert left.source_state_identity != right.source_state_identity


def test_provenance_change_changes_source_identity(oracle, one_cell_state):
    provenance = ParentProvenance(
        parent_grid_digest="a" * 64,
        parent_expansion_cell=0,
        fold_rule_id="fold.replace_cell.v1",
        depth=1,
    )
    changed = replace(one_cell_state, depth=1, provenance=provenance)
    left = compute_transition_fields(one_cell_state, oracle.evaluate(one_cell_state))
    right = compute_transition_fields(changed, oracle.evaluate(changed))
    assert left.source_state_identity != right.source_state_identity


def test_canonical_target_must_be_candidate(one_cell_state, one_cell_transition):
    invalid = replace(
        one_cell_transition,
        valid_next_states=one_cell_transition.valid_next_states[1:],
        canonical_next_state=one_cell_transition.valid_next_states[0],
    )
    with pytest.raises(
        StructuralTransitionFieldsError,
        match="canonical_next_state is not a member",
    ):
        compute_transition_fields(one_cell_state, invalid)


def test_identities_and_digest_are_lowercase_sha256(one_cell_fields):
    assert one_cell_fields.schema == SCHEMA
    for value in (
        one_cell_fields.source_state_identity,
        one_cell_fields.oracle_transition_identity,
        one_cell_fields.canonical_target_identity,
        one_cell_fields.fields_digest,
    ):
        assert HEX64.fullmatch(value)


def test_encoding_is_deterministic(one_cell_fields):
    first = encode_transition_fields(one_cell_fields)
    second = encode_transition_fields(replace(one_cell_fields))
    assert first == second
    assert first.startswith(len(SCHEMA).to_bytes(8, "big") + SCHEMA.encode())


def test_tampered_digest_rejected(one_cell_fields):
    with pytest.raises(StructuralTransitionFieldsError, match="fields_digest mismatch"):
        replace(one_cell_fields, fields_digest="0" * 64)


def test_invalid_schema_rejected(one_cell_fields):
    with pytest.raises(StructuralTransitionFieldsError, match="schema"):
        replace(one_cell_fields, schema="elpis.structural.transition_fields.v0")


@pytest.mark.parametrize(
    "field_name",
    [
        "source_state_identity",
        "oracle_transition_identity",
        "canonical_target_identity",
        "fields_digest",
    ],
)
def test_invalid_identity_rejected(one_cell_fields, field_name):
    with pytest.raises(StructuralTransitionFieldsError, match=field_name):
        replace(one_cell_fields, **{field_name: "NOT-A-DIGEST"})


@pytest.mark.parametrize(
    "field_name",
    [
        "canonical_delta81",
        "branch_modify_count81",
        "branch_distinct_value_count81",
    ],
)
def test_invalid_vector_length_rejected(one_cell_fields, field_name):
    value = getattr(one_cell_fields, field_name)
    with pytest.raises(StructuralTransitionFieldsError, match="length"):
        replace(one_cell_fields, **{field_name: value[:-1]})


def test_invalid_delta_rejected(one_cell_fields):
    value = list(one_cell_fields.canonical_delta81)
    value[0] = 2
    with pytest.raises(StructuralTransitionFieldsError, match="not in"):
        replace(one_cell_fields, canonical_delta81=tuple(value))


def test_invalid_modify_count_rejected(one_cell_fields):
    value = list(one_cell_fields.branch_modify_count81)
    value[0] = one_cell_fields.valid_next_state_count + 1
    with pytest.raises(StructuralTransitionFieldsError, match="outside"):
        replace(one_cell_fields, branch_modify_count81=tuple(value))


def test_invalid_distinct_count_rejected(one_cell_fields):
    value = list(one_cell_fields.branch_distinct_value_count81)
    value[0] = 10
    with pytest.raises(StructuralTransitionFieldsError, match="outside"):
        replace(one_cell_fields, branch_distinct_value_count81=tuple(value))


def test_bool_is_not_accepted_as_integer(one_cell_fields):
    value = list(one_cell_fields.branch_modify_count81)
    value[0] = True
    with pytest.raises(StructuralTransitionFieldsError, match="must be an integer"):
        replace(one_cell_fields, branch_modify_count81=tuple(value))


def test_zero_candidate_record_is_well_defined(one_cell_state, one_cell_transition):
    empty = replace(one_cell_transition, valid_next_states=())
    record = compute_transition_fields(one_cell_state, empty)
    assert record.valid_next_state_count == 0
    assert record.branch_modify_count81 == (0,) * GRID_SIZE
    assert record.branch_distinct_value_count81 == (0,) * GRID_SIZE
    validate_transition_fields(record)


def test_record_has_no_learned_or_probability_fields():
    field_names = {field.name for field in dataclass_fields(StructuralTransitionFieldsV1)}
    forbidden = {"residual", "uncertainty", "confidence", "probability"}
    assert not any(
        token in field_name
        for field_name in field_names
        for token in forbidden
    )


def test_computation_preserves_oracle_canonical_target(one_cell_state, one_cell_transition):
    before = one_cell_transition.canonical_next_state
    record = compute_transition_fields(one_cell_state, one_cell_transition)
    assert one_cell_transition.canonical_next_state is before
    assert record.canonical_target_identity == oracle_next_state_identity(before)


def test_wrong_input_types_fail_closed(one_cell_state, one_cell_transition):
    with pytest.raises(StructuralTransitionFieldsError, match="state must"):
        compute_transition_fields(object(), one_cell_transition)  # type: ignore[arg-type]
    with pytest.raises(StructuralTransitionFieldsError, match="transition must"):
        compute_transition_fields(one_cell_state, object())  # type: ignore[arg-type]


def test_fresh_process_digest_replay():
    code = r'''
from elpis_fractal_spine.structural_oracle import StructuralOracle
from elpis_fractal_spine.structural_semantics import GRID_SIZE, StructuralGrid, StructuralState
from elpis_fractal_spine.structural_transition_fields import compute_transition_fields
mask = [0] * GRID_SIZE
mask[0] = 1
state = StructuralState.root(StructuralGrid(tokens=(0,) * GRID_SIZE), mask=tuple(mask))
transition = StructuralOracle().evaluate(state)
record = compute_transition_fields(state, transition)
print(record.source_state_identity)
print(record.oracle_transition_identity)
print(record.canonical_target_identity)
print(record.fields_digest)
'''
    outputs = []
    for seed in ("0", "977", "1954"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        assert result.stderr == ""
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1] == outputs[2]


def test_source_does_not_import_model_or_gpu_code():
    import elpis_fractal_spine.structural_transition_fields as module

    source = inspect.getsource(module)
    assert "import torch" not in source
    assert "import triton" not in source
    assert "cuda" not in source.lower()
    assert "network" not in source.lower()
