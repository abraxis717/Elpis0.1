"""Typed fail-closed gates — canonical regression coverage (C2R6-P1 R1).

These three gates exist in the canonical bridge and are each proven below to
reject with their SPECIFIC typed code. Before this file, the suite covered
only the ``set``-branch frozen-write gate; the ``move``-branch frozen-write
gate, the KEEP-event-carries-a-candidate gate, and the corrupted residual-
digest replay gate had no test that would fail if the gate were removed.

Each test is non-vacuous by construction (it requires an applied move or a
frozen locus to exist, and asserts that precondition) and asserts the EXACT
typed rejection code — never a bare ``except`` that could swallow its own
assertion. The forensic incident evidence (``mutation/probe.py``) carried the
same three "useful missing test concepts"; this is the clean canonical
re-implementation, not a copy of the forensic scratch.
"""
from __future__ import annotations

from dataclasses import replace

import conftest as C

from c2r6p1_bridge import (
    BridgeRejectionCode,
    CandidateMoveV1,
    FirstLegalMoveRefiner,
    RefinerTransitionEvent,
    RefinerTransitionTraceV1,
    adapt_projection_to_refiner_input,
    apply_candidate,
    empty_trace,
    replay_transition_chain,
    residual_state_digest,
    run_refiner_bounded,
    signed_trace,
)
from elpis_p0.structural_residual import GRID_SIZE


def _applied_trace(r):
    """Run FirstLegalMoveRefiner to a real chain of >=1 applied moves.

    Returns (ri, trace, applied) and asserts the chain is non-vacuous.
    """
    ri = adapt_projection_to_refiner_input(r)
    _, trace, applied = run_refiner_bounded(FirstLegalMoveRefiner(), ri, 4)
    assert applied >= 1, "need a non-vacuous applied chain (>=1 move)"
    return ri, trace, applied


def test_apply_candidate_move_frozen_target_rejected(one_projected):
    """The ``move`` branch of ``apply_candidate`` must reject a relocation
    whose target cell is frozen with CANDIDATE_FROZEN_WRITE (not the generic
    malformed/transition path).

    ``move`` semantics: a=lane, b=rank, target cell = rank*9 + lane. Pick a
    frozen locus ``f`` and decompose it into (lane=f%9, rank=f//9) so the
    target is EXACTLY the frozen locus.
    """
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    frozen = [i for i in range(GRID_SIZE) if r.frozen_mask[i]]
    assert frozen, "need a frozen locus"
    f = frozen[0]
    lane, rank = f % 9, f // 9
    assert rank * 9 + lane == f  # target cell is exactly the frozen locus
    cand = CandidateMoveV1(move=("move", lane, rank), enum_index=0)
    rec = C.expect_rejection(
        lambda: apply_candidate(ri, cand),
        BridgeRejectionCode.CANDIDATE_FROZEN_WRITE,
    )
    # the specific gate fired for THIS locus, not the generic one
    assert rec.detail.get("index") == f


def test_apply_candidate_set_frozen_target_still_rejected(one_projected):
    """Positive control for the ``set`` branch (already covered elsewhere,
    kept here so the move-branch test is not the only frozen-write proof)."""
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    frozen = next(i for i in range(GRID_SIZE) if r.frozen_mask[i])
    token = next(t for t in range(10) if t != r.grid81[frozen])
    rec = C.expect_rejection(
        lambda: apply_candidate(
            ri, CandidateMoveV1(move=("set", frozen, token), enum_index=0)
        ),
        BridgeRejectionCode.CANDIDATE_FROZEN_WRITE,
    )
    assert rec.detail.get("index") == frozen


def test_replay_rejects_keep_event_with_candidate(one_projected):
    """A KEEP event must NOT carry a candidate. Construct a well-formed
    single-KEEP trace whose KEEP carries a candidate; replay must reject with
    TRACE_CANDIDATE_MISMATCH (the KEEP-candidate gate), not a generic code."""
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    rd = residual_state_digest(
        ri.residual_ids, ri.active_residual, ri.declared_features
    )
    ev = RefinerTransitionEvent(
        seq=0,
        event_type="KEEP",
        candidate_move=("set", 0, 4),
        enum_index=0,
        validation_ok=True,
        validation_error="",
        prev_refinement_fingerprint=ri.refinement_state_fingerprint,
        next_refinement_fingerprint=ri.refinement_state_fingerprint,
        prev_residual_digest=rd,
        next_residual_digest=rd,
        transition_digest="",
    )
    bad = signed_trace(
        RefinerTransitionTraceV1(
            schema="c2r6p1.refiner-transition-trace.v1", events=(ev,)
        )
    )
    rec = C.expect_rejection(
        lambda: replay_transition_chain(r, bad),
        BridgeRejectionCode.TRACE_CANDIDATE_MISMATCH,
    )
    # the SPECIFIC gate fired (KEEP carrying a candidate), not a seq/fp gate
    assert "KEEP" in str(rec.detail)


def test_replay_rejects_corrupted_residual_digest(one_projected):
    """Corrupt ONLY the next_residual_digest of one TRANSITION_APPLIED event
    (re-sign the trace). Replay must reject with
    TRACE_PREDECESSOR_DIGEST_MISMATCH — the residual-digest continuity gate.
    A generic candidate/fingerprint mutation is NOT the expected code."""
    r = one_projected
    ri, trace, applied = _applied_trace(r)
    applied_events = [e for e in trace.events if e.event_type == "TRANSITION_APPLIED"]
    assert applied_events, "need an applied event to corrupt"
    idx = list(trace.events).index(applied_events[0])
    arr = list(trace.events)
    arr[idx] = replace(arr[idx], next_residual_digest="C" + "0" * 20)
    bad = signed_trace(
        RefinerTransitionTraceV1(schema=trace.schema, events=tuple(arr))
    )
    rec = C.expect_rejection(
        lambda: replay_transition_chain(r, bad),
        BridgeRejectionCode.TRACE_PREDECESSOR_DIGEST_MISMATCH,
    )
    assert "residual" in str(rec.detail)
