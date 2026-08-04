from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from elpis_fractal_spine.structural_identity import structural_state_identity
from elpis_fractal_spine.structural_semantics import (
    ParentProvenance,
    StructuralGrid,
    StructuralState,
)
from elpis_fractal_spine.structural_state_1024 import (
    GLOBAL_SCALAR_SLICE,
    HEADER_SLICE,
    LAYOUT,
    MASK_SLICE,
    ONEHOT_SLICE,
    RESERVED_SLICE,
    SCHEMA,
    TRANSITION_FEATURE_SLICE,
    VECTOR_WIDTH,
    StructuralState1024Error,
    StructuralState1024V1,
    TransitionFeatureMode,
    encode_structural_state_1024,
    to_numpy_fp16,
    to_numpy_fp32,
    validate_structural_state_1024,
)


def _state(
    *,
    tokens: tuple[int, ...] | None = None,
    mask: tuple[int, ...] | None = None,
    depth: int = 2,
    provenance: ParentProvenance | None = None,
) -> StructuralState:
    if tokens is None:
        tokens = tuple([0, 6, 1, 2, 3, 4, 5, 7, 8, 9] * 8 + [0])
    if mask is None:
        mask = tuple(1 if i % 3 == 0 else 0 for i in range(81))
    return StructuralState(
        grid=StructuralGrid(tokens=tokens),
        mask=mask,
        depth=depth,
        provenance=provenance,
    )


def _header() -> bytes:
    return bytes(range(16))


def _record(**kwargs) -> StructuralState1024V1:
    return encode_structural_state_1024(_state(**kwargs), _header())


def _unsafe_replace(record: StructuralState1024V1, **changes) -> StructuralState1024V1:
    # dataclasses.replace invokes validation; construct an intentionally invalid
    # frozen record for negative validation tests.
    result = object.__new__(StructuralState1024V1)
    for name in record.__dataclass_fields__:
        object.__setattr__(result, name, changes.get(name, getattr(record, name)))
    return result


def test_layout_is_exactly_1024() -> None:
    assert VECTOR_WIDTH == 1024
    assert ONEHOT_SLICE == slice(0, 810)
    assert MASK_SLICE == slice(810, 891)
    assert TRANSITION_FEATURE_SLICE == slice(891, 972)
    assert HEADER_SLICE == slice(972, 988)
    assert GLOBAL_SCALAR_SLICE == slice(988, 996)
    assert RESERVED_SLICE == slice(996, 1024)


def test_default_record_validates() -> None:
    record = _record()
    assert record.schema == SCHEMA
    assert record.layout == LAYOUT
    assert record.transition_feature_mode is TransitionFeatureMode.RESERVED_ZERO_V1
    validate_structural_state_1024(record)


def test_vector_is_float32_c_contiguous_read_only() -> None:
    vector = _record().vector
    assert vector.shape == (1024,)
    assert vector.dtype == np.float32
    assert vector.flags.c_contiguous
    assert not vector.flags.writeable
    with pytest.raises(ValueError):
        vector[0] = 0.0


def test_onehot_lane_exact() -> None:
    state = _state()
    record = encode_structural_state_1024(state, _header())
    onehot = record.vector[ONEHOT_SLICE].reshape(81, 10)
    assert np.array_equal(onehot.sum(axis=1), np.ones(81, dtype=np.float32))
    for cell, token in enumerate(state.grid.tokens):
        assert onehot[cell, token] == 1.0
        assert np.count_nonzero(onehot[cell]) == 1


def test_mask_lane_exact() -> None:
    state = _state()
    record = encode_structural_state_1024(state, _header())
    assert np.array_equal(
        record.vector[MASK_SLICE], np.asarray(state.mask, dtype=np.float32)
    )


def test_default_transition_lane_is_zero() -> None:
    record = _record()
    assert np.array_equal(
        record.vector[TRANSITION_FEATURE_SLICE], np.zeros(81, dtype=np.float32)
    )


def test_opcode_fanout_hint_exact() -> None:
    tokens = tuple([0, 1, 6] * 27)
    state = _state(tokens=tokens)
    record = encode_structural_state_1024(
        state,
        _header(),
        transition_feature_mode=TransitionFeatureMode.OPCODE_FANOUT_HINT_V1,
    )
    expected = np.asarray([1.0, 1.0 / 9.0, 8.0 / 9.0] * 27, dtype=np.float32)
    assert np.array_equal(record.vector[TRANSITION_FEATURE_SLICE], expected)


def test_feature_mode_is_explicit_ablation_and_changes_identity() -> None:
    state = _state()
    zero = encode_structural_state_1024(state, _header())
    hint = encode_structural_state_1024(
        state,
        _header(),
        transition_feature_mode=TransitionFeatureMode.OPCODE_FANOUT_HINT_V1,
    )
    assert zero.vector_digest != hint.vector_digest
    assert zero.record_digest != hint.record_digest
    assert zero.source_state_identity == hint.source_state_identity


def test_header_lane_is_raw_bytes_divided_by_255() -> None:
    raw = _header()
    record = _record()
    expected = np.asarray(list(raw), dtype=np.float32) / np.float32(255.0)
    assert np.array_equal(record.vector[HEADER_SLICE], expected)



def test_header_byte_extremes_round_trip_exactly() -> None:
    raw = bytes([0, 1, 2, 63, 64, 127, 128, 191, 192, 253, 254, 255, 17, 85, 170, 240])
    record = encode_structural_state_1024(_state(), raw)
    recovered = bytes(
        int(value)
        for value in np.rint(record.vector[HEADER_SLICE].astype(np.float64) * 255.0)
    )
    assert recovered == raw
    validate_structural_state_1024(record)


def test_wrong_vector_shape_rejected() -> None:
    record = _record()
    vector = record.vector[:-1].copy()
    vector.setflags(write=False)
    invalid = _unsafe_replace(record, vector=vector)
    with pytest.raises(StructuralState1024Error, match="shape"):
        validate_structural_state_1024(invalid)


def test_invalid_onehot_row_rejected() -> None:
    record = _record()
    vector = record.vector.copy()
    vector[0:10] = 0.0
    vector.setflags(write=False)
    invalid = _unsafe_replace(record, vector=vector)
    with pytest.raises(StructuralState1024Error, match="exactly one"):
        validate_structural_state_1024(invalid)

def test_header_change_changes_vector_and_record() -> None:
    state = _state()
    first = encode_structural_state_1024(state, bytes(range(16)))
    second = encode_structural_state_1024(state, bytes(reversed(range(16))))
    assert first.header_digest != second.header_digest
    assert first.vector_digest != second.vector_digest
    assert first.record_digest != second.record_digest


def test_global_scalars_are_current_state_only() -> None:
    provenance = ParentProvenance(
        parent_grid_digest="a" * 64,
        parent_expansion_cell=40,
        fold_rule_id="fold.test.v1",
        depth=1,
    )
    tokens = tuple([0] * 27 + [6] * 27 + [1] * 27)
    mask = tuple([1] * 9 + [0] * 72)
    state = _state(tokens=tokens, mask=mask, depth=3, provenance=provenance)
    scalars = encode_structural_state_1024(state, _header()).vector[GLOBAL_SCALAR_SLICE]
    expected = np.asarray(
        [
            3.0 / 4.0,
            27.0 / 81.0,
            27.0 / 81.0,
            27.0 / 81.0,
            9.0 / 81.0,
            0.0,
            1.0,
            41.0 / 81.0,
        ],
        dtype=np.float32,
    )
    assert np.array_equal(scalars, expected)


def test_quiescent_scalar_uses_current_grid_only() -> None:
    tokens = tuple([1] * 81)
    record = _record(tokens=tokens)
    assert record.vector[GLOBAL_SCALAR_SLICE][5] == 1.0


def test_reserved_lane_is_exact_zero() -> None:
    assert np.array_equal(
        _record().vector[RESERVED_SLICE], np.zeros(28, dtype=np.float32)
    )


def test_source_state_identity_is_patch0_identity() -> None:
    state = _state()
    record = encode_structural_state_1024(state, _header())
    assert record.source_state_identity == structural_state_identity(state)


def test_same_grid_different_mask_changes_vector_and_identity() -> None:
    state_a = _state(mask=tuple([0] * 81))
    state_b = _state(mask=tuple([1] + [0] * 80))
    a = encode_structural_state_1024(state_a, _header())
    b = encode_structural_state_1024(state_b, _header())
    assert a.source_state_identity != b.source_state_identity
    assert a.vector_digest != b.vector_digest


def test_depth_change_changes_scalar_vector_and_identity() -> None:
    a = _record(depth=0)
    b = _record(depth=4)
    assert a.source_state_identity != b.source_state_identity
    assert a.vector[GLOBAL_SCALAR_SLICE][0] == 0.0
    assert b.vector[GLOBAL_SCALAR_SLICE][0] == np.float32(4.0 / 5.0)
    assert a.vector_digest != b.vector_digest


def test_provenance_detail_may_share_vector_but_never_record_identity() -> None:
    common = dict(parent_expansion_cell=4, depth=1)
    p1 = ParentProvenance(
        parent_grid_digest="1" * 64,
        fold_rule_id="fold.a",
        **common,
    )
    p2 = ParentProvenance(
        parent_grid_digest="2" * 64,
        fold_rule_id="fold.b",
        **common,
    )
    a = _record(provenance=p1)
    b = _record(provenance=p2)
    assert np.array_equal(a.vector, b.vector)
    assert a.source_state_identity != b.source_state_identity
    assert a.record_digest != b.record_digest


def test_no_oracle_transition_argument_exists() -> None:
    import inspect
    from elpis_fractal_spine import structural_state_1024 as module

    signature = inspect.signature(module.encode_structural_state_1024)
    assert "transition" not in signature.parameters
    assert "oracle" not in signature.parameters


def test_wrong_header_length_rejected() -> None:
    with pytest.raises(StructuralState1024Error, match="exactly 16 bytes"):
        encode_structural_state_1024(_state(), b"\x00" * 15)


def test_non_bytes_header_rejected() -> None:
    with pytest.raises(StructuralState1024Error, match="bytes-like"):
        encode_structural_state_1024(_state(), "not bytes")  # type: ignore[arg-type]


def test_wrong_state_type_rejected() -> None:
    with pytest.raises(StructuralState1024Error, match="StructuralState"):
        encode_structural_state_1024(object(), _header())  # type: ignore[arg-type]


def test_wrong_feature_mode_type_rejected() -> None:
    with pytest.raises(StructuralState1024Error, match="TransitionFeatureMode"):
        encode_structural_state_1024(
            _state(), _header(), transition_feature_mode="bad"  # type: ignore[arg-type]
        )


def test_digest_fields_are_lowercase_sha256() -> None:
    record = _record()
    for value in (
        record.source_state_identity,
        record.header_digest,
        record.vector_digest,
        record.fp16_vector_digest,
        record.record_digest,
    ):
        assert len(value) == 64
        assert value == value.lower()
        int(value, 16)


def test_vector_mutation_is_detected() -> None:
    record = _record()
    vector = record.vector.copy()
    vector[0] = 0.0
    vector.setflags(write=False)
    invalid = _unsafe_replace(record, vector=vector)
    with pytest.raises(StructuralState1024Error):
        validate_structural_state_1024(invalid)


def test_nonzero_reserved_lane_is_rejected() -> None:
    record = _record()
    vector = record.vector.copy()
    vector[RESERVED_SLICE.start] = 1.0
    vector.setflags(write=False)
    invalid = _unsafe_replace(record, vector=vector)
    with pytest.raises(StructuralState1024Error, match="reserved"):
        validate_structural_state_1024(invalid)


def test_writeable_vector_is_rejected() -> None:
    record = _record()
    invalid = _unsafe_replace(record, vector=record.vector.copy())
    with pytest.raises(StructuralState1024Error, match="read-only"):
        validate_structural_state_1024(invalid)


def test_wrong_vector_dtype_rejected() -> None:
    record = _record()
    vector = record.vector.astype(np.float64)
    vector.setflags(write=False)
    invalid = _unsafe_replace(record, vector=vector)
    with pytest.raises(StructuralState1024Error, match="dtype"):
        validate_structural_state_1024(invalid)


def test_nan_rejected() -> None:
    record = _record()
    vector = record.vector.copy()
    vector[1000] = np.nan
    vector.setflags(write=False)
    invalid = _unsafe_replace(record, vector=vector)
    with pytest.raises(StructuralState1024Error, match="NaN"):
        validate_structural_state_1024(invalid)


def test_header_digest_mismatch_rejected() -> None:
    record = _record()
    invalid = _unsafe_replace(record, header_digest="0" * 64)
    with pytest.raises(StructuralState1024Error, match="header digest"):
        validate_structural_state_1024(invalid)


def test_vector_digest_mismatch_rejected() -> None:
    record = _record()
    invalid = _unsafe_replace(record, vector_digest="0" * 64)
    with pytest.raises(StructuralState1024Error, match="FP32 vector digest"):
        validate_structural_state_1024(invalid)


def test_record_digest_mismatch_rejected() -> None:
    record = _record()
    invalid = _unsafe_replace(record, record_digest="0" * 64)
    with pytest.raises(StructuralState1024Error, match="record digest"):
        validate_structural_state_1024(invalid)


def test_fp32_materialization_copy_and_view() -> None:
    record = _record()
    copy = to_numpy_fp32(record)
    view = to_numpy_fp32(record, copy=False)
    assert np.array_equal(copy, record.vector)
    assert copy.flags.writeable
    assert view is record.vector
    assert not view.flags.writeable


def test_fp16_materialization_matches_digest() -> None:
    record = _record()
    fp16 = to_numpy_fp16(record)
    assert fp16.shape == (1024,)
    assert fp16.dtype == np.float16
    payload = fp16.astype("<f2", copy=False).tobytes(order="C")
    expected = hashlib.sha256(
        len(b"elpis.structural.state1024.vector_fp16.v1").to_bytes(8, "big")
        + b"elpis.structural.state1024.vector_fp16.v1"
        + len(payload).to_bytes(8, "big")
        + payload
    ).hexdigest()
    assert expected == record.fp16_vector_digest


def test_fresh_process_replay() -> None:
    source_root = str(Path(__file__).resolve().parents[1] / "src")
    program = r'''
from elpis_fractal_spine.structural_semantics import ParentProvenance, StructuralGrid, StructuralState
from elpis_fractal_spine.structural_state_1024 import encode_structural_state_1024
p = ParentProvenance(parent_grid_digest="a"*64, parent_expansion_cell=7, fold_rule_id="fold.v1", depth=1)
s = StructuralState(grid=StructuralGrid(tokens=tuple([0,6,1]*27)), mask=tuple([1,0,0]*27), depth=3, provenance=p)
r = encode_structural_state_1024(s, bytes(range(16)))
print(r.source_state_identity)
print(r.header_digest)
print(r.vector_digest)
print(r.fp16_vector_digest)
print(r.record_digest)
'''
    outputs = []
    for seed in ("0", "977", "1954"):
        env = os.environ.copy()
        env["PYTHONPATH"] = source_root
        env["PYTHONHASHSEED"] = seed
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [sys.executable, "-c", program],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1] == outputs[2]


def test_module_has_no_torch_model_network_or_oracle_api() -> None:
    import ast

    source = Path(
        __import__(
            "elpis_fractal_spine.structural_state_1024",
            fromlist=["dummy"],
        ).__file__
    ).read_text()
    tree = ast.parse(source)

    imported_modules: set[str] = set()
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module.split(".")[0])
            imported_names.update(alias.name for alias in node.names)

    assert imported_modules.isdisjoint(
        {"torch", "requests", "urllib", "socket", "subprocess"}
    )
    assert imported_names.isdisjoint({"StructuralOracle", "OracleTransition"})
