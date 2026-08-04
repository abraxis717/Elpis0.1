"""Deterministic structural transition evidence derived from Canon oracle output.

This module is Patch 1 of P3 topology dynamics and corpus binding.  It creates
an immutable, content-addressed record describing how a complete
``StructuralState`` relates to one complete ``OracleTransition``.

The record is evidence only.  It is not a model residual, probability,
confidence score, or learned uncertainty estimate.  It does not modify the
oracle, select a canonical candidate, change ``TRMRefinementProposal``, or
migrate any existing ``residual81`` consumer.

Identity dependencies are the qualified Patch 0 primitives in
``structural_identity.py``.  Consequently the source identity binds the full
state (grid, writable mask, depth, and provenance), while the transition and
canonical-target identities bind every semantic field of their respective
Canon objects.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Iterable, Sequence

from .structural_identity import (
    oracle_next_state_identity,
    oracle_transition_identity,
    structural_state_identity,
)
from .structural_oracle import OracleTransition
from .structural_semantics import GRID_SIZE, StructuralState, VOCABULARY_SIZE

__all__ = [
    "SCHEMA",
    "StructuralTransitionFieldsError",
    "StructuralTransitionFieldsV1",
    "compute_transition_fields",
    "encode_transition_fields",
    "validate_transition_fields",
]

SCHEMA = "elpis.structural.transition_fields.v1"
_DOMAIN = SCHEMA.encode("utf-8")
_HEX_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")
_U64_MAX = 0xFFFFFFFFFFFFFFFF


class StructuralTransitionFieldsError(ValueError):
    """Raised when a transition-evidence record is incomplete or invalid."""


def _lp(payload: bytes) -> bytes:
    """Encode bytes as uint64-be length followed by the payload."""
    if not isinstance(payload, (bytes, bytearray)):
        raise StructuralTransitionFieldsError(
            f"length-prefix payload must be bytes, got {type(payload)!r}"
        )
    raw = bytes(payload)
    if len(raw) > _U64_MAX:
        raise StructuralTransitionFieldsError("payload exceeds uint64 length")
    return len(raw).to_bytes(8, "big") + raw


def _field(name: str, value: bytes) -> bytes:
    return _lp(name.encode("utf-8")) + _lp(value)


def _u64(value: int, *, name: str) -> bytes:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StructuralTransitionFieldsError(
            f"{name} must be an integer, got {type(value)!r}"
        )
    if value < 0 or value > _U64_MAX:
        raise StructuralTransitionFieldsError(
            f"{name}={value} outside unsigned 64-bit range"
        )
    return value.to_bytes(8, "big")


def _u8(value: int, *, name: str) -> bytes:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StructuralTransitionFieldsError(
            f"{name} must be an integer, got {type(value)!r}"
        )
    if value < 0 or value > 0xFF:
        raise StructuralTransitionFieldsError(
            f"{name}={value} outside unsigned 8-bit range"
        )
    return bytes((value,))


def _identity_bytes(value: str, *, name: str) -> bytes:
    if not isinstance(value, str) or _HEX_SHA256.fullmatch(value) is None:
        raise StructuralTransitionFieldsError(
            f"{name} must be a lowercase 64-character SHA-256 hex string"
        )
    return value.encode("ascii")


def _tuple_of_ints(value: object, *, name: str) -> tuple[int, ...]:
    if not isinstance(value, tuple):
        raise StructuralTransitionFieldsError(
            f"{name} must be a tuple, got {type(value)!r}"
        )
    if len(value) != GRID_SIZE:
        raise StructuralTransitionFieldsError(
            f"{name} length {len(value)} != {GRID_SIZE}"
        )
    for index, item in enumerate(value):
        if not isinstance(item, int) or isinstance(item, bool):
            raise StructuralTransitionFieldsError(
                f"{name}[{index}] must be an integer, got {type(item)!r}"
            )
    return value


def _sequence_u8(values: Sequence[int], *, name: str) -> bytes:
    return b"".join(_u8(item, name=f"{name}[{index}]") for index, item in enumerate(values))


def _sequence_u64(values: Sequence[int], *, name: str) -> bytes:
    return b"".join(
        _u64(item, name=f"{name}[{index}]") for index, item in enumerate(values)
    )


@dataclass(frozen=True, slots=True)
class StructuralTransitionFieldsV1:
    """Complete deterministic evidence for one structural oracle transition.

    Vector semantics, for cell ``i``:

    ``canonical_delta81[i]``
        1 exactly when the oracle-supplied canonical next grid differs from the
        source grid at cell ``i``; otherwise 0.

    ``branch_modify_count81[i]``
        Number of states in ``valid_next_states`` whose grid differs from the
        source grid at cell ``i``.

    ``branch_distinct_value_count81[i]``
        Number of distinct token values represented at cell ``i`` across
        ``valid_next_states``.

    No field carries probabilistic semantics.  ``valid_next_state_count`` is
    the exact denominator for the two branch-count vectors.
    """

    schema: str
    source_state_identity: str
    oracle_transition_identity: str
    canonical_target_identity: str
    canonical_delta81: tuple[int, ...]
    branch_modify_count81: tuple[int, ...]
    branch_distinct_value_count81: tuple[int, ...]
    valid_next_state_count: int
    fields_digest: str

    def __post_init__(self) -> None:
        validate_transition_fields(self)


def _encode_values(
    *,
    source_state_identity_value: str,
    oracle_transition_identity_value: str,
    canonical_target_identity_value: str,
    canonical_delta81: Sequence[int],
    branch_modify_count81: Sequence[int],
    branch_distinct_value_count81: Sequence[int],
    valid_next_state_count: int,
) -> bytes:
    """Canonical digest preimage for every record field except its digest."""
    return b"".join(
        (
            _lp(_DOMAIN),
            _field(
                "source_state_identity",
                _identity_bytes(
                    source_state_identity_value, name="source_state_identity"
                ),
            ),
            _field(
                "oracle_transition_identity",
                _identity_bytes(
                    oracle_transition_identity_value,
                    name="oracle_transition_identity",
                ),
            ),
            _field(
                "canonical_target_identity",
                _identity_bytes(
                    canonical_target_identity_value,
                    name="canonical_target_identity",
                ),
            ),
            _field(
                "canonical_delta81",
                _sequence_u8(canonical_delta81, name="canonical_delta81"),
            ),
            _field(
                "branch_modify_count81",
                _sequence_u64(
                    branch_modify_count81, name="branch_modify_count81"
                ),
            ),
            _field(
                "branch_distinct_value_count81",
                _sequence_u8(
                    branch_distinct_value_count81,
                    name="branch_distinct_value_count81",
                ),
            ),
            _field(
                "valid_next_state_count",
                _u64(valid_next_state_count, name="valid_next_state_count"),
            ),
        )
    )


def _encode_without_digest(fields: StructuralTransitionFieldsV1) -> bytes:
    return _encode_values(
        source_state_identity_value=fields.source_state_identity,
        oracle_transition_identity_value=fields.oracle_transition_identity,
        canonical_target_identity_value=fields.canonical_target_identity,
        canonical_delta81=fields.canonical_delta81,
        branch_modify_count81=fields.branch_modify_count81,
        branch_distinct_value_count81=fields.branch_distinct_value_count81,
        valid_next_state_count=fields.valid_next_state_count,
    )


def encode_transition_fields(fields: StructuralTransitionFieldsV1) -> bytes:
    """Return the canonical record encoding, including the verified digest."""
    validate_transition_fields(fields)
    return _encode_without_digest(fields) + _field(
        "fields_digest", _identity_bytes(fields.fields_digest, name="fields_digest")
    )


def _expected_digest(fields: StructuralTransitionFieldsV1) -> str:
    return hashlib.sha256(_encode_without_digest(fields)).hexdigest()


def validate_transition_fields(fields: StructuralTransitionFieldsV1) -> None:
    """Fail closed unless ``fields`` is a complete valid V1 record."""
    if not isinstance(fields, StructuralTransitionFieldsV1):
        raise StructuralTransitionFieldsError(
            f"expected StructuralTransitionFieldsV1, got {type(fields)!r}"
        )
    if fields.schema != SCHEMA:
        raise StructuralTransitionFieldsError(
            f"schema {fields.schema!r} != {SCHEMA!r}"
        )

    _identity_bytes(fields.source_state_identity, name="source_state_identity")
    _identity_bytes(
        fields.oracle_transition_identity, name="oracle_transition_identity"
    )
    _identity_bytes(fields.canonical_target_identity, name="canonical_target_identity")
    _identity_bytes(fields.fields_digest, name="fields_digest")

    delta = _tuple_of_ints(fields.canonical_delta81, name="canonical_delta81")
    modify = _tuple_of_ints(
        fields.branch_modify_count81, name="branch_modify_count81"
    )
    distinct = _tuple_of_ints(
        fields.branch_distinct_value_count81,
        name="branch_distinct_value_count81",
    )

    count = fields.valid_next_state_count
    if not isinstance(count, int) or isinstance(count, bool):
        raise StructuralTransitionFieldsError(
            "valid_next_state_count must be an integer"
        )
    if count < 0 or count > _U64_MAX:
        raise StructuralTransitionFieldsError(
            f"valid_next_state_count={count} outside unsigned 64-bit range"
        )

    for index, value in enumerate(delta):
        if value not in (0, 1):
            raise StructuralTransitionFieldsError(
                f"canonical_delta81[{index}]={value} not in {{0, 1}}"
            )

    distinct_upper = min(VOCABULARY_SIZE, count)
    for index, value in enumerate(modify):
        if value < 0 or value > count:
            raise StructuralTransitionFieldsError(
                f"branch_modify_count81[{index}]={value} outside [0, {count}]"
            )
        if count > 0 and delta[index] == 1 and value == 0:
            raise StructuralTransitionFieldsError(
                f"canonical_delta81[{index}]=1 but no valid candidate modifies the cell"
            )

    for index, value in enumerate(distinct):
        if count == 0:
            if value != 0:
                raise StructuralTransitionFieldsError(
                    "branch_distinct_value_count81 must be all zero when "
                    "valid_next_state_count is zero"
                )
        elif value < 1 or value > distinct_upper:
            raise StructuralTransitionFieldsError(
                f"branch_distinct_value_count81[{index}]={value} outside "
                f"[1, {distinct_upper}]"
            )

    if count == 0 and any(modify):
        raise StructuralTransitionFieldsError(
            "branch_modify_count81 must be all zero when valid_next_state_count is zero"
        )

    expected = _expected_digest(fields)
    if fields.fields_digest != expected:
        raise StructuralTransitionFieldsError(
            f"fields_digest mismatch: expected {expected}, got {fields.fields_digest}"
        )


def _build_record(
    *,
    source_state_identity_value: str,
    oracle_transition_identity_value: str,
    canonical_target_identity_value: str,
    canonical_delta81: tuple[int, ...],
    branch_modify_count81: tuple[int, ...],
    branch_distinct_value_count81: tuple[int, ...],
    valid_next_state_count: int,
) -> StructuralTransitionFieldsV1:
    """Construct a record only after computing its canonical digest."""
    digest = hashlib.sha256(
        _encode_values(
            source_state_identity_value=source_state_identity_value,
            oracle_transition_identity_value=oracle_transition_identity_value,
            canonical_target_identity_value=canonical_target_identity_value,
            canonical_delta81=canonical_delta81,
            branch_modify_count81=branch_modify_count81,
            branch_distinct_value_count81=branch_distinct_value_count81,
            valid_next_state_count=valid_next_state_count,
        )
    ).hexdigest()

    return StructuralTransitionFieldsV1(
        schema=SCHEMA,
        source_state_identity=source_state_identity_value,
        oracle_transition_identity=oracle_transition_identity_value,
        canonical_target_identity=canonical_target_identity_value,
        canonical_delta81=canonical_delta81,
        branch_modify_count81=branch_modify_count81,
        branch_distinct_value_count81=branch_distinct_value_count81,
        valid_next_state_count=valid_next_state_count,
        fields_digest=digest,
    )


def compute_transition_fields(
    state: StructuralState,
    transition: OracleTransition,
) -> StructuralTransitionFieldsV1:
    """Compute deterministic evidence without changing the supplied transition.

    The canonical target is bound exactly as emitted by the oracle.  When the
    transition has one or more valid candidates, that target must be a member
    by complete Patch 0 identity; otherwise computation fails closed.
    Candidate ordering is irrelevant because both the Patch 0 transition
    identity and all branch aggregations are order-independent.
    """
    if not isinstance(state, StructuralState):
        raise StructuralTransitionFieldsError(
            f"state must be StructuralState, got {type(state)!r}"
        )
    if not isinstance(transition, OracleTransition):
        raise StructuralTransitionFieldsError(
            f"transition must be OracleTransition, got {type(transition)!r}"
        )

    source_tokens = state.grid.tokens
    canonical_tokens = transition.canonical_next_state.grid.tokens
    if len(source_tokens) != GRID_SIZE or len(canonical_tokens) != GRID_SIZE:
        raise StructuralTransitionFieldsError("source or canonical grid has invalid width")

    valid_next_states = transition.valid_next_states
    count = len(valid_next_states)
    canonical_identity = oracle_next_state_identity(
        transition.canonical_next_state
    )
    if count > 0:
        candidate_identities = {
            oracle_next_state_identity(candidate) for candidate in valid_next_states
        }
        if canonical_identity not in candidate_identities:
            raise StructuralTransitionFieldsError(
                "canonical_next_state is not a member of valid_next_states"
            )

    canonical_delta = tuple(
        int(canonical_tokens[index] != source_tokens[index])
        for index in range(GRID_SIZE)
    )

    modify_counts: list[int] = []
    distinct_counts: list[int] = []
    for index in range(GRID_SIZE):
        values = [candidate.grid.tokens[index] for candidate in valid_next_states]
        modify_counts.append(
            sum(value != source_tokens[index] for value in values)
        )
        distinct_counts.append(len(set(values)))

    return _build_record(
        source_state_identity_value=structural_state_identity(state),
        oracle_transition_identity_value=oracle_transition_identity(transition),
        canonical_target_identity_value=canonical_identity,
        canonical_delta81=canonical_delta,
        branch_modify_count81=tuple(modify_counts),
        branch_distinct_value_count81=tuple(distinct_counts),
        valid_next_state_count=count,
    )
