"""Trace chaining + replay (missions 15, 16).

The structural refinement trace is separate from the projection trace.
Replay requires byte-identical final grid/masks/residual/fingerprint and
rejects altered candidate, altered prev/next fingerprint, frozen write, or
reordered events.
"""
from __future__ import annotations

from dataclasses import replace

import conftest as C

from c2r6p1_bridge import (
    BridgeRejectionCode,
    FirstLegalMoveRefiner,
    NullRefiner,
    adapt_projection_to_refiner_input,
    apply_candidate,
    empty_trace,
    replay_transition_chain,
    run_refiner_bounded,
    signed_trace,
)
from c2r6p1_bridge.contracts import (
    RefinerTransitionTraceV1,
)


def _refine(r, refiner, moves):
    ri = adapt_projection_to_refiner_input(r)
    ri1, trace, applied = run_refiner_bounded(refiner, ri, max_moves=moves)
    return ri, ri1, trace, applied


def test_trace_is_separate_from_projection_trace(one_projected):
    r = one_projected
    _, _, trace, _ = _refine(r, NullRefiner(), 1)
    # separate schema + separate digest domain
    assert trace.schema == "c2r6p1.refiner-transition-trace.v1"
    assert trace.schema != r.trace.schema
    assert trace.trace_digest != r.trace.trace_digest
    # no semantic projection event types in the refinement trace
    for ev in trace.events:
        assert ev.event_type in ("TRANSITION_APPLIED", "KEEP")
        assert ev.event_type not in (
            "SEMANTIC_NODE_ACCEPTED", "LANE_ASSIGNED", "ROLE_PLACED",
        )


def test_replay_null_continuity_byte_identical(one_projected):
    r = one_projected
    ri, ri1, trace, applied = _refine(r, NullRefiner(), 8)
    assert applied == 0
    ri_replayed = replay_transition_chain(r, trace)
    assert ri_replayed.grid81 == ri1.grid81
    assert ri_replayed.frozen_mask == ri1.frozen_mask
    assert ri_replayed.writable_mask == ri1.writable_mask
    assert ri_replayed.active_residual == ri1.active_residual
    assert ri_replayed.declared_features == ri1.declared_features
    assert ri_replayed.refinement_state_fingerprint == ri1.refinement_state_fingerprint
    assert ri_replayed.refiner_input_digest == ri1.refiner_input_digest


def test_replay_first_legal_byte_identical(one_projected):
    r = one_projected
    ri, ri1, trace, applied = _refine(r, FirstLegalMoveRefiner(), 8)
    if applied == 0:
        return
    ri_replayed = replay_transition_chain(r, trace)
    assert ri_replayed.grid81 == ri1.grid81
    assert ri_replayed.frozen_mask == ri1.frozen_mask
    assert ri_replayed.writable_mask == ri1.writable_mask
    assert ri_replayed.active_residual == ri1.active_residual
    assert ri_replayed.residual_ids == ri1.residual_ids
    assert ri_replayed.refinement_state_fingerprint == ri1.refinement_state_fingerprint


def test_replay_rejects_reordered_events(one_projected):
    r = one_projected
    ri, ri1, trace, applied = _refine(r, FirstLegalMoveRefiner(), 8)
    if applied < 2:
        return
    evs = list(trace.events)
    # deterministic reorder: swap events 0 and 1 (both TRANSITION_APPLIED
    # for a run of >=2 applied moves). The swapped event's seq then does
    # not match its position -> typed TRACE_BAD_SEQ.
    evs[0], evs[1] = evs[1], evs[0]
    assert evs[0].event_type == "TRANSITION_APPLIED"
    assert evs[1].event_type == "TRANSITION_APPLIED"
    bad = signed_trace(replace(trace, events=tuple(evs)))
    C.expect_rejection(
        lambda: replay_transition_chain(r, bad),
        BridgeRejectionCode.TRACE_BAD_SEQ,
    )


def test_replay_rejects_altered_candidate(one_projected):
    r = one_projected
    ri, ri1, trace, applied = _refine(r, FirstLegalMoveRefiner(), 8)
    if applied < 1:
        return
    ev = trace.events[0]
    # alter the candidate locus (keep it structurally plausible: same op,
    # different index) -> replay must reject
    op, a, b = ev.candidate_move
    new_a = (a + 1) % 81
    altered = replace(ev, candidate_move=(op, new_a, b),
                      enum_index=ev.enum_index)
    bad = signed_trace(replace(trace, events=(altered,)))
    C.expect_rejection(
        lambda: replay_transition_chain(r, bad),
        (
            BridgeRejectionCode.TRACE_FINGERPRINT_DISCONTINUITY,
            BridgeRejectionCode.TRACE_CANDIDATE_MISMATCH,
            BridgeRejectionCode.TRANSITION_REJECTED,
        ),
    )


def test_replay_rejects_altered_prev_fingerprint(one_projected):
    r = one_projected
    ri, ri1, trace, applied = _refine(r, FirstLegalMoveRefiner(), 4)
    if applied < 1:
        return
    ev = trace.events[0]
    altered = replace(ev, prev_refinement_fingerprint="0" * 64)
    bad = signed_trace(replace(trace, events=(altered,)))
    C.expect_rejection(
        lambda: replay_transition_chain(r, bad),
        BridgeRejectionCode.TRACE_FINGERPRINT_DISCONTINUITY,
    )


def test_apply_candidate_rejects_frozen_write(one_projected):
    """Direct typed rejection: a candidate writing a frozen locus fails
    closed with CANDIDATE_FROZEN_WRITE (before any validation path)."""
    from c2r6p1_bridge.contracts import CandidateMoveV1

    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    frozen = next(i for i in range(81) if r.frozen_mask[i])
    cand = CandidateMoveV1(move=("set", frozen, 4), enum_index=99)
    rec = C.expect_rejection(
        lambda: apply_candidate(ri, cand),
        BridgeRejectionCode.CANDIDATE_FROZEN_WRITE,
    )
    assert rec.detail.get("index") == frozen


def test_replay_rejects_write_to_frozen_locus(one_projected):
    """Replay of a trace event whose candidate writes a frozen locus must
    reject (the re-applied candidate hits the same typed gate)."""
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    frozen = next(i for i in range(81) if r.frozen_mask[i])
    from c2r6p1_bridge.contracts import RefinerTransitionEvent

    ev = RefinerTransitionEvent(
        seq=0,
        event_type="TRANSITION_APPLIED",
        candidate_move=("set", frozen, 4),
        enum_index=0,
        validation_ok=True,
        validation_error="",
        prev_refinement_fingerprint=ri.refinement_state_fingerprint,
        next_refinement_fingerprint="f" * 64,
        prev_residual_digest="a" * 64,
        next_residual_digest="b" * 64,
        transition_digest="c" * 64,
    )
    bad = signed_trace(
        RefinerTransitionTraceV1(
            schema="c2r6p1.refiner-transition-trace.v1", events=(ev,)
        )
    )
    C.expect_rejection(
        lambda: replay_transition_chain(r, bad),
        (
            BridgeRejectionCode.CANDIDATE_FROZEN_WRITE,
            BridgeRejectionCode.CANDIDATE_MALFORMED,
        ),
    )


def test_replay_rejects_bad_seq(one_projected):
    r = one_projected
    ri, ri1, trace, applied = _refine(r, NullRefiner(), 2)
    evs = [replace(e, seq=e.seq + 5) for e in trace.events]
    bad = signed_trace(replace(trace, events=tuple(evs)))
    C.expect_rejection(
        lambda: replay_transition_chain(r, bad),
        BridgeRejectionCode.TRACE_BAD_SEQ,
    )


def test_replay_rejects_unknown_event_type(one_projected):
    r = one_projected
    _, _, trace, _ = _refine(r, NullRefiner(), 1)
    ev = trace.events[0]
    altered = replace(ev, event_type="MUTATE")
    bad = signed_trace(replace(trace, events=(altered,)))
    C.expect_rejection(
        lambda: replay_transition_chain(r, bad),
        BridgeRejectionCode.TRACE_EVENT_TYPE,
    )


def test_replay_rejects_wrong_schema(one_projected):
    r = one_projected
    _, _, trace, _ = _refine(r, NullRefiner(), 1)
    bad = replace(trace, schema="c2r6p1.refiner-transition-trace.v2")
    C.expect_rejection(
        lambda: replay_transition_chain(r, bad),
        BridgeRejectionCode.TRACE_SCHEMA_MISMATCH,
    )


def test_trace_chain_replayable_multiple_moves(one_projected):
    """Full chain 1->2->4->8 moves: each link verifies, final state
    reproducible from (projection, trace) alone."""
    r = one_projected
    for n in (1, 2, 4, 8):
        ri, ri1, trace, applied = _refine(r, FirstLegalMoveRefiner(), n)
        ri_replayed = replay_transition_chain(r, trace)
        assert ri_replayed.grid81 == ri1.grid81
        assert ri_replayed.refinement_state_fingerprint == ri1.refinement_state_fingerprint
        # every event's prev == previous event's next (chain continuity)
        fp = ri.refinement_state_fingerprint
        for ev in trace.events:
            assert ev.prev_refinement_fingerprint == fp
            fp = ev.next_refinement_fingerprint
