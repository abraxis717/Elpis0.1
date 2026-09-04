"""Fingerprint continuity (mission 17).

Separate identities:
  * projection_fingerprint    — the initial projected structural input
                                (C2R6-P0 structural_input_fingerprint)
  * refinement_state_fingerprint — the mutable refinement state
Prove:
  * semantic binding change -> relevant envelope digest changes
  * legal structural mutation -> refinement_state_fingerprint changes
  * request/debug ID change -> NO structural identity change
"""
from __future__ import annotations

from dataclasses import replace

import conftest as C

from c2r6p0.contracts import ProjectionStatus
from c2r6p1_bridge import (
    FirstLegalMoveRefiner,
    adapt_projection_to_refiner_input,
    build_envelope,
    run_refiner_bounded,
)


def test_projection_fingerprint_untouched_by_adapter(one_projected):
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    # the adapter never overwrites the projector's initial fingerprint
    assert ri.projection_fingerprint == r.structural_input_fingerprint
    # and the two identities differ (initial vs mutable state)
    assert ri.refinement_state_fingerprint != ri.projection_fingerprint


def test_legal_mutation_changes_refinement_fp(one_projected):
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    ri1, trace, applied = run_refiner_bounded(
        FirstLegalMoveRefiner(), ri, max_moves=4
    )
    if applied == 0:
        return
    # legal structural mutation -> refinement_state_fingerprint changes
    # at EVERY applied transition (a greedy first-legal refiner may
    # oscillate between two states over 4 moves; what must hold is that
    # each applied mutation changes the mutable-state identity, while the
    # INITIAL projection identity never changes)
    assert ri1.projection_fingerprint == ri.projection_fingerprint
    # grid actually mutated somewhere in the chain
    assert any(ev.event_type == "TRANSITION_APPLIED" for ev in trace.events)
    # each applied transition changes the fingerprint exactly once
    fp = ri.refinement_state_fingerprint
    applied_fp_changes = 0
    for ev in trace.events:
        if ev.event_type == "TRANSITION_APPLIED":
            assert ev.next_refinement_fingerprint != fp
            applied_fp_changes += 1
            fp = ev.next_refinement_fingerprint
        else:
            assert ev.next_refinement_fingerprint == fp
    assert applied_fp_changes == applied


def test_semantic_binding_change_changes_envelope_only(one_projected):
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    env = build_envelope(r, ri)
    changed = C.rebind(r, bindings=replace(
        r.bindings,
        output_entity_ids=r.bindings.output_entity_ids + ("zz",),
    ))
    env2 = build_envelope(changed, adapt_projection_to_refiner_input(changed))
    # envelope digest (semantic identity) changes
    assert env.envelope_digest != env2.envelope_digest
    ri2 = adapt_projection_to_refiner_input(changed)
    # the MUTABLE structural refinement-state identity does NOT change
    # (same grid / masks / invariants)
    assert ri2.refinement_state_fingerprint == ri.refinement_state_fingerprint
    # the projector's initial input fingerprint DOES change (it embeds the
    # semantic bindings), proving the semantic sidecar is digest-bound
    assert ri2.projection_fingerprint != ri.projection_fingerprint


def test_request_debug_id_no_structural_change(project):
    from c2r6p0 import fixtures as F

    # same graph, two different request/debug ids; find PROJECTED seeds
    # deterministically (no ambient state: seed scan from a fixed base)
    cases = []
    s = 0
    while len(cases) < 2:
        g = F.gen_valid(s)
        r1 = project(C.wrap(g, request_id="A", debug_tag="d1"))
        if r1.status == "PROJECTED":
            r2 = project(C.wrap(g, request_id="B", debug_tag="d2"))
            cases.append((r1, r2))
        s += 1
    assert cases, "no PROJECTED case found in deterministic scan"
    r1, r2 = cases[0]
    assert r2.status == "PROJECTED"
    # identical structural content, different request identity
    assert r1.grid81 == r2.grid81
    assert r1.frozen_mask == r2.frozen_mask
    assert r1.writable_mask == r2.writable_mask
    ri1 = adapt_projection_to_refiner_input(r1)
    ri2 = adapt_projection_to_refiner_input(r2)
    assert ri1.projection_fingerprint == ri2.projection_fingerprint
    assert ri1.refinement_state_fingerprint == ri2.refinement_state_fingerprint
    assert ri1.refiner_input_digest == ri2.refiner_input_digest
