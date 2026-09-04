"""Adapter contract: losslessness, typed rejection, fingerprint separation.

Missions 4, 5, 17.
"""
from __future__ import annotations

import conftest as C
from dataclasses import replace

from c2r6p0.contracts import ProjectionStatus
from c2r6p1_bridge import (
    BridgeRejectionCode,
    BridgeRejectionError,
    adapt_projection_to_refiner_input,
    build_envelope,
)
from elpis_p0.structural_residual import GRID_SIZE


def _projected_from_status(r, status):
    return replace(r, status=status)


def test_adapter_lossless_structural_identity(one_projected):
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    assert ri.grid81 == r.grid81
    assert ri.frozen_mask == r.frozen_mask
    assert ri.writable_mask == r.writable_mask
    assert ri.invariants == r.invariants
    assert ri.lane_bindings == r.lane_bindings
    assert ri.declared_features == r.declared_features
    assert ri.active_residual == r.active_residual
    assert ri.residual_ids == r.residual_ids
    # lossless: every refiner-relevant structural bit survived
    for i in range(529):
        assert ri.declared_features[i] == r.declared_features[i]
        assert ri.active_residual[i] == r.active_residual[i]
    for i in range(GRID_SIZE):
        assert ri.grid81[i] == r.grid81[i]


def test_adapter_fingerprint_separation(one_projected):
    """Mission 17: projection fp (initial) vs refinement fp (mutable) are
    separate identities; the adapter never overwrites the projection fp."""
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    assert ri.projection_fingerprint == r.structural_input_fingerprint
    assert ri.refinement_state_fingerprint != ri.projection_fingerprint
    # the refiner-input digest binds both
    assert len(ri.refiner_input_digest) == 64


def test_adapter_rejects_all_five_statuses(one_projected):
    r = one_projected
    for status in (
        "INVALID_SEMANTIC_IR",
        "UNSUPPORTED_SEMANTIC_SHAPE",
        "DECOMPOSITION_REQUIRED",
        "AMBIGUOUS_BINDING",
        "STRUCTURAL_CONTRADICTION",
    ):
        bad = _projected_from_status(r, status)
        rej = C.expect_rejection(
            lambda b=bad: adapt_projection_to_refiner_input(b),
            BridgeRejectionCode.NOT_PROJECTED,
        )
        assert rej.detail["status"] == status


def test_adapter_rejects_wrong_type():
    rej = C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(object()),
        BridgeRejectionCode.SCHEMA_MISMATCH,
    )
    assert rej.detail["actual_type"] == "object"


def test_request_debug_id_do_not_change_structural_identity(project):
    """Mission 17: request/debug ID changes -> no structural identity
    change (same grid, masks, fingerprints, refiner-input digest)."""
    from c2r6p0 import fixtures as F

    g = F.gen_valid(3)
    r1 = project(C.wrap(g, request_id="req_A", debug_tag="dbg_1"))
    r2 = project(C.wrap(g, request_id="req_B", debug_tag="dbg_2"))
    assert r1.status == "PROJECTED" and r2.status == "PROJECTED"
    assert r1.grid81 == r2.grid81
    assert r1.frozen_mask == r2.frozen_mask
    assert r1.structural_input_fingerprint == r2.structural_input_fingerprint
    ri1 = adapt_projection_to_refiner_input(r1)
    ri2 = adapt_projection_to_refiner_input(r2)
    assert ri1.refiner_input_digest == ri2.refiner_input_digest
    assert ri1.refinement_state_fingerprint == ri2.refinement_state_fingerprint
    assert ri1.projection_fingerprint == ri2.projection_fingerprint


def test_semantic_binding_change_changes_envelope_digest(one_projected):
    """Mission 17: semantic binding changes -> relevant envelope digest
    changes (the out-of-band sidecar is digest-bound)."""
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    env = build_envelope(r, ri)
    changed_bindings = replace(
        r.bindings,
        output_entity_ids=r.bindings.output_entity_ids + ("zz_extra",),
    )
    r2 = C.rebind(r, bindings=changed_bindings)
    env2 = build_envelope(r2, adapt_projection_to_refiner_input(r2))
    assert env.envelope_digest != env2.envelope_digest
    ri2 = adapt_projection_to_refiner_input(r2)
    # the MUTABLE structural refinement-state identity is untouched by a
    # binding-only change (grid/masks/invariants identical)
    assert ri2.refinement_state_fingerprint == ri.refinement_state_fingerprint
    # while the semantic sidecar is digest-bound: the projection
    # fingerprint (which embeds the bindings) moves
    assert ri2.projection_fingerprint != ri.projection_fingerprint
