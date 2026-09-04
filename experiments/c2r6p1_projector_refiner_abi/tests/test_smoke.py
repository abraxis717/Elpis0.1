"""Smoke: the whole bridge path on one fixed projected case."""
from __future__ import annotations

import conftest as C  # noqa: F401  (installs overlay, exposes helpers)
from c2r6p1_bridge import (
    BridgeRejectionCode,
    BridgeRejectionError,
    adapt_projection_to_refiner_input,
    build_envelope,
    legal_candidates,
    replay_transition_chain,
    run_refiner_bounded,
    NullRefiner,
    FirstLegalMoveRefiner,
    pack_529,
    roundtrip_529,
    one_hot,
)
from dataclasses import replace


def test_adapter_one_case(one_projected):
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    # structural identity carried through
    assert ri.grid81 == r.grid81
    assert ri.frozen_mask == r.frozen_mask
    assert ri.writable_mask == r.writable_mask
    assert ri.declared_features == r.declared_features
    assert ri.active_residual == r.active_residual
    assert ri.residual_ids == r.residual_ids
    # fingerprints: projection fingerprint preserved, refinement fp separate
    assert ri.projection_fingerprint == r.structural_input_fingerprint
    assert ri.refinement_state_fingerprint != r.structural_input_fingerprint
    # refiner schema mask == projector mask (no widening)
    for i in range(81):
        assert ri.structural_schema.writable_mask[i] == r.writable_mask[i]
        assert not (ri.structural_schema.writable_mask[i]
                    and not r.structural_schema.writable_mask[i])
    # digest bound
    assert ri.refiner_input_digest


def test_envelope_preserves_bindings(one_projected):
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    env = build_envelope(r, ri)
    assert env.structural_bindings is r.bindings
    assert env.projection_trace_digest == r.trace.trace_digest
    assert env.semantic_input_digest == r.semantic_input_digest
    assert env.envelope_digest == env.envelope_digest_computed()
    # envelope digest changes if the binding sidecar changes
    changed = replace(env, structural_bindings=replace(
        r.bindings, output_entity_ids=r.bindings.output_entity_ids + ("zz",)))
    assert changed.envelope_digest_computed() != env.envelope_digest_computed()


def test_null_refiner_continuity(one_projected):
    r = one_projected
    ri0 = adapt_projection_to_refiner_input(r)
    ri1, trace, applied = run_refiner_bounded(NullRefiner(), ri0, max_moves=8)
    assert applied == 0
    assert ri1.grid81 == ri0.grid81
    assert ri1.frozen_mask == ri0.frozen_mask
    assert ri1.writable_mask == ri0.writable_mask
    assert ri1.refinement_state_fingerprint == ri0.refinement_state_fingerprint
    assert trace.events[0].event_type == "KEEP"
    # replay reproduces byte-identical state
    ri_replayed = replay_transition_chain(r, trace)
    assert ri_replayed.grid81 == ri1.grid81
    assert ri_replayed.refinement_state_fingerprint == ri1.refinement_state_fingerprint


def test_first_legal_move(one_projected):
    r = one_projected
    ri0 = adapt_projection_to_refiner_input(r)
    cands = legal_candidates(ri0)
    if not cands:
        # degenerate: nothing legal -> refiner keeps
        ri1, trace, applied = run_refiner_bounded(FirstLegalMoveRefiner(), ri0, 8)
        assert applied == 0
        return
    ri1, trace, applied = run_refiner_bounded(FirstLegalMoveRefiner(), ri0, max_moves=8)
    assert applied >= 1
    assert trace.events[0].event_type == "TRANSITION_APPLIED"
    # fingerprint must have changed (structural mutation)
    assert trace.events[0].next_refinement_fingerprint != trace.events[0].prev_refinement_fingerprint
    # replay reproduces
    ri_replayed = replay_transition_chain(r, trace)
    assert ri_replayed.grid81 == ri1.grid81
    assert ri_replayed.refinement_state_fingerprint == ri1.refinement_state_fingerprint
    assert ri_replayed.active_residual == ri1.active_residual


def test_packer_roundtrip():
    for bit in (0, 511, 512, 528):
        decl, act = one_hot(bit)
        d, a = roundtrip_529(decl, act)
        assert d == decl
        assert a == act
    # all-zeros / all-ones
    z = tuple(0 for _ in range(529))
    o = tuple(1 for _ in range(529))
    assert roundtrip_529(z, z) == (z, z)
    assert roundtrip_529(o, o) == (o, o)
    assert roundtrip_529(o, z) == (o, z)


def test_reject_non_projected(one_projected):
    r = one_projected
    # craft a non-PROJECTED result by forcing status
    from c2r6p0.contracts import ProjectionStatus
    bad = replace(r, status=ProjectionStatus.INVALID_SEMANTIC_IR.value)
    try:
        adapt_projection_to_refiner_input(bad)
        raise AssertionError("expected rejection")
    except BridgeRejectionError as e:
        assert e.rejection.code is BridgeRejectionCode.NOT_PROJECTED
