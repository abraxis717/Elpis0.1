"""Complete canonical identity primitives for structural states and oracle output.

WHY THIS MODULE EXISTS
  ``StructuralState`` (structural_semantics.py:266-323) has no identity method.
  The only digest available in that module is ``StructuralGrid.digest()``
  (structural_semantics.py:207-212), which binds grid tokens ONLY: two states
  differing in ``mask``, ``depth``, or ``provenance`` share it.

  ``OracleTransition`` (structural_oracle.py:89-104) has no identity method at
  all.  ``OracleNextState.digest()`` (structural_oracle.py:78-86) exists but is
  incomplete: it omits ``fold_expectations`` and ``rationale_codes`` entirely,
  omits ``ChildSpecification.seed_rule_id``, and builds its preimage by
  delimiter concatenation, which is not injective.

  This module supplies complete, unambiguous identities.  It does NOT modify,
  replace, or remediate the existing digests; existing consumers are untouched.

ENCODING LAW
  Every record is a concatenation of length-prefixed byte strings:

      LP(x) = uint64_be(len(x)) || x

  and every record begins with ``LP(domain)``.  Every field contributes
  ``LP(field_name_utf8) || LP(canonical_field_value)`` in declared semantic
  field order.  Because every element carries an explicit 8-byte length, the
  concatenation is injective: no rearrangement of field boundaries can produce
  the same byte string, so nested-boundary ambiguity is impossible by
  construction rather than by convention.

SCALAR ENCODINGS
  unsigned int   fixed-width big-endian; widths documented per field below
  signed int     fixed-width two's-complement big-endian (none required today)
  bool           exactly one byte, 0x00 or 0x01
  str            UTF-8, then length-prefixed
  opcode token   uint16_be (domain is 0..9, structural_semantics.py:30-42)
  cell index     uint16_be (domain is 0..80, GRID_SIZE = 81)
  depth          uint64_be (non-negative by construction)
  optional       one presence byte 0x00/0x01, then the value when present

FORBIDDEN, AND ABSENT FROM THIS MODULE
  delimiter concatenation, repr, Python hash, pickle, unconstrained JSON,
  StructuralGrid.digest() as a state identity, OracleNextState.digest() as a
  complete next-state identity, empty strings / null placeholders / magic
  hashes for absent values.

ORDERING
  See ORDERING NOTES in the module body.  Every tuple is classified either
  POSITIONAL (order preserved) or SET-LIKE (canonicalized by sorting on the
  complete encoded bytes of each element, preserving multiplicity).

No network, no GPU, no model loading, no torch.  Pure stdlib plus the Canon
structural dataclasses.
"""
from __future__ import annotations

import hashlib
from typing import Iterable, Sequence

from .structural_oracle import (
    ChildSpecification,
    ExpansionTarget,
    FoldExpectation,
    OracleNextState,
    OracleTransition,
)
from .structural_semantics import (
    GRID_SIZE,
    ParentProvenance,
    StructuralGrid,
    StructuralState,
)

__all__ = [
    "DOMAIN_STRUCTURAL_STATE",
    "DOMAIN_ORACLE_NEXT_STATE",
    "DOMAIN_ORACLE_TRANSITION",
    "StructuralIdentityError",
    "structural_state_identity",
    "oracle_next_state_identity",
    "oracle_transition_identity",
    "encode_structural_state",
    "encode_oracle_next_state",
    "encode_oracle_transition",
]

# ---------------------------------------------------------------------------
# Domain separators (exact, frozen)
# ---------------------------------------------------------------------------

DOMAIN_STRUCTURAL_STATE = b"elpis.structural.state_identity.v1"
DOMAIN_ORACLE_NEXT_STATE = b"elpis.structural.oracle_next_state_identity.v1"
DOMAIN_ORACLE_TRANSITION = b"elpis.structural.oracle_transition_identity.v1"

# Nested-element domains. Nested values are encoded through their own complete
# domain-separated record, so an ExpansionTarget can never be confused with a
# ChildSpecification even if their scalar fields coincide.
DOMAIN_PARENT_PROVENANCE = b"elpis.structural.parent_provenance_identity.v1"
DOMAIN_EXPANSION_TARGET = b"elpis.structural.expansion_target_identity.v1"
DOMAIN_CHILD_SPECIFICATION = b"elpis.structural.child_specification_identity.v1"
DOMAIN_FOLD_EXPECTATION = b"elpis.structural.fold_expectation_identity.v1"
DOMAIN_STRUCTURAL_GRID = b"elpis.structural.grid_identity.v1"

_PRESENT = b"\x01"
_ABSENT = b"\x00"
_TRUE = b"\x01"
_FALSE = b"\x00"

_U16_MAX = 0xFFFF
_U64_MAX = 0xFFFFFFFFFFFFFFFF


class StructuralIdentityError(ValueError):
    """Raised when a value cannot be canonically encoded."""


# ---------------------------------------------------------------------------
# Primitive encoders
# ---------------------------------------------------------------------------


def _lp(payload: bytes) -> bytes:
    """LP(x) = uint64_be(len(x)) || x."""
    if not isinstance(payload, (bytes, bytearray)):
        raise StructuralIdentityError(f"LP requires bytes, got {type(payload)!r}")
    payload = bytes(payload)
    if len(payload) > _U64_MAX:
        raise StructuralIdentityError("payload exceeds uint64 length")
    return len(payload).to_bytes(8, "big") + payload


def _u16(value: int, *, name: str) -> bytes:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StructuralIdentityError(f"{name}: expected int, got {type(value)!r}")
    if value < 0 or value > _U16_MAX:
        raise StructuralIdentityError(f"{name}: {value} outside uint16 domain")
    return value.to_bytes(2, "big")


def _u64(value: int, *, name: str) -> bytes:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StructuralIdentityError(f"{name}: expected int, got {type(value)!r}")
    if value < 0 or value > _U64_MAX:
        raise StructuralIdentityError(f"{name}: {value} outside uint64 domain")
    return value.to_bytes(8, "big")


def _boolean(value: bool, *, name: str) -> bytes:
    if not isinstance(value, bool):
        raise StructuralIdentityError(f"{name}: expected bool, got {type(value)!r}")
    return _TRUE if value else _FALSE


def _text(value: str, *, name: str) -> bytes:
    if not isinstance(value, str):
        raise StructuralIdentityError(f"{name}: expected str, got {type(value)!r}")
    return value.encode("utf-8")


def _field(name: str, value: bytes) -> bytes:
    """LP(field_name) || LP(canonical_field_value)."""
    return _lp(name.encode("utf-8")) + _lp(value)


def _record(domain: bytes, fields: Sequence[bytes]) -> bytes:
    """LP(domain) || LP(field_0) || ... || LP(field_n) in declared order."""
    out = [_lp(domain)]
    out.extend(_lp(f) for f in fields)
    return b"".join(out)


def _sequence_positional(items: Iterable[bytes]) -> bytes:
    """Order-preserving sequence: elements kept in the order supplied."""
    return b"".join(_lp(item) for item in items)


def _sequence_set_like(items: Iterable[bytes]) -> bytes:
    """Order-insensitive sequence.

    Elements are sorted by their COMPLETE encoded bytes, so the result is
    invariant under any permutation of the input.  Multiplicity is preserved:
    duplicates are not collapsed, because collapsing them would lose
    information the source may carry.
    """
    return b"".join(_lp(item) for item in sorted(items))


def _digest(preimage: bytes) -> str:
    return hashlib.sha256(preimage).hexdigest()


# ---------------------------------------------------------------------------
# ORDERING NOTES
# ---------------------------------------------------------------------------
#
# POSITIONAL (order is semantic; preserved):
#   StructuralGrid.tokens   cell index i is the meaning of position i
#                           (structural_semantics.py:157, GRID_SIZE = 81)
#   StructuralState.mask    same positional cell indexing
#                           (structural_semantics.py:274)
#
# SET-LIKE (order is not semantic; canonicalized by sorted encoded bytes):
#   expansion_targets       each element carries its own `cell`
#                           (structural_oracle.py:43); the oracle appends them
#                           in generation order (structural_oracle.py:257), so
#                           position carries no information the element does
#                           not already carry.
#   child_specifications    each element carries `parent_cell`
#                           (structural_oracle.py:51).
#   fold_expectations       each element carries `parent_cell`
#                           (structural_oracle.py:60).
#   violation_codes         the oracle already emits these sorted and
#                           de-duplicated (structural_oracle.py:365
#                           `tuple(sorted(set(violations)))`); sorting here is
#                           idempotent for oracle-produced values and makes the
#                           identity robust for directly constructed ones.
#   rationale_codes         the oracle already emits these sorted
#                           (structural_oracle.py:387 `tuple(sorted(rationale))`).
#   valid_next_states       the oracle emits these sorted by the LEGACY
#                           incomplete digest (structural_oracle.py:187-192,
#                           :209).  That ordering is derived, not semantic, and
#                           is not injective over the full field set, so this
#                           module canonicalizes by complete encoded bytes.
#                           Candidate order therefore cannot affect the
#                           identity.
#
# canonical_next_state is bound SEPARATELY and by position (it is a single
# distinguished element, structural_oracle.py:98).  This module never selects
# or re-selects a canonical candidate; it binds the one the oracle produced.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Nested element encoders
# ---------------------------------------------------------------------------


def _encode_grid(grid: StructuralGrid) -> bytes:
    """StructuralGrid: tokens only (structural_semantics.py:154-212).

    Encoded through its own domain so a bare token sequence can never collide
    with a grid record.
    """
    if not isinstance(grid, StructuralGrid):
        raise StructuralIdentityError(f"expected StructuralGrid, got {type(grid)!r}")
    tokens = grid.tokens
    if len(tokens) != GRID_SIZE:
        raise StructuralIdentityError(
            f"grid tokens length {len(tokens)} != {GRID_SIZE}"
        )
    token_bytes = b"".join(
        _u16(int(t), name=f"grid.tokens[{i}]") for i, t in enumerate(tokens)
    )
    return _record(
        DOMAIN_STRUCTURAL_GRID,
        [_field("tokens", token_bytes)],
    )


def _encode_parent_provenance(provenance: ParentProvenance) -> bytes:
    """ParentProvenance (structural_semantics.py:133-151).

    Declared field order: parent_grid_digest, parent_expansion_cell,
    fold_rule_id, depth.
    """
    if not isinstance(provenance, ParentProvenance):
        raise StructuralIdentityError(
            f"expected ParentProvenance, got {type(provenance)!r}"
        )
    cell = provenance.parent_expansion_cell
    if cell is None:
        cell_bytes = _ABSENT
    else:
        cell_bytes = _PRESENT + _u16(
            int(cell), name="provenance.parent_expansion_cell"
        )
    return _record(
        DOMAIN_PARENT_PROVENANCE,
        [
            _field(
                "parent_grid_digest",
                _text(provenance.parent_grid_digest, name="parent_grid_digest"),
            ),
            _field("parent_expansion_cell", cell_bytes),
            _field("fold_rule_id", _text(provenance.fold_rule_id, name="fold_rule_id")),
            _field("depth", _u64(int(provenance.depth), name="provenance.depth")),
        ],
    )


def _encode_expansion_target(target: ExpansionTarget) -> bytes:
    """ExpansionTarget (structural_oracle.py:39-44): cell, rationale_code."""
    if not isinstance(target, ExpansionTarget):
        raise StructuralIdentityError(
            f"expected ExpansionTarget, got {type(target)!r}"
        )
    return _record(
        DOMAIN_EXPANSION_TARGET,
        [
            _field("cell", _u16(int(target.cell), name="expansion_target.cell")),
            _field(
                "rationale_code",
                _text(target.rationale_code, name="expansion_target.rationale_code"),
            ),
        ],
    )


def _encode_child_specification(spec: ChildSpecification) -> bytes:
    """ChildSpecification (structural_oracle.py:47-53).

    Binds seed_rule_id, which OracleNextState.digest() (structural_oracle.py:84)
    omits.
    """
    if not isinstance(spec, ChildSpecification):
        raise StructuralIdentityError(
            f"expected ChildSpecification, got {type(spec)!r}"
        )
    return _record(
        DOMAIN_CHILD_SPECIFICATION,
        [
            _field(
                "parent_cell",
                _u16(int(spec.parent_cell), name="child_specification.parent_cell"),
            ),
            _field(
                "seed_grid_digest",
                _text(spec.seed_grid_digest, name="child_specification.seed_grid_digest"),
            ),
            _field(
                "seed_rule_id",
                _text(spec.seed_rule_id, name="child_specification.seed_rule_id"),
            ),
        ],
    )


def _encode_fold_expectation(expectation: FoldExpectation) -> bytes:
    """FoldExpectation (structural_oracle.py:56-63).

    Entirely absent from OracleNextState.digest() (structural_oracle.py:78-86).
    """
    if not isinstance(expectation, FoldExpectation):
        raise StructuralIdentityError(
            f"expected FoldExpectation, got {type(expectation)!r}"
        )
    return _record(
        DOMAIN_FOLD_EXPECTATION,
        [
            _field(
                "parent_cell",
                _u16(int(expectation.parent_cell), name="fold_expectation.parent_cell"),
            ),
            _field(
                "expected_token",
                _u16(
                    int(expectation.expected_token),
                    name="fold_expectation.expected_token",
                ),
            ),
            _field(
                "unresolved_expansion",
                _boolean(
                    bool(expectation.unresolved_expansion),
                    name="fold_expectation.unresolved_expansion",
                ),
            ),
            _field(
                "fold_rule_id",
                _text(expectation.fold_rule_id, name="fold_expectation.fold_rule_id"),
            ),
        ],
    )


def _encode_code_tuple(codes: Sequence[str], *, name: str) -> bytes:
    return _sequence_set_like(
        _text(code, name=f"{name}[{i}]") for i, code in enumerate(codes)
    )


# ---------------------------------------------------------------------------
# Public encoders and identities
# ---------------------------------------------------------------------------


def encode_structural_state(state: StructuralState) -> bytes:
    """Complete canonical preimage for a StructuralState.

    StructuralState (structural_semantics.py:265-323) declared field order:
    grid, mask, depth, provenance.
    """
    if not isinstance(state, StructuralState):
        raise StructuralIdentityError(
            f"expected StructuralState, got {type(state)!r}"
        )
    mask = state.mask
    if len(mask) != GRID_SIZE:
        raise StructuralIdentityError(f"mask length {len(mask)} != {GRID_SIZE}")
    mask_bytes = b"".join(
        _u16(int(m), name=f"state.mask[{i}]") for i, m in enumerate(mask)
    )
    if state.provenance is None:
        provenance_bytes = _ABSENT
    else:
        provenance_bytes = _PRESENT + _encode_parent_provenance(state.provenance)
    return _record(
        DOMAIN_STRUCTURAL_STATE,
        [
            _field("grid", _encode_grid(state.grid)),
            _field("mask", mask_bytes),
            _field("depth", _u64(int(state.depth), name="state.depth")),
            _field("provenance", provenance_bytes),
        ],
    )


def structural_state_identity(state: StructuralState) -> str:
    """Lowercase hex SHA-256 identity binding the COMPLETE StructuralState.

    Binds grid tokens, writable mask, depth, provenance presence, and every
    ParentProvenance field.  Two states sharing a grid but differing in mask,
    depth, or provenance have different identities.
    """
    return _digest(encode_structural_state(state))


def encode_oracle_next_state(next_state: OracleNextState) -> bytes:
    """Complete canonical preimage for an OracleNextState.

    OracleNextState (structural_oracle.py:66-86) declared field order: grid,
    expansion_targets, child_specifications, fold_expectations, quiescence,
    violation_codes, rationale_codes.  All seven are bound.
    """
    if not isinstance(next_state, OracleNextState):
        raise StructuralIdentityError(
            f"expected OracleNextState, got {type(next_state)!r}"
        )
    return _record(
        DOMAIN_ORACLE_NEXT_STATE,
        [
            _field("grid", _encode_grid(next_state.grid)),
            _field(
                "expansion_targets",
                _sequence_set_like(
                    _encode_expansion_target(t) for t in next_state.expansion_targets
                ),
            ),
            _field(
                "child_specifications",
                _sequence_set_like(
                    _encode_child_specification(c)
                    for c in next_state.child_specifications
                ),
            ),
            _field(
                "fold_expectations",
                _sequence_set_like(
                    _encode_fold_expectation(f) for f in next_state.fold_expectations
                ),
            ),
            _field(
                "quiescence",
                _boolean(bool(next_state.quiescence), name="next_state.quiescence"),
            ),
            _field(
                "violation_codes",
                _encode_code_tuple(
                    next_state.violation_codes, name="next_state.violation_codes"
                ),
            ),
            _field(
                "rationale_codes",
                _encode_code_tuple(
                    next_state.rationale_codes, name="next_state.rationale_codes"
                ),
            ),
        ],
    )


def oracle_next_state_identity(next_state: OracleNextState) -> str:
    """Lowercase hex SHA-256 identity binding the COMPLETE OracleNextState.

    Unlike OracleNextState.digest() (structural_oracle.py:78-86) this binds
    fold_expectations, rationale_codes, and ChildSpecification.seed_rule_id,
    and uses injective length-prefixed encoding rather than delimiter
    concatenation.
    """
    return _digest(encode_oracle_next_state(next_state))


def encode_oracle_transition(transition: OracleTransition) -> bytes:
    """Complete canonical preimage for an OracleTransition.

    OracleTransition (structural_oracle.py:89-104) declared field order:
    valid_next_states, canonical_next_state, quiescence, violation_codes,
    rationale_codes, expansion_targets, child_specifications,
    fold_expectations.  All eight are bound.

    ``valid_next_states`` is canonicalized by complete encoded bytes and is
    therefore candidate-order invariant.  ``canonical_next_state`` is bound
    separately and exactly as supplied; no canonical candidate is selected
    here.
    """
    if not isinstance(transition, OracleTransition):
        raise StructuralIdentityError(
            f"expected OracleTransition, got {type(transition)!r}"
        )
    return _record(
        DOMAIN_ORACLE_TRANSITION,
        [
            _field(
                "valid_next_states",
                _sequence_set_like(
                    encode_oracle_next_state(ns) for ns in transition.valid_next_states
                ),
            ),
            _field(
                "canonical_next_state",
                encode_oracle_next_state(transition.canonical_next_state),
            ),
            _field(
                "quiescence",
                _boolean(bool(transition.quiescence), name="transition.quiescence"),
            ),
            _field(
                "violation_codes",
                _encode_code_tuple(
                    transition.violation_codes, name="transition.violation_codes"
                ),
            ),
            _field(
                "rationale_codes",
                _encode_code_tuple(
                    transition.rationale_codes, name="transition.rationale_codes"
                ),
            ),
            _field(
                "expansion_targets",
                _sequence_set_like(
                    _encode_expansion_target(t) for t in transition.expansion_targets
                ),
            ),
            _field(
                "child_specifications",
                _sequence_set_like(
                    _encode_child_specification(c)
                    for c in transition.child_specifications
                ),
            ),
            _field(
                "fold_expectations",
                _sequence_set_like(
                    _encode_fold_expectation(f) for f in transition.fold_expectations
                ),
            ),
        ],
    )


def oracle_transition_identity(transition: OracleTransition) -> str:
    """Lowercase hex SHA-256 identity binding the COMPLETE OracleTransition."""
    return _digest(encode_oracle_transition(transition))
