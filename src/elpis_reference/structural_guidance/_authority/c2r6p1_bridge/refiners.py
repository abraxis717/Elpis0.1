"""Deterministic test-only refiners + transition execution + replay.

Two integration-test refiners (NO learned inference):

  * NullRefiner          — emits KEEP, no structural mutation.
    Purpose: complete ABI traversal continuity (byte-identical state).
  * FirstLegalMoveRefiner — deterministically applies the FIRST legal
    candidate in the vendored D0.1 canonical enumeration order.
    Purpose: prove a real structural mutation traverses the bridge.

Both read ONLY the structural refiner input (grid, writable mask, and the
authoritative schema for transition validation). Neither reads the
residual as a *decision input* (the residual is recomputed AFTER the move,
never used to choose it), neither reads a target grid, teacher, or expected
answer, and neither reads a semantic identity.

Residual recomputation boundary (mission 11): the projector residual is the
residual of the INITIAL projected seed. After ANY accepted refiner mutation,
the residual is recomputed from the authoritative structural machinery
(``residual`` + ``encode_constraint_state``) over the MUTATED grid. The
stale (pre-mutation) residual is never carried forward as authoritative.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Sequence

from ..c2r7c import structural_trm_features as FEATURES
from ..elpis_p0.structural_residual import (
    GRID_SIZE,
    residual as authority_residual,
    validate_transition,
)

from ..vendor_d01 import legal_decoder as _decoder_mod
from .contracts import (
    BridgeRejection,
    BridgeRejectionCode,
    BridgeRejectionError,
    CandidateMoveV1,
    RefinerEnvelopeV1,
    RefinerInputV1,
    RefinerTransitionEvent,
    RefinerTransitionTraceV1,
    TransitionResultV1,
    refinement_state_fingerprint,
    residual_state_digest,
    signed_trace,
    signed_transition,
)
from .adapter import validate_projection_for_bridge  # noqa: F401 (re-export)


class _Ref:  # noqa: N801
    """Small holder so refiners expose a uniform .name / .step surface."""


def _reject(code: BridgeRejectionCode, **detail: Any) -> None:
    raise BridgeRejectionError(BridgeRejection(code=code, detail=detail))


# ---------------------------------------------------------------------------
# Candidate enumeration (vendored D0.1 decoder, canonical order)
# ---------------------------------------------------------------------------


def legal_candidates(ri: RefinerInputV1) -> tuple[CandidateMoveV1, ...]:
    """Deterministic legal candidates from (grid, writable mask) ONLY.

    The candidate domain is the vendored D0.1 ``legal_moves`` enumeration
    FILTERED to the moves that pass the authoritative
    ``validate_transition`` under the refiner's (projector-mask) schema.
    This is required because the projector freezes loci that the D0.1
    degenerate schema leaves writable: a D0.1-legal ``move`` out of a
    frozen operational locus would write a frozen cell, so it is excluded
    (deterministically rejected) rather than offered. The canonical
    ordering is the surviving D0.1 enumeration order; ``enum_index`` is
    the position within that filtered canonical order. No
    residual/target/teacher is read.
    """
    dec = _decoder_mod()
    moves = dec.legal_moves(list(ri.grid81), list(ri.writable_mask))
    kept: list[tuple[str, int, int]] = []
    for m in moves:
        try:
            after = dec.apply_move(list(ri.grid81), m)
        except Exception:
            continue  # malformed at the decoder level: excluded
        try:
            validate_transition(ri.grid81, tuple(after), ri.structural_schema)
        except Exception:
            continue  # legal under D0.1 mask, not under projector mask
        kept.append(m)
    return tuple(
        CandidateMoveV1(move=m, enum_index=i) for i, m in enumerate(kept)
    )


# ---------------------------------------------------------------------------
# Transition execution (fresh residual recomputation)
# ---------------------------------------------------------------------------


def apply_candidate(
    ri: RefinerInputV1,
    candidate: CandidateMoveV1,
) -> TransitionResultV1:
    """Apply one candidate through the refiner ABI; recompute residual fresh.

    Fail-closed: the candidate must be structurally legal AND pass the
    authoritative ``validate_transition`` under the refiner's (projector-
    mask) schema. On success the residual is recomputed from the mutated
    grid; the stale residual is never carried forward.
    """
    dec = _decoder_mod()
    op, a, b = candidate.move

    # typed malformed check (op token, index/token domains)
    if op not in ("set", "move"):
        _reject(BridgeRejectionCode.CANDIDATE_ILLEGAL_TOKEN, op=op)
    if op == "set":
        if not (0 <= a < GRID_SIZE) or not (0 <= b <= 9):
            _reject(BridgeRejectionCode.CANDIDATE_MALFORMED, move=list(candidate.move))
        if ri.frozen_mask[a]:
            _reject(BridgeRejectionCode.CANDIDATE_FROZEN_WRITE, index=a)
    else:  # move: a=lane, b=rank
        if not (0 <= a < 9) or not (0 <= b < 9):
            _reject(BridgeRejectionCode.CANDIDATE_MALFORMED, move=list(candidate.move))
        target = b * 9 + a  # cell(rank, lane)
        if ri.frozen_mask[target]:
            _reject(BridgeRejectionCode.CANDIDATE_FROZEN_WRITE, index=target)

    grid_before = list(ri.grid81)
    try:
        grid_after = dec.apply_move(grid_before, candidate.move)
    except Exception as exc:
        raise BridgeRejectionError(
            BridgeRejection(code=BridgeRejectionCode.CANDIDATE_MALFORMED,
                            detail={"error": str(exc)})
        ) from exc

    # structural legality of the candidate itself (must be enumerable)
    if candidate.move not in [c.move for c in legal_candidates(ri)]:
        raise BridgeRejectionError(
            BridgeRejection(code=BridgeRejectionCode.CANDIDATE_MALFORMED,
                            detail={"move": list(candidate.move)})
        )

    # authoritative transition validation under the refiner schema
    validation_error = ""
    try:
        validate_transition(
            tuple(grid_before), tuple(grid_after), ri.structural_schema
        )
    except Exception as exc:
        validation_error = str(exc)
    # cross-check with the vendored decoder contract (must agree)
    try:
        dec.validate_transition_d0(grid_before, grid_after,
                                   list(ri.writable_mask))
    except Exception as exc:
        if not validation_error:
            validation_error = str(exc)

    residual_ids_after = authority_residual(tuple(grid_after), ri.invariants)
    declared_after, active_after = FEATURES.encode_constraint_state(
        ri.invariants, residual_ids_after
    )
    if len(declared_after) != 529 or len(active_after) != 529:
        raise BridgeRejectionError(
            BridgeRejection(code=BridgeRejectionCode.RESIDUAL_WIDTH,
                            detail={"declared": len(declared_after),
                                    "active": len(active_after)})
        )

    t = TransitionResultV1(
        candidate=candidate,
        grid_before=ri.grid81,
        grid_after=tuple(grid_after),
        residual_ids_before=ri.residual_ids,
        residual_ids_after=tuple(residual_ids_after),
        active529_after=tuple(active_after),
        declared529_after=tuple(declared_after),
        validation_ok=(validation_error == ""),
        validation_error=validation_error,
        refinement_state_fingerprint_after=refinement_state_fingerprint(
            tuple(grid_after), ri.frozen_mask, ri.writable_mask, ri.invariants
        ),
        residual_state_digest_after=residual_state_digest(
            tuple(residual_ids_after), tuple(active_after), tuple(declared_after)
        ),
        transition_digest="",
    )
    return signed_transition(t)


def _next_input(ri: RefinerInputV1, t: TransitionResultV1) -> RefinerInputV1:
    """Advance the refiner input to the post-transition state (fresh
    residual). The initial projection fingerprint is preserved; only the
    mutable refinement-state fingerprint changes."""
    return signed_replace(
        ri,
        grid81=t.grid_after,
        active_residual=t.active529_after,
        declared_features=t.declared529_after,
        residual_ids=t.residual_ids_after,
        refinement_state_fingerprint=t.refinement_state_fingerprint_after,
    )


def signed_replace(ri: RefinerInputV1, **fields: Any) -> RefinerInputV1:
    from .contracts import signed_refiner_input

    return signed_refiner_input(replace(ri, **fields))


# ---------------------------------------------------------------------------
# Refiner A: NullRefiner (KEEP; byte-identical continuity)
# ---------------------------------------------------------------------------


class NullRefiner:
    """Emits KEEP. Establishes complete ABI traversal without mutation."""

    name = "NullRefiner"

    def step(
        self,
        ri: RefinerInputV1,
        trace: RefinerTransitionTraceV1,
    ) -> tuple[RefinerInputV1, RefinerTransitionTraceV1, bool]:
        seq = len(trace.events)
        event = RefinerTransitionEvent(
            seq=seq,
            event_type="KEEP",
            candidate_move=None,
            enum_index=None,
            validation_ok=True,
            validation_error="",
            prev_refinement_fingerprint=ri.refinement_state_fingerprint,
            next_refinement_fingerprint=ri.refinement_state_fingerprint,
            prev_residual_digest=residual_state_digest(
                ri.residual_ids, ri.active_residual, ri.declared_features
            ),
            next_residual_digest=residual_state_digest(
                ri.residual_ids, ri.active_residual, ri.declared_features
            ),
            transition_digest="",
        )
        new_trace = signed_trace(
            replace(trace, events=trace.events + (event,))
        )
        return ri, new_trace, False  # kept (no mutation)


# ---------------------------------------------------------------------------
# Refiner B: FirstLegalMoveRefiner (deterministic first legal candidate)
# ---------------------------------------------------------------------------


def _keep_step(
    ri: RefinerInputV1,
    trace: RefinerTransitionTraceV1,
) -> tuple[RefinerInputV1, RefinerTransitionTraceV1, bool]:
    """Emit a KEEP event (no structural mutation)."""
    seq = len(trace.events)
    event = RefinerTransitionEvent(
        seq=seq,
        event_type="KEEP",
        candidate_move=None,
        enum_index=None,
        validation_ok=True,
        validation_error="",
        prev_refinement_fingerprint=ri.refinement_state_fingerprint,
        next_refinement_fingerprint=ri.refinement_state_fingerprint,
        prev_residual_digest=residual_state_digest(
            ri.residual_ids, ri.active_residual, ri.declared_features
        ),
        next_residual_digest=residual_state_digest(
            ri.residual_ids, ri.active_residual, ri.declared_features
        ),
        transition_digest="",
    )
    new_trace = signed_trace(replace(trace, events=trace.events + (event,)))
    return ri, new_trace, False


class FirstLegalMoveRefiner:
    """Applies the FIRST MUTATING legal candidate in canonical order.

    It inspects neither the residual, target identity, teacher data, nor the
    expected answer: the choice is the first candidate whose ``apply_move``
    result differs from the current grid. A no-op rewrite of a writable
    filled cell to its own token is legal but not a structural mutation;
    applying it would 2-cycle with its own inverse, so it is skipped
    deterministically. If no candidate mutates the grid the step is KEEP
    (bounded halt), never a silent no-op mutation.
    """
    name = "FirstLegalMoveRefiner"

    def step(
        self,
        ri: RefinerInputV1,
        trace: RefinerTransitionTraceV1,
    ) -> tuple[RefinerInputV1, RefinerTransitionTraceV1, bool]:
        dec = _decoder_mod()
        cands = legal_candidates(ri)
        cand = None
        for c in cands:
            if tuple(dec.apply_move(list(ri.grid81), c.move)) != ri.grid81:
                cand = c
                break
        if cand is None:
            # No mutating legal move: behave as KEEP (bounded halt).
            return _keep_step(ri, trace)
        seq = len(trace.events)
        t = apply_candidate(ri, cand)
        if not t.validation_ok:
            _reject(
                BridgeRejectionCode.TRANSITION_REJECTED,
                candidate=list(cand.move),
                error=t.validation_error,
            )
        event = RefinerTransitionEvent(
            seq=seq,
            event_type="TRANSITION_APPLIED",
            candidate_move=t.candidate.move,
            enum_index=t.candidate.enum_index,
            validation_ok=True,
            validation_error="",
            prev_refinement_fingerprint=ri.refinement_state_fingerprint,
            next_refinement_fingerprint=t.refinement_state_fingerprint_after,
            prev_residual_digest=residual_state_digest(
                ri.residual_ids, ri.active_residual, ri.declared_features
            ),
            next_residual_digest=t.residual_state_digest_after,
            transition_digest=t.transition_digest,
        )
        new_trace = signed_trace(replace(trace, events=trace.events + (event,)))
        return _next_input(ri, t), new_trace, True


def empty_trace() -> RefinerTransitionTraceV1:
    return signed_trace(
        RefinerTransitionTraceV1(schema="c2r6p1.refiner-transition-trace.v1",
                                 events=(), trace_digest="")
    )


def run_refiner_bounded(
    refiner,
    ri: RefinerInputV1,
    max_moves: int,
) -> tuple[RefinerInputV1, RefinerTransitionTraceV1, int]:
    """Run a refiner for up to ``max_moves`` structural moves.

    Returns (final_input, final_trace, applied_moves). Stops early on KEEP.
    """
    trace = empty_trace()
    applied = 0
    cur = ri
    for _ in range(max_moves):
        cur, trace, moved = refiner.step(cur, trace)
        if not moved:
            break
        applied += 1
    return cur, trace, applied


# ---------------------------------------------------------------------------
# Replay (mission 16): re-derive the whole chain from projection + trace
# ---------------------------------------------------------------------------


def replay_transition_chain(
    initial_projection,
    trace: RefinerTransitionTraceV1,
) -> RefinerInputV1:
    """Replay a structural transition chain and verify every link.

    Requires byte-identical final grid/masks/residual/fingerprint and rejects
    any altered candidate, altered fingerprint, frozen write, or reordered
    event.
    """
    from .adapter import adapt_projection_to_refiner_input

    if trace.schema != "c2r6p1.refiner-transition-trace.v1":
        _reject(BridgeRejectionCode.TRACE_SCHEMA_MISMATCH,
                schema=trace.schema)
    if trace.trace_digest != signed_trace(trace).trace_digest:
        _reject(BridgeRejectionCode.TRACE_FINGERPRINT_DISCONTINUITY,
                detail="trace digest mismatch")

    ri = adapt_projection_to_refiner_input(initial_projection)
    for i, ev in enumerate(trace.events):
        if ev.seq != i:
            _reject(BridgeRejectionCode.TRACE_BAD_SEQ, seq=ev.seq, expected=i)
        if ev.event_type not in ("TRANSITION_APPLIED", "KEEP"):
            _reject(BridgeRejectionCode.TRACE_EVENT_TYPE,
                    event_type=ev.event_type)
        if ev.prev_refinement_fingerprint != ri.refinement_state_fingerprint:
            _reject(
                BridgeRejectionCode.TRACE_FINGERPRINT_DISCONTINUITY,
                expected=ri.refinement_state_fingerprint,
                actual=ev.prev_refinement_fingerprint,
            )
        if ev.event_type == "KEEP":
            if ev.candidate_move is not None:
                _reject(BridgeRejectionCode.TRACE_CANDIDATE_MISMATCH,
                        detail="KEEP carries a candidate")
            if ev.next_refinement_fingerprint != ri.refinement_state_fingerprint:
                _reject(BridgeRejectionCode.TRACE_FINGERPRINT_DISCONTINUITY,
                        detail="KEEP changed the fingerprint")
            continue

        # TRANSITION_APPLIED: re-derive and compare
        if ev.candidate_move is None or ev.enum_index is None:
            _reject(BridgeRejectionCode.TRACE_CANDIDATE_MISMATCH,
                    detail="TRANSITION_APPLIED missing candidate")
        move_t: tuple[str, int, int] = ev.candidate_move
        idx_i: int = ev.enum_index
        cand = CandidateMoveV1(move=move_t, enum_index=idx_i)
        t = apply_candidate(ri, cand)
        if not t.validation_ok:
            _reject(BridgeRejectionCode.TRANSITION_REJECTED,
                    candidate=list(move_t),
                    error=t.validation_error)
        if t.grid_after != replay_grid_after(ri, move_t):
            _reject(BridgeRejectionCode.TRACE_CANDIDATE_MISMATCH,
                    detail="grid after mismatch")
        if t.refinement_state_fingerprint_after != ev.next_refinement_fingerprint:
            _reject(
                BridgeRejectionCode.TRACE_FINGERPRINT_DISCONTINUITY,
                expected=t.refinement_state_fingerprint_after,
                actual=ev.next_refinement_fingerprint,
            )
        if t.residual_state_digest_after != ev.next_residual_digest:
            _reject(
                BridgeRejectionCode.TRACE_PREDECESSOR_DIGEST_MISMATCH,
                detail="residual digest mismatch",
            )
        if t.transition_digest != ev.transition_digest:
            _reject(
                BridgeRejectionCode.TRACE_CANDIDATE_MISMATCH,
                detail="transition digest mismatch",
            )
        ri = _next_input(ri, t)
    return ri


def replay_grid_after(ri: RefinerInputV1, move: tuple[str, int, int]) -> tuple[int, ...]:
    """Recompute the post-move grid directly (byte-identity check in replay)."""
    dec = _decoder_mod()
    return tuple(dec.apply_move(list(ri.grid81), move))
