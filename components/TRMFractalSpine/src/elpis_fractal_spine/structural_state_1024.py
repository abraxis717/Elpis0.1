"""Deterministic 1024-wide structural-state encoding for the K3 topology boundary.

Patch 3 of P3 topology dynamics and existing-corpus binding.

This module encodes only information available from the current
``StructuralState`` and an already-constructed 16-byte Markov header.  It does
not accept ``OracleTransition``, canonical targets, valid-next-state sets,
quiescence labels, violation labels, or learned residuals.  The default mode
leaves the 81-wide transition-feature lane at zero.  An explicit ablation mode
may populate that lane with a deterministic opcode fan-out hint derived only
from the current opcode and ``LEGAL_TRANSITIONS``; it supplies no independent
information beyond the one-hot opcode lane.

No torch, no model loading, no GPU, no network, no graph traversal.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from typing import Final

import numpy as np

from .structural_identity import structural_state_identity
from .structural_semantics import (
    EXPANSION_OPCODE,
    GRID_SIZE,
    LEGAL_TRANSITIONS,
    TERMINAL_OPCODES,
    VOID_OPCODE,
    VOCABULARY_SIZE,
    StructuralState,
)

__all__ = [
    "SCHEMA",
    "LAYOUT",
    "VECTOR_WIDTH",
    "HEADER_SIZE",
    "ONEHOT_SLICE",
    "MASK_SLICE",
    "TRANSITION_FEATURE_SLICE",
    "HEADER_SLICE",
    "GLOBAL_SCALAR_SLICE",
    "RESERVED_SLICE",
    "TransitionFeatureMode",
    "StructuralState1024Error",
    "StructuralState1024V1",
    "encode_structural_state_1024",
    "validate_structural_state_1024",
    "to_numpy_fp32",
    "to_numpy_fp16",
]

SCHEMA: Final[str] = "elpis.structural.state1024.v1"
LAYOUT: Final[str] = "grid81_onehot_mask_transition_header_scalars_reserved.v1"
VECTOR_WIDTH: Final[int] = 1024
HEADER_SIZE: Final[int] = 16

ONEHOT_SLICE: Final[slice] = slice(0, 810)
MASK_SLICE: Final[slice] = slice(810, 891)
TRANSITION_FEATURE_SLICE: Final[slice] = slice(891, 972)
HEADER_SLICE: Final[slice] = slice(972, 988)
GLOBAL_SCALAR_SLICE: Final[slice] = slice(988, 996)
RESERVED_SLICE: Final[slice] = slice(996, 1024)

_DOMAIN_HEADER = b"elpis.structural.state1024.header.v1"
_DOMAIN_VECTOR_FP32 = b"elpis.structural.state1024.vector_fp32.v1"
_DOMAIN_VECTOR_FP16 = b"elpis.structural.state1024.vector_fp16.v1"
_DOMAIN_RECORD = b"elpis.structural.state1024.record.v1"
_HEX_64 = re.compile(r"\A[0-9a-f]{64}\Z")
_U64_MAX = 0xFFFFFFFFFFFFFFFF


class TransitionFeatureMode(str, Enum):
    """Admitted semantics of the 81-wide transition-feature lane."""

    RESERVED_ZERO_V1 = "reserved_zero.v1"
    OPCODE_FANOUT_HINT_V1 = "opcode_fanout_hint.v1"


class StructuralState1024Error(ValueError):
    """Raised when the structural 1024-wide ABI is incomplete or invalid."""


def _lp(payload: bytes) -> bytes:
    if not isinstance(payload, (bytes, bytearray)):
        raise StructuralState1024Error("length-prefix payload must be bytes")
    raw = bytes(payload)
    if len(raw) > _U64_MAX:
        raise StructuralState1024Error("payload exceeds uint64 length")
    return len(raw).to_bytes(8, "big") + raw


def _field(name: str, value: bytes) -> bytes:
    return _lp(name.encode("utf-8")) + _lp(value)


def _identity(value: str, *, name: str) -> bytes:
    if not isinstance(value, str) or _HEX_64.fullmatch(value) is None:
        raise StructuralState1024Error(
            f"{name} must be lowercase 64-character hexadecimal"
        )
    return value.encode("ascii")


def _domain_digest(domain: bytes, payload: bytes) -> str:
    return hashlib.sha256(_lp(domain) + _lp(payload)).hexdigest()


def _record_digest(record: "StructuralState1024V1") -> str:
    preimage = b"".join(
        (
            _lp(_DOMAIN_RECORD),
            _field("schema", record.schema.encode("utf-8")),
            _field("layout", record.layout.encode("utf-8")),
            _field("transition_feature_mode", record.transition_feature_mode.value.encode("utf-8")),
            _field(
                "source_state_identity",
                _identity(record.source_state_identity, name="source_state_identity"),
            ),
            _field("header_digest", _identity(record.header_digest, name="header_digest")),
            _field("vector_digest", _identity(record.vector_digest, name="vector_digest")),
            _field(
                "fp16_vector_digest",
                _identity(record.fp16_vector_digest, name="fp16_vector_digest"),
            ),
        )
    )
    return hashlib.sha256(preimage).hexdigest()


def _bounded_nonnegative(value: int, *, name: str) -> np.float32:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise StructuralState1024Error(f"{name} must be a nonnegative integer")
    return np.float32(value / (value + 1.0))


def _normalize_header(header: bytes | bytearray | memoryview) -> tuple[bytes, np.ndarray]:
    if not isinstance(header, (bytes, bytearray, memoryview)):
        raise StructuralState1024Error("header must be bytes-like")
    raw = bytes(header)
    if len(raw) != HEADER_SIZE:
        raise StructuralState1024Error(
            f"header must be exactly {HEADER_SIZE} bytes, got {len(raw)}"
        )
    values = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / np.float32(255.0)
    return raw, values


def _transition_feature(
    state: StructuralState,
    mode: TransitionFeatureMode,
) -> np.ndarray:
    if mode is TransitionFeatureMode.RESERVED_ZERO_V1:
        return np.zeros(GRID_SIZE, dtype=np.float32)
    if mode is TransitionFeatureMode.OPCODE_FANOUT_HINT_V1:
        denominator = np.float32(VOCABULARY_SIZE - 1)
        return np.asarray(
            [
                np.float32((len(LEGAL_TRANSITIONS[int(token)]) - 1) / denominator)
                for token in state.grid.tokens
            ],
            dtype=np.float32,
        )
    raise StructuralState1024Error(f"unsupported transition feature mode: {mode!r}")


def _global_scalars(state: StructuralState) -> np.ndarray:
    tokens = state.grid.tokens
    void_count = sum(int(token) == int(VOID_OPCODE) for token in tokens)
    expansion_count = sum(int(token) == int(EXPANSION_OPCODE) for token in tokens)
    terminal_count = sum(int(token) in TERMINAL_OPCODES for token in tokens)
    writable_count = sum(state.mask)

    provenance_present = state.provenance is not None
    parent_expansion = (
        state.provenance.parent_expansion_cell
        if state.provenance is not None
        else None
    )
    parent_expansion_scalar = (
        np.float32((parent_expansion + 1) / GRID_SIZE)
        if parent_expansion is not None
        else np.float32(0.0)
    )

    return np.asarray(
        (
            _bounded_nonnegative(state.depth, name="state.depth"),
            np.float32(void_count / GRID_SIZE),
            np.float32(expansion_count / GRID_SIZE),
            np.float32(terminal_count / GRID_SIZE),
            np.float32(writable_count / GRID_SIZE),
            np.float32(1.0 if state.grid.is_refinement_quiescent() else 0.0),
            np.float32(1.0 if provenance_present else 0.0),
            parent_expansion_scalar,
        ),
        dtype=np.float32,
    )


@dataclass(frozen=True, slots=True)
class StructuralState1024V1:
    """Immutable metadata plus a read-only canonical FP32 1024-wide vector."""

    schema: str
    layout: str
    transition_feature_mode: TransitionFeatureMode
    vector: np.ndarray
    source_state_identity: str
    header_digest: str
    vector_digest: str
    fp16_vector_digest: str
    record_digest: str

    def __post_init__(self) -> None:
        validate_structural_state_1024(self)


def encode_structural_state_1024(
    state: StructuralState,
    header: bytes | bytearray | memoryview,
    *,
    transition_feature_mode: TransitionFeatureMode = TransitionFeatureMode.RESERVED_ZERO_V1,
) -> StructuralState1024V1:
    """Encode current structural state and a fixed 16-byte header.

    No oracle transition or target-derived value is admitted.
    """
    if not isinstance(state, StructuralState):
        raise StructuralState1024Error(
            f"state must be StructuralState, got {type(state)!r}"
        )
    if not isinstance(transition_feature_mode, TransitionFeatureMode):
        raise StructuralState1024Error(
            "transition_feature_mode must be TransitionFeatureMode"
        )

    header_raw, header_values = _normalize_header(header)
    vector = np.zeros(VECTOR_WIDTH, dtype=np.float32)

    onehot = vector[ONEHOT_SLICE].reshape(GRID_SIZE, VOCABULARY_SIZE)
    for cell, token in enumerate(state.grid.tokens):
        onehot[cell, int(token)] = np.float32(1.0)

    vector[MASK_SLICE] = np.asarray(state.mask, dtype=np.float32)
    vector[TRANSITION_FEATURE_SLICE] = _transition_feature(
        state, transition_feature_mode
    )
    vector[HEADER_SLICE] = header_values
    vector[GLOBAL_SCALAR_SLICE] = _global_scalars(state)
    # RESERVED_SLICE remains exactly zero by construction.

    vector = np.ascontiguousarray(vector, dtype=np.float32)
    fp32_bytes = vector.astype("<f4", copy=False).tobytes(order="C")
    fp16_bytes = vector.astype("<f2").tobytes(order="C")

    source_identity = structural_state_identity(state)
    header_digest = _domain_digest(_DOMAIN_HEADER, header_raw)
    vector_digest = _domain_digest(_DOMAIN_VECTOR_FP32, fp32_bytes)
    fp16_vector_digest = _domain_digest(_DOMAIN_VECTOR_FP16, fp16_bytes)

    vector.setflags(write=False)
    provisional = object.__new__(StructuralState1024V1)
    object.__setattr__(provisional, "schema", SCHEMA)
    object.__setattr__(provisional, "layout", LAYOUT)
    object.__setattr__(provisional, "transition_feature_mode", transition_feature_mode)
    object.__setattr__(provisional, "vector", vector)
    object.__setattr__(provisional, "source_state_identity", source_identity)
    object.__setattr__(provisional, "header_digest", header_digest)
    object.__setattr__(provisional, "vector_digest", vector_digest)
    object.__setattr__(provisional, "fp16_vector_digest", fp16_vector_digest)
    object.__setattr__(provisional, "record_digest", "0" * 64)
    record_digest = _record_digest(provisional)

    return StructuralState1024V1(
        schema=SCHEMA,
        layout=LAYOUT,
        transition_feature_mode=transition_feature_mode,
        vector=vector,
        source_state_identity=source_identity,
        header_digest=header_digest,
        vector_digest=vector_digest,
        fp16_vector_digest=fp16_vector_digest,
        record_digest=record_digest,
    )


def _recover_header_bytes(vector: np.ndarray) -> bytes:
    scaled = vector[HEADER_SLICE].astype(np.float64) * 255.0
    rounded = np.rint(scaled)
    if not np.allclose(scaled, rounded, rtol=0.0, atol=1e-5):
        raise StructuralState1024Error(
            "header lane contains values that are not exact byte/255 encodings"
        )
    if np.any(rounded < 0) or np.any(rounded > 255):
        raise StructuralState1024Error("header lane decodes outside byte range")
    return bytes(int(value) for value in rounded)


def validate_structural_state_1024(record: StructuralState1024V1) -> None:
    if not isinstance(record, StructuralState1024V1):
        raise StructuralState1024Error(
            f"expected StructuralState1024V1, got {type(record)!r}"
        )
    if record.schema != SCHEMA:
        raise StructuralState1024Error(f"schema {record.schema!r} != {SCHEMA!r}")
    if record.layout != LAYOUT:
        raise StructuralState1024Error(f"layout {record.layout!r} != {LAYOUT!r}")
    if not isinstance(record.transition_feature_mode, TransitionFeatureMode):
        raise StructuralState1024Error("invalid transition_feature_mode")

    for name, value in (
        ("source_state_identity", record.source_state_identity),
        ("header_digest", record.header_digest),
        ("vector_digest", record.vector_digest),
        ("fp16_vector_digest", record.fp16_vector_digest),
        ("record_digest", record.record_digest),
    ):
        _identity(value, name=name)

    vector = record.vector
    if not isinstance(vector, np.ndarray):
        raise StructuralState1024Error("vector must be numpy.ndarray")
    if vector.shape != (VECTOR_WIDTH,):
        raise StructuralState1024Error(
            f"vector shape {vector.shape} != ({VECTOR_WIDTH},)"
        )
    if vector.dtype != np.dtype(np.float32):
        raise StructuralState1024Error(f"vector dtype {vector.dtype} != float32")
    if not vector.flags.c_contiguous:
        raise StructuralState1024Error("vector must be C-contiguous")
    if vector.flags.writeable:
        raise StructuralState1024Error("vector must be read-only")
    if not np.isfinite(vector).all():
        raise StructuralState1024Error("vector contains NaN or infinity")

    onehot = vector[ONEHOT_SLICE].reshape(GRID_SIZE, VOCABULARY_SIZE)
    if not np.isin(onehot, np.asarray((0.0, 1.0), dtype=np.float32)).all():
        raise StructuralState1024Error("one-hot lane contains values outside {0,1}")
    if not np.array_equal(onehot.sum(axis=1), np.ones(GRID_SIZE, dtype=np.float32)):
        raise StructuralState1024Error("each one-hot row must contain exactly one 1")

    mask = vector[MASK_SLICE]
    if not np.isin(mask, np.asarray((0.0, 1.0), dtype=np.float32)).all():
        raise StructuralState1024Error("mask lane contains values outside {0,1}")

    token_indices = np.argmax(onehot, axis=1)
    feature = vector[TRANSITION_FEATURE_SLICE]
    if record.transition_feature_mode is TransitionFeatureMode.RESERVED_ZERO_V1:
        if not np.array_equal(feature, np.zeros(GRID_SIZE, dtype=np.float32)):
            raise StructuralState1024Error("reserved-zero transition lane is nonzero")
    elif record.transition_feature_mode is TransitionFeatureMode.OPCODE_FANOUT_HINT_V1:
        expected = np.asarray(
            [
                np.float32((len(LEGAL_TRANSITIONS[int(token)]) - 1) / (VOCABULARY_SIZE - 1))
                for token in token_indices
            ],
            dtype=np.float32,
        )
        if not np.array_equal(feature, expected):
            raise StructuralState1024Error("opcode fan-out hint lane mismatch")
    else:  # pragma: no cover - enum exhaustiveness guard
        raise StructuralState1024Error("unsupported transition feature mode")

    header_raw = _recover_header_bytes(vector)
    if record.header_digest != _domain_digest(_DOMAIN_HEADER, header_raw):
        raise StructuralState1024Error("header digest mismatch")

    globals_ = vector[GLOBAL_SCALAR_SLICE]
    if np.any(globals_ < 0.0) or np.any(globals_ > 1.0):
        raise StructuralState1024Error("global scalar outside [0,1]")
    if not np.isclose(
        float(globals_[1] + globals_[2] + globals_[3]),
        1.0,
        rtol=0.0,
        atol=2e-6,
    ):
        raise StructuralState1024Error("VOID+EXPANSION+terminal fractions must sum to 1")
    expected_fractions = np.asarray(
        (
            np.count_nonzero(token_indices == int(VOID_OPCODE)) / GRID_SIZE,
            np.count_nonzero(token_indices == int(EXPANSION_OPCODE)) / GRID_SIZE,
            np.count_nonzero(np.isin(token_indices, [int(x) for x in TERMINAL_OPCODES])) / GRID_SIZE,
            np.count_nonzero(mask) / GRID_SIZE,
            1.0 if np.count_nonzero(token_indices == int(EXPANSION_OPCODE)) == 0 else 0.0,
        ),
        dtype=np.float32,
    )
    if not np.allclose(globals_[1:6], expected_fractions, rtol=0.0, atol=1e-7):
        raise StructuralState1024Error("state-derived global scalar mismatch")
    if globals_[0] < 0.0 or globals_[0] >= 1.0:
        raise StructuralState1024Error("normalized depth must be in [0,1)")
    if globals_[6] not in (np.float32(0.0), np.float32(1.0)):
        raise StructuralState1024Error("provenance-present scalar must be binary")
    if globals_[7] < 0.0 or globals_[7] > 1.0:
        raise StructuralState1024Error("parent-expansion scalar outside [0,1]")
    if globals_[6] == 0.0 and globals_[7] != 0.0:
        raise StructuralState1024Error(
            "parent-expansion scalar must be zero when provenance is absent"
        )

    if not np.array_equal(
        vector[RESERVED_SLICE], np.zeros(RESERVED_SLICE.stop - RESERVED_SLICE.start, dtype=np.float32)
    ):
        raise StructuralState1024Error("reserved lane must be exactly zero")

    fp32_bytes = vector.astype("<f4", copy=False).tobytes(order="C")
    fp16_bytes = vector.astype("<f2").tobytes(order="C")
    if record.vector_digest != _domain_digest(_DOMAIN_VECTOR_FP32, fp32_bytes):
        raise StructuralState1024Error("FP32 vector digest mismatch")
    if record.fp16_vector_digest != _domain_digest(_DOMAIN_VECTOR_FP16, fp16_bytes):
        raise StructuralState1024Error("FP16 vector digest mismatch")
    if record.record_digest != _record_digest(record):
        raise StructuralState1024Error("record digest mismatch")


def to_numpy_fp32(record: StructuralState1024V1, *, copy: bool = True) -> np.ndarray:
    validate_structural_state_1024(record)
    if copy:
        return np.array(record.vector, dtype=np.float32, order="C", copy=True)
    return record.vector


def to_numpy_fp16(record: StructuralState1024V1) -> np.ndarray:
    validate_structural_state_1024(record)
    return np.asarray(record.vector, dtype=np.float16).copy(order="C")
