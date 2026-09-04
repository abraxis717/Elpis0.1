"""adapt_projection_to_refiner_input: the bridge adapter.

Pure, deterministic, lossless for all refiner-relevant structural
information. No semantic inference, no topology solving, no model access,
no filesystem / network / time dependence during adaptation (the authority
imports are installed once; adaptation itself reads only the projection).

Authority boundary (mission 5): the adapter may NOT widen writable
authority. It re-derives the refiner's schema from the projector's own
mask (a subset of the authority schema's mask by the projector's own
fail-closed invariant), so:

    refiner_writable[i] == projector_writable[i] <= authority_writable[i]

and every projector-frozen locus stays frozen under validate_transition.

Every non-PROJECTED result is deterministically rejected with a typed
BridgeRejection; the five projector rejection statuses are mapped 1:1 so
they never enter the structural refiner.
"""
from __future__ import annotations

from typing import Any, NoReturn

import structural_trm_features as FEATURES
from elpis_p0.structural_residual import (
    GRID_SIZE,
    TERMINAL_CELL,
    StructuralSchemaV1,
    StructuralInvariantV1,
    build_structural_schema,
    structural_schema_payload,
    STRUCTURAL_RESIDUAL_DOMAIN,
    _domain_digest,
)

from .contracts import (
    BINDING_ENVELOPE_DOMAIN,  # noqa: F401  (re-exported for envelope build)
    BridgeRejection,
    BridgeRejectionCode,
    BridgeRejectionError,
    RefinerEnvelopeV1,
    RefinerInputV1,
    domain_digest,
    refinement_state_fingerprint,
    residual_state_digest,
    signed_envelope,
    signed_refiner_input,
)
from c2r6p0.contracts import ProjectionResultV1, ProjectionStatus
from c2r6p0.residual import build_fingerprint as projector_build_fingerprint


# ---------------------------------------------------------------------------
# Validation (fail closed; typed)
# ---------------------------------------------------------------------------


def _reject(code: BridgeRejectionCode, **detail: Any) -> "NoReturn":  # noqa: F821
    raise BridgeRejectionError(BridgeRejection(code=code, detail=detail))


def validate_projection_for_bridge(r: ProjectionResultV1) -> None:
    """Deterministically reject anything that must not enter the refiner."""
    if not isinstance(r, ProjectionResultV1):
        _reject(
            BridgeRejectionCode.SCHEMA_MISMATCH,
            actual_type=type(r).__name__,
        )
    err_code = r.error.code if r.error is not None else ""
    err_rule = r.error.rule if r.error is not None else ""
    if r.status != ProjectionStatus.PROJECTED.value:
        _reject(
            BridgeRejectionCode.NOT_PROJECTED,
            status=r.status,
            error_code=err_code,
            rule=err_rule,
        )

    # structural surface widths / domains
    if len(r.grid81) != GRID_SIZE:
        _reject(BridgeRejectionCode.GRID_WRONG_WIDTH, width=len(r.grid81))
    if len(r.frozen_mask) != GRID_SIZE:
        _reject(BridgeRejectionCode.MASK_WRONG_WIDTH, width=len(r.frozen_mask))
    if len(r.writable_mask) != GRID_SIZE:
        _reject(BridgeRejectionCode.MASK_WRONG_WIDTH, width=len(r.writable_mask))
    if any(v not in (0, 1) for v in r.frozen_mask) or any(
        v not in (0, 1) for v in r.writable_mask
    ):
        _reject(BridgeRejectionCode.MASK_VALUES)
    if any(r.frozen_mask[i] and r.writable_mask[i] for i in range(GRID_SIZE)):
        _reject(BridgeRejectionCode.FROZEN_WRITABLE_OVERLAP)
    if any(
        not r.frozen_mask[i] and not r.writable_mask[i]
        for i in range(GRID_SIZE)
    ):
        _reject(BridgeRejectionCode.MASKS_DO_NOT_COVER)
    if r.writable_mask[TERMINAL_CELL] != 0:
        _reject(BridgeRejectionCode.TERMINAL_NOT_FROZEN)
    if any(not 0 <= v <= 9 for v in r.grid81):
        _reject(BridgeRejectionCode.GRID_TOKENS)

    # residual / feature vectors
    if len(r.declared_features) != 529:
        _reject(BridgeRejectionCode.FEATURE_WIDTH, width=len(r.declared_features))
    if len(r.active_residual) != 529:
        _reject(BridgeRejectionCode.RESIDUAL_WIDTH, width=len(r.active_residual))
    if any(v not in (0, 1) for v in r.declared_features) or any(
        v not in (0, 1) for v in r.active_residual
    ):
        _reject(BridgeRejectionCode.RESIDUAL_VOCABULARY)
    if FEATURES.FEATURE_WIDTH != 529:
        _reject(BridgeRejectionCode.RESIDUAL_VOCABULARY, live=FEATURES.FEATURE_WIDTH)

    # the residual must be consistent with the grid (fresh, not stale)
    from elpis_p0.structural_residual import residual as authority_residual

    fresh = authority_residual(r.grid81, r.invariants)
    if tuple(fresh) != tuple(r.residual_ids):
        _reject(
            BridgeRejectionCode.STALE_RESIDUAL,
            stored=list(r.residual_ids),
            fresh=list(fresh),
        )
    declared_fresh, active_fresh = FEATURES.encode_constraint_state(
        r.invariants, r.residual_ids
    )
    if tuple(declared_fresh) != tuple(r.declared_features):
        _reject(BridgeRejectionCode.STALE_DECLARED)
    if tuple(active_fresh) != tuple(r.active_residual):
        _reject(BridgeRejectionCode.STALE_RESIDUAL)

    # authority schema present and self-consistent
    if r.structural_schema is None:
        _reject(BridgeRejectionCode.NO_AUTHORITY_SCHEMA)
    try:
        r.structural_schema.validate()
    except Exception as exc:  # StructuralSchemaError
        _reject(BridgeRejectionCode.SCHEMA_INVALID, detail=str(exc))
    # lane bindings identical (same objects, same order by lane)
    schema_lanes = tuple(sorted(r.structural_schema.lanes, key=lambda b: b.lane))
    proj_lanes = tuple(sorted(r.lane_bindings, key=lambda b: b.lane))
    if schema_lanes != proj_lanes:
        _reject(BridgeRejectionCode.LANE_BINDING_MISMATCH)
    schema_invs = tuple(sorted(r.structural_schema.invariants,
                               key=lambda i: i.invariant_id))
    if schema_invs != tuple(sorted(r.invariants, key=lambda i: i.invariant_id)):
        _reject(BridgeRejectionCode.SCHEMA_INVARIANTS_MISMATCH)

    # semantic binding sidecar: typed structural-domain validation (the
    # envelope preserves the bindings out-of-band, but a binding that
    # references a nonexistent locus or contradicts the frozen authority
    # must fail closed before the refiner sees anything). Runs BEFORE the
    # global fingerprint recompute so each violation gets its own typed code.
    _validate_bindings(r)

    # fingerprint present and FRESH: the projector's structural input
    # fingerprint is a pure function of the projected structural state
    # (grid, masks, invariants, lane bindings, declared, active,
    # semantic bindings). Recompute it: any tampered/stale fingerprint
    # fails closed here, so a mutated projection can never pose as a
    # different-but-trusted initial input.
    if not r.structural_input_fingerprint:
        _reject(BridgeRejectionCode.SCHEMA_MISMATCH, detail="empty fingerprint")
    fresh_fp = projector_build_fingerprint(
        r.grid81,
        r.frozen_mask,
        r.writable_mask,
        r.invariants,
        r.lane_bindings,
        r.declared_features,
        r.active_residual,
        r.bindings,
    )
    if fresh_fp != r.structural_input_fingerprint:
        _reject(
            BridgeRejectionCode.PROJECTION_FINGERPRINT_MISMATCH,
            stored=r.structural_input_fingerprint,
            fresh=fresh_fp,
        )


def _validate_bindings(r: ProjectionResultV1) -> None:
    """Typed structural-domain checks on the semantic binding sidecar."""
    seen: set[str] = set()
    for b in r.bindings.op_bindings:
        if b.binding_id in seen:
            _reject(BridgeRejectionCode.BINDING_DUPLICATE_ID,
                    binding_id=b.binding_id)
        seen.add(b.binding_id)
        if not (0 <= b.cell < GRID_SIZE):
            _reject(BridgeRejectionCode.BINDING_CELL_OUT_OF_RANGE,
                    cell=b.cell, binding_id=b.binding_id)
        if not (0 <= b.lane < 9) or not (0 <= b.rank < 9):
            _reject(BridgeRejectionCode.LANE_OUT_OF_RANGE,
                    lane=b.lane, rank=b.rank, binding_id=b.binding_id)
        if b.cell != b.rank * 9 + b.lane:
            _reject(BridgeRejectionCode.BINDING_CELL_OUT_OF_RANGE,
                    cell=b.cell, lane=b.lane, rank=b.rank,
                    binding_id=b.binding_id)
        # a frozen-fact binding must sit on a frozen locus, and its grid
        # token must be the bound operational token
        if b.frozen and not r.frozen_mask[b.cell]:
            _reject(BridgeRejectionCode.BINDING_FROZEN_MISMATCH,
                    cell=b.cell, binding_id=b.binding_id)
        if r.grid81[b.cell] != b.token:
            _reject(BridgeRejectionCode.BINDING_TOKEN_MISMATCH,
                    cell=b.cell, token=b.token,
                    actual=r.grid81[b.cell], binding_id=b.binding_id)
    # edge bindings may only reference real lanes
    for e in r.bindings.edge_bindings:
        for lane in e.lanes:
            if not (0 <= lane < 9):
                _reject(BridgeRejectionCode.LANE_OUT_OF_RANGE,
                        lane=lane, binding_id=e.binding_id)


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------


def _build_refiner_schema(
    r: ProjectionResultV1,
) -> StructuralSchemaV1:
    """Rebuild the authority schema under the PROJECTOR's (narrower) mask.

    This is what the refiner actually consumes as its transition authority:
    its writable mask is exactly the projector's writable mask, so the
    refiner can never widen authority, and validate_transition enforces it.
    """
    from dataclasses import replace

    base = r.structural_schema
    new = replace(base, writable_mask=r.writable_mask)
    digest = _domain_digest(
        STRUCTURAL_RESIDUAL_DOMAIN, structural_schema_payload(new)
    )
    return StructuralSchemaV1(
        semantic_request_digest=base.semantic_request_digest,
        lanes=base.lanes,
        writable_mask=r.writable_mask,
        initial_grid=base.initial_grid,
        invariants=base.invariants,
        schema_digest=digest,
    )


def adapt_projection_to_refiner_input(
    r: ProjectionResultV1,
) -> RefinerInputV1:
    """ProjectionResultV1 -> RefinerInputV1 (pure, deterministic, lossless)."""
    validate_projection_for_bridge(r)
    schema = _build_refiner_schema(r)
    schema.validate()
    # authority non-widening: refiner writable <= projector writable (equal)
    # <= authority (schema) writable
    for i in range(GRID_SIZE):
        if schema.writable_mask[i] and not r.structural_schema.writable_mask[i]:
            _reject(
                BridgeRejectionCode.AUTHORITY_WIDENING, cell=i
            )
    ri = RefinerInputV1(
        schema="c2r6p1.refiner-input.v1",
        grid81=r.grid81,
        frozen_mask=r.frozen_mask,
        writable_mask=r.writable_mask,
        invariants=r.invariants,
        lane_bindings=r.lane_bindings,
        structural_schema=schema,
        declared_features=r.declared_features,
        active_residual=r.active_residual,
        residual_ids=r.residual_ids,
        projection_fingerprint=r.structural_input_fingerprint,
        refinement_state_fingerprint=refinement_state_fingerprint(
            r.grid81, r.frozen_mask, r.writable_mask, r.invariants
        ),
        refiner_input_digest="",
    )
    return signed_refiner_input(ri)


def build_envelope(r: ProjectionResultV1, ri: RefinerInputV1) -> RefinerEnvelopeV1:
    """Wrap the refiner input with the out-of-band semantic binding sidecar."""
    validate_projection_for_bridge(r)
    env = RefinerEnvelopeV1(
        schema="c2r6p1.refiner-envelope.v1",
        refiner_input=ri,
        structural_bindings=r.bindings,
        projection_trace_digest=r.trace.trace_digest,
        semantic_input_digest=r.semantic_input_digest,
        projection_digest=r.projection_digest,
        envelope_digest="",
    )
    return signed_envelope(env)
