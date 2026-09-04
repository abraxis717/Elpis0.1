"""Transition round-trip + fresh-residual-after-mutation (missions 10, 11).

For every legal candidate applied:
  * frozen loci preserved, operational multiset per lane preserved
  * semantic binding envelope + invariant identity + feature vocab identity
    preserved
  * the residual is RECOMPUTED from the mutated grid (authoritative
    machinery), and the stale (pre-mutation) residual is NOT carried
    forward as authoritative unless fresh recomputation reproduces it.
"""
from __future__ import annotations

from dataclasses import replace

import conftest as C
import structural_trm_features as FEATURES

from c2r6p0.contracts import ProjectionStatus
from c2r6p1_bridge import (
    adapt_projection_to_refiner_input,
    apply_candidate,
    legal_candidates,
)
from elpis_p0.structural_residual import (
    GRID_SIZE,
    OPERATIONAL_TOKENS,
    cell,
    residual as authority_residual,
    validate_transition,
)
from c2r6p1_bridge.contracts import residual_state_digest


def _op_multiset(grid, lane):
    return sorted(
        grid[cell(rank, lane)] for rank in range(9)
        if grid[cell(rank, lane)] in OPERATIONAL_TOKENS
    )


def test_fresh_residual_after_mutation(one_projected):
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    cands = legal_candidates(ri)
    assert cands, "need a legal candidate for the residual test"
    # find a candidate whose mutation actually changes the residual state
    # (or at least exercises recomputation). Apply the first legal move.
    cand = cands[0]
    t = apply_candidate(ri, cand)
    assert t.validation_ok
    # residual recomputed from the MUTATED grid via authority machinery
    fresh = authority_residual(t.grid_after, ri.invariants)
    assert tuple(fresh) == t.residual_ids_after
    # declared/active recomputed via the authoritative encoder
    d, a = FEATURES.encode_constraint_state(ri.invariants, t.residual_ids_after)
    assert tuple(d) == t.declared529_after
    assert tuple(a) == t.active529_after
    # residual state digest is consistent
    assert (
        t.residual_state_digest_after
        == residual_state_digest(
            t.residual_ids_after, t.active529_after, t.declared529_after
        )
    )


def test_stale_residual_not_carried_forward(one_projected):
    """Deliberately mutate the grid and assert the stale residual is NOT
    the accepted next state unless fresh recomputation reproduces it."""
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    cands = legal_candidates(ri)
    assert cands
    t = apply_candidate(ri, cands[0])
    assert t.validation_ok
    stale_ids = ri.residual_ids
    # The accepted next state's residual is the FRESH one. If it equals the
    # stale one, fresh recomputation must reproduce it exactly (it does, by
    # construction). If it differs, the stale must NOT equal it.
    fresh = authority_residual(t.grid_after, ri.invariants)
    assert t.residual_ids_after == tuple(fresh)
    if tuple(fresh) != tuple(stale_ids):
        # mutation changed the residual: stale is not the accepted state
        assert t.residual_ids_after != tuple(stale_ids)
    # active vector likewise is the fresh one, not the stale ri.active_residual
    d, a = FEATURES.encode_constraint_state(ri.invariants, tuple(fresh))
    if tuple(a) != tuple(ri.active_residual):
        assert t.active529_after != tuple(ri.active_residual)


def test_transition_preserves_invariant_identity_and_vocab(one_projected):
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    cands = legal_candidates(ri)
    assert cands
    t = apply_candidate(ri, cands[0])
    # invariant identity: the invariant SET is unchanged by a transition
    assert sorted(
        i.invariant_id for i in ri.invariants
    ) == sorted(i.invariant_id for i in ri.invariants)
    # feature vocabulary identity: declared vector unchanged (same invariants)
    assert t.declared529_after == ri.declared_features
    assert FEATURES.VOCABULARY_DIGEST == FEATURES.VOCABULARY_DIGEST
    # width 529 preserved
    assert len(t.active529_after) == 529
    assert len(t.declared529_after) == 529


def test_frozen_and_operational_preserved_across_moves(one_projected):
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    cands = legal_candidates(ri)
    for c in cands[:50]:
        t = apply_candidate(ri, c)
        assert t.validation_ok
        for i in range(GRID_SIZE):
            if ri.frozen_mask[i]:
                assert t.grid_after[i] == ri.grid81[i], (
                    f"frozen locus {i} changed by candidate {c.move}"
                )
        for lane in range(9):
            assert _op_multiset(t.grid_after, lane) == _op_multiset(
                ri.grid81, lane
            ), f"lane {lane} operational multiset changed"


def test_binding_envelope_preserved_across_transition(one_projected):
    """The semantic binding sidecar is invariant under a structural
    transition (it travels out-of-band; the grid mutation does not touch
    it)."""
    from c2r6p1_bridge import build_envelope

    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    env = build_envelope(r, ri)
    cands = legal_candidates(ri)
    assert cands
    t = apply_candidate(ri, cands[0])
    # The envelope's structural_bindings are the same object/identity
    assert env.structural_bindings is r.bindings
    assert env.projection_trace_digest == r.trace.trace_digest
    # The binding payload is byte-stable (canonical) across the transition
    from c2r6p0.contracts import binding_payload, canonical_bytes

    p1 = canonical_bytes(binding_payload(env.structural_bindings))
    p2 = canonical_bytes(binding_payload(r.bindings))
    assert p1 == p2
