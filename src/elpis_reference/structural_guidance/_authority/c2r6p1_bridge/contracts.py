"""C2R6-P1 bridge contracts: the explicit refiner-facing input ABI.

``RefinerInputV1`` is the exact structural-refinement input consumed by the
existing deterministic refiner machinery. It reuses the authority input type
(``elpis_p0.structural_residual.StructuralSchemaV1``) for the lane/invariant
problem and adds ONLY what the refiner ABI additionally needs from the
projector:

  * the projector's frozen/writable mask (a SUBSET of the schema's
    authority: refiner_writable[i] <= projector_writable[i] is trivially
    true here, and projector_writable <= schema_writable is enforced by
    the adapter, never widened);
  * the projector's initial seed grid (stronger than the schema's
    degenerate seed: the projector places what the facts determine);
  * the 529-bit declared features / active residual (authoritative C2R7-C
    vocabulary; packable by the D0.1 lossless 4-slot prefix);
  * the residual invariant-id list;
  * the projector's structural input fingerprint (INITIAL identity; the
    mutable refinement state gets its own separate fingerprint).

Semantic identity is NOT part of RefinerInputV1. It travels out-of-band in
``RefinerEnvelopeV1`` so a structural refiner cannot become a semantic
reasoner (the residual firewall of the authority, extended to the bridge).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..elpis_p0.structural_residual import (
    GRID_SIZE,
    LaneBindingV1,
    StructuralSchemaV1,
    StructuralInvariantV1,
)
from ..c2r6p0.contracts import StructuralBindingV1

# ---------------------------------------------------------------------------
# Canonical helpers (same formula as c2r6p0 / the structural authority)
# ---------------------------------------------------------------------------


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


import hashlib


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def domain_digest(domain: str, payload: Any) -> str:
    return sha256_hex(domain.encode("utf-8") + b"\x00" + canonical_bytes(payload))


# Digest domains (separate from the projector's, so bridge identities never
# alias projector identities).
REFINER_INPUT_DOMAIN = "elpis.c2r6p1.refiner-input.v1"
REFINEMENT_STATE_DOMAIN = "elpis.c2r6p1.refinement-state.v1"
BINDING_ENVELOPE_DOMAIN = "elpis.c2r6p1.refiner-envelope.v1"
TRANSITION_DOMAIN = "elpis.c2r6p1.refiner-transition.v1"
TRACE_DOMAIN = "elpis.c2r6p1.refiner-transition-trace.v1"
RESIDUAL_STATE_DOMAIN = "elpis.c2r6p1.residual-state.v1"


# ---------------------------------------------------------------------------
# Typed rejection (fail closed; no free-form exceptions at the bridge API)
# ---------------------------------------------------------------------------


class BridgeRejectionCode(str, Enum):
    """Every deterministic bridge rejection carries one of these codes."""

    NOT_PROJECTED = "ERR.NOT_PROJECTED"
    SCHEMA_MISMATCH = "ERR.SCHEMA_MISMATCH"
    GRID_WRONG_WIDTH = "ERR.GRID_WRONG_WIDTH"
    MASK_WRONG_WIDTH = "ERR.MASK_WRONG_WIDTH"
    MASK_VALUES = "ERR.MASK_VALUES"
    FROZEN_WRITABLE_OVERLAP = "ERR.FROZEN_WRITABLE_OVERLAP"
    MASKS_DO_NOT_COVER = "ERR.MASKS_DO_NOT_COVER"
    TERMINAL_NOT_FROZEN = "ERR.TERMINAL_NOT_FROZEN"
    GRID_TOKENS = "ERR.GRID_TOKENS"
    NO_AUTHORITY_SCHEMA = "ERR.NO_AUTHORITY_SCHEMA"
    SCHEMA_INVALID = "ERR.SCHEMA_INVALID"
    SCHEMA_LANES_MISMATCH = "ERR.SCHEMA_LANES_MISMATCH"
    SCHEMA_INVARIANTS_MISMATCH = "ERR.SCHEMA_INVARIANTS_MISMATCH"
    AUTHORITY_WIDENING = "ERR.AUTHORITY_WIDENING"
    LANE_BINDING_MISMATCH = "ERR.LANE_BINDING_MISMATCH"
    LANE_OUT_OF_RANGE = "ERR.LANE_OUT_OF_RANGE"
    DUPLICATE_LANE_BINDING = "ERR.DUPLICATE_LANE_BINDING"
    RESIDUAL_WIDTH = "ERR.RESIDUAL_WIDTH"
    FEATURE_WIDTH = "ERR.FEATURE_WIDTH"
    RESIDUAL_VOCABULARY = "ERR.RESIDUAL_VOCABULARY"
    STALE_RESIDUAL = "ERR.STALE_RESIDUAL"
    STALE_DECLARED = "ERR.STALE_DECLARED"
    PROJECTION_FINGERPRINT_MISMATCH = "ERR.PROJECTION_FINGERPRINT_MISMATCH"
    BINDING_CELL_OUT_OF_RANGE = "ERR.BINDING_CELL_OUT_OF_RANGE"
    BINDING_DUPLICATE_ID = "ERR.BINDING_DUPLICATE_ID"
    BINDING_FROZEN_MISMATCH = "ERR.BINDING_FROZEN_MISMATCH"
    BINDING_TOKEN_MISMATCH = "ERR.BINDING_TOKEN_MISMATCH"
    CANDIDATE_MALFORMED = "ERR.CANDIDATE_MALFORMED"
    CANDIDATE_FROZEN_WRITE = "ERR.CANDIDATE_FROZEN_WRITE"
    CANDIDATE_ILLEGAL_TOKEN = "ERR.CANDIDATE_ILLEGAL_TOKEN"
    TRANSITION_REJECTED = "ERR.TRANSITION_REJECTED"
    TRACE_SCHEMA_MISMATCH = "ERR.TRACE_SCHEMA_MISMATCH"
    TRACE_EMPTY = "ERR.TRACE_EMPTY"
    TRACE_BAD_SEQ = "ERR.TRACE_BAD_SEQ"
    TRACE_FINGERPRINT_DISCONTINUITY = "ERR.TRACE_FINGERPRINT_DISCONTINUITY"
    TRACE_CANDIDATE_MISMATCH = "ERR.TRACE_CANDIDATE_MISMATCH"
    TRACE_PREDECESSOR_DIGEST_MISMATCH = (
        "ERR.TRACE_PREDECESSOR_DIGEST_MISMATCH"
    )
    TRACE_EVENT_TYPE = "ERR.TRACE_EVENT_TYPE"
    REFINER_STATE_MISMATCH = "ERR.REFINER_STATE_MISMATCH"
    PACKER_REJECTED = "ERR.PACKER_REJECTED"
    ENVELOPE_MISMATCH = "ERR.ENVELOPE_MISMATCH"
    MUTANT_ACCEPTED = "ERR.MUTANT_ACCEPTED"


@dataclass(frozen=True)
class BridgeRejection:
    """Deterministic typed rejection detail (no exception reprs)."""

    code: BridgeRejectionCode
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "detail": self.detail}


class BridgeRejectionError(Exception):
    """Raised by the adapter/refiners carrying a typed BridgeRejection."""

    def __init__(self, rejection: BridgeRejection) -> None:
        super().__init__(
            f"{rejection.code.value}: {json.dumps(rejection.detail, sort_keys=True)}"
        )
        self.rejection = rejection


# ---------------------------------------------------------------------------
# RefinerInputV1 — the exact structural-refiner input
# ---------------------------------------------------------------------------


def refinement_state_payload(
    grid81: tuple[int, ...],
    frozen_mask: tuple[int, ...],
    writable_mask: tuple[int, ...],
    invariants: tuple[StructuralInvariantV1, ...],
) -> dict[str, Any]:
    """Canonical payload of the MUTABLE refinement state.

    Deliberately excludes the initial projection fingerprint and any
    semantic identity: it identifies the structural search state as it
    exists at a point in refinement.
    """
    return {
        "schema": "c2r6p1.refinement-state.v1",
        "grid81": list(grid81),
        "frozen_mask": list(frozen_mask),
        "writable_mask": list(writable_mask),
        "invariants": [
            {
                "invariant_id": i.invariant_id,
                "kind": i.kind,
                "lanes": list(i.lanes),
            }
            for i in sorted(invariants, key=lambda i: i.invariant_id)
        ],
    }


def refinement_state_fingerprint(
    grid81: tuple[int, ...],
    frozen_mask: tuple[int, ...],
    writable_mask: tuple[int, ...],
    invariants: tuple[StructuralInvariantV1, ...],
) -> str:
    return domain_digest(
        REFINEMENT_STATE_DOMAIN,
        refinement_state_payload(
            grid81, frozen_mask, writable_mask, invariants
        ),
    )


def residual_state_digest(
    residual_ids: tuple[str, ...],
    active529: tuple[int, ...],
    declared529: tuple[int, ...],
) -> str:
    """Digest of an authoritative residual state (ids + both 529 vectors)."""
    return domain_digest(
        RESIDUAL_STATE_DOMAIN,
        {
            "schema": "c2r6p1.residual-state.v1",
            "residual_ids": list(residual_ids),
            "active529": list(active529),
            "declared529": list(declared529),
        },
    )


@dataclass(frozen=True)
class RefinerInputV1:
    """Exact structural-refinement input (structural state ONLY).

    ``structural_schema`` is the authority schema rebuilt under the
    PROJECTOR's mask (refiner_writable <= projector_writable by
    construction, projector_writable <= authority_writable enforced by the
    adapter). ``structural_schema`` (the projector's own, degenerate-seed
    one) is preserved for provenance in the envelope, not here.
    """

    schema: str  # "c2r6p1.refiner-input.v1"
    # structural state (mutable refinement state, initial value)
    grid81: tuple[int, ...]
    frozen_mask: tuple[int, ...]
    writable_mask: tuple[int, ...]
    invariants: tuple[StructuralInvariantV1, ...]
    lane_bindings: tuple[LaneBindingV1, ...]
    structural_schema: StructuralSchemaV1  # rebuilt under projector mask
    # residual side (authoritative C2R7-C vocabulary, width 529)
    declared_features: tuple[int, ...]
    active_residual: tuple[int, ...]
    residual_ids: tuple[str, ...]
    # fingerprints (separate identities: initial vs mutable)
    projection_fingerprint: str  # == projector structural_input_fingerprint
    refinement_state_fingerprint: str  # initial refinement state
    # identity of the input itself
    refiner_input_digest: str = ""

    def __post_init__(self) -> None:
        if self.schema != "c2r6p1.refiner-input.v1":
            raise ValueError(f"unsupported RefinerInputV1 schema {self.schema!r}")
        for name, seq in (
            ("grid81", self.grid81),
            ("frozen_mask", self.frozen_mask),
            ("writable_mask", self.writable_mask),
            ("declared_features", self.declared_features),
            ("active_residual", self.active_residual),
        ):
            if not isinstance(seq, tuple):
                raise ValueError(f"{name} must be a tuple")
        if len(self.grid81) != GRID_SIZE or len(self.frozen_mask) != GRID_SIZE:
            raise ValueError("grid81/frozen_mask must be 81 entries")
        if len(self.writable_mask) != GRID_SIZE:
            raise ValueError("writable_mask must be 81 entries")

    def structural_view(self) -> dict[str, Any]:
        """Exactly what a structural refiner may see. No semantic id."""
        return {
            "grid81": list(self.grid81),
            "frozen_mask": list(self.frozen_mask),
            "writable_mask": list(self.writable_mask),
            "declared_features": list(self.declared_features),
            "active_residual": list(self.active_residual),
            "residual_ids": list(self.residual_ids),
        }


def refiner_input_payload(ri: RefinerInputV1) -> dict[str, Any]:
    return {
        "schema": ri.schema,
        "grid81": list(ri.grid81),
        "frozen_mask": list(ri.frozen_mask),
        "writable_mask": list(ri.writable_mask),
        "invariants": [
            {
                "invariant_id": i.invariant_id,
                "kind": i.kind,
                "lanes": list(i.lanes),
            }
            for i in sorted(ri.invariants, key=lambda i: i.invariant_id)
        ],
        "lane_bindings": [
            {
                "lane": b.lane,
                "semantic_id": b.semantic_id,
                "role": b.role,
                "operational_token": b.operational_token,
            }
            for b in sorted(ri.lane_bindings, key=lambda b: b.lane)
        ],
        "structural_schema_digest": ri.structural_schema.schema_digest,
        "declared_features": list(ri.declared_features),
        "active_residual": list(ri.active_residual),
        "residual_ids": list(ri.residual_ids),
        "projection_fingerprint": ri.projection_fingerprint,
        "refinement_state_fingerprint": ri.refinement_state_fingerprint,
    }


def digest_refiner_input(ri: RefinerInputV1) -> str:
    return domain_digest(REFINER_INPUT_DOMAIN, refiner_input_payload(ri))


def signed_refiner_input(ri: RefinerInputV1) -> RefinerInputV1:
    """Bind refiner_input_digest (everything but itself)."""
    from dataclasses import replace

    return replace(ri, refiner_input_digest=digest_refiner_input(ri))


# ---------------------------------------------------------------------------
# RefinerEnvelopeV1 — semantic bindings preserved out-of-band
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RefinerEnvelopeV1:
    """The bridge envelope: structural input + semantic sidecar + digests.

    The structural model sees only ``refiner_input.structural_view()``;
    the outer deterministic system retains ``structural_bindings``.
    """

    schema: str  # "c2r6p1.refiner-envelope.v1"
    refiner_input: RefinerInputV1
    structural_bindings: StructuralBindingV1
    projection_trace_digest: str
    semantic_input_digest: str
    projection_digest: str
    envelope_digest: str = ""

    def __post_init__(self) -> None:
        if self.schema != "c2r6p1.refiner-envelope.v1":
            raise ValueError(
                f"unsupported RefinerEnvelopeV1 schema {self.schema!r}"
            )

    def envelope_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "refiner_input_digest": self.refiner_input.refiner_input_digest,
            "structural_bindings": _binding_payload(self.structural_bindings),
            "projection_trace_digest": self.projection_trace_digest,
            "semantic_input_digest": self.semantic_input_digest,
            "projection_digest": self.projection_digest,
        }

    def envelope_digest_computed(self) -> str:
        return domain_digest(
            BINDING_ENVELOPE_DOMAIN, self.envelope_payload()
        )


def _binding_payload(b: StructuralBindingV1) -> dict[str, Any]:
    # Import lazily to avoid a cycle at module import time.
    from ..c2r6p0.contracts import binding_payload

    return binding_payload(b)


def signed_envelope(env: RefinerEnvelopeV1) -> RefinerEnvelopeV1:
    from dataclasses import replace

    return replace(env, envelope_digest=env.envelope_digest_computed())


# ---------------------------------------------------------------------------
# Candidates, transition results, trace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateMoveV1:
    """One structurally legal candidate, in canonical enumeration order.

    ``move`` is the D0.1 decoder tuple ("set", index, token) |
    ("move", lane, rank). ``enum_index`` is its position in the
    deterministic enumeration (the canonical ordering).
    """

    move: tuple[str, int, int]
    enum_index: int


@dataclass(frozen=True)
class TransitionResultV1:
    """Outcome of applying one candidate through the refiner ABI."""

    candidate: CandidateMoveV1
    grid_before: tuple[int, ...]
    grid_after: tuple[int, ...]
    residual_ids_before: tuple[str, ...]
    residual_ids_after: tuple[str, ...]
    active529_after: tuple[int, ...]
    declared529_after: tuple[int, ...]
    validation_ok: bool
    validation_error: str  # "" when ok
    refinement_state_fingerprint_after: str
    residual_state_digest_after: str
    transition_digest: str = ""


def transition_payload(t: TransitionResultV1) -> dict[str, Any]:
    return {
        "schema": "c2r6p1.refiner-transition.v1",
        "candidate": {"move": list(t.candidate.move),
                      "enum_index": t.candidate.enum_index},
        "grid_before": list(t.grid_before),
        "grid_after": list(t.grid_after),
        "residual_ids_before": list(t.residual_ids_before),
        "residual_ids_after": list(t.residual_ids_after),
        "active529_after": list(t.active529_after),
        "declared529_after": list(t.declared529_after),
        "validation_ok": t.validation_ok,
        "validation_error": t.validation_error,
        "refinement_state_fingerprint_after": (
            t.refinement_state_fingerprint_after
        ),
        "residual_state_digest_after": t.residual_state_digest_after,
    }


def signed_transition(t: TransitionResultV1) -> TransitionResultV1:
    from dataclasses import replace

    return replace(
        t,
        transition_digest=domain_digest(TRANSITION_DOMAIN, transition_payload(t)),
    )


@dataclass(frozen=True)
class RefinerTransitionEvent:
    """One structural refinement event (never a semantic projection event)."""

    seq: int
    event_type: str  # "TRANSITION_APPLIED" | "KEEP"
    candidate_move: tuple[str, int, int] | None  # None for KEEP
    enum_index: int | None
    validation_ok: bool
    validation_error: str
    prev_refinement_fingerprint: str
    next_refinement_fingerprint: str
    prev_residual_digest: str
    next_residual_digest: str
    transition_digest: str


@dataclass(frozen=True)
class RefinerTransitionTraceV1:
    """Replayable structural refinement trace (separate from projection)."""

    schema: str  # "c2r6p1.refiner-transition-trace.v1"
    events: tuple[RefinerTransitionEvent, ...]
    trace_digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "events": [
                {
                    "seq": e.seq,
                    "event_type": e.event_type,
                    "candidate_move": (
                        list(e.candidate_move)
                        if e.candidate_move is not None
                        else None
                    ),
                    "enum_index": e.enum_index,
                    "validation_ok": e.validation_ok,
                    "validation_error": e.validation_error,
                    "prev_refinement_fingerprint": (
                        e.prev_refinement_fingerprint
                    ),
                    "next_refinement_fingerprint": (
                        e.next_refinement_fingerprint
                    ),
                    "prev_residual_digest": e.prev_residual_digest,
                    "next_residual_digest": e.next_residual_digest,
                    "transition_digest": e.transition_digest,
                }
                for e in self.events
            ],
            "trace_digest": self.trace_digest,
        }

    def to_canonical_bytes(self) -> bytes:
        return canonical_bytes(self.to_dict())


def trace_digest_computed(trace: RefinerTransitionTraceV1) -> str:
    """Digest over everything but the digest itself (idempotent recompute)."""
    payload = trace.to_dict()
    payload.pop("trace_digest", None)
    return domain_digest(TRACE_DOMAIN, payload)


def signed_trace(trace: RefinerTransitionTraceV1) -> RefinerTransitionTraceV1:
    from dataclasses import replace

    return replace(trace, trace_digest=trace_digest_computed(trace))
