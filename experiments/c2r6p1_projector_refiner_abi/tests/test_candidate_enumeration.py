"""Candidate enumeration safety (mission 9).

For representative projected cases (chain, branch, fan-in, fan-out, route,
memory, constraint, interface, unresolved EXPANSION):
  * no candidate targets a frozen cell
  * every candidate target is writable
  * candidate token is valid (placeable, 0..9)
  * applying a candidate passes validate_transition
  * illegal candidates are excluded / deterministically rejected
"""
from __future__ import annotations

from dataclasses import replace

import conftest as C

from c2r6p0.contracts import ProjectionStatus
from c2r6p1_bridge import (
    BridgeRejectionCode,
    BridgeRejectionError,
    CandidateMoveV1,
    adapt_projection_to_refiner_input,
    apply_candidate,
    legal_candidates,
)
from elpis_p0.contracts import BasisToken
from elpis_p0.structural_residual import (
    GRID_SIZE,
    PLACEABLE_TOKENS,
    OPERATIONAL_TOKENS,
    cell,
    validate_transition,
)

ALL_TOKENS = tuple(int(t) for t in BasisToken)
LANES = 9
RANKS = 9


def _named_projected():
    """Named C2R6-P0 fixtures covering the required shapes, projected only."""
    from c2r6p0 import fixtures as F
    from c2r6p0 import projector
    from c2r6p0.rules import load_ruleset

    rs = load_ruleset()
    out = []
    for fx in F._named():
        r = projector.project(
            C.wrap(fx.graph, request_id=f"cand_{fx.name}"), rs
        )
        if r.status == ProjectionStatus.PROJECTED.value:
            out.append((fx.name, r))
    return out


def _candidates_for(r):
    ri = adapt_projection_to_refiner_input(r)
    return ri, legal_candidates(ri)


def test_every_named_shape_enumeration_safety():
    cases = _named_projected()
    assert len(cases) >= 5, "need several named projected shapes"
    total_cands = 0
    for name, r in cases:
        ri, cands = _candidates_for(r)
        total_cands += len(cands)
        for c in cands:
            op, a, b = c.move
            if op == "set":
                # target writable, not frozen
                assert ri.writable_mask[a] == 1, (
                    f"{name}: set targets frozen cell {a}"
                )
                assert ri.frozen_mask[a] == 0
                # candidate token is placeable (never operational)
                assert b in PLACEABLE_TOKENS, (
                    f"{name}: non-placeable token {b}"
                )
                assert b in ALL_TOKENS
            elif op == "move":
                # move: lane a, target rank b — target cell writable
                tgt = cell(b, a)
                assert ri.writable_mask[tgt] == 1, (
                    f"{name}: move target {tgt} not writable"
                )
            else:
                raise AssertionError(f"unknown op {op}")
    assert total_cands > 0, "expected at least one legal candidate overall"


def test_apply_every_candidate_passes_validate_transition():
    cases = _named_projected()
    tried = 0
    for name, r in cases:
        ri, cands = _candidates_for(r)
        for c in cands:
            t = apply_candidate(ri, c)
            assert t.validation_ok, (
                f"{name}: candidate {c.move} failed validation: "
                f"{t.validation_error}"
            )
            # independent check against the authority validator
            validate_transition(ri.grid81, t.grid_after, ri.structural_schema)
            tried += 1
            if tried > 300:
                return
    assert tried > 0


def test_illegal_candidate_frozen_write_rejected(one_projected):
    r = one_projected
    ri, cands = _candidates_for(r)
    # pick a frozen cell
    frozen = next(i for i in range(GRID_SIZE) if r.frozen_mask[i])
    token = next(t for t in ALL_TOKENS if t != r.grid81[frozen])
    bad = CandidateMoveV1(move=("set", frozen, token), enum_index=999)
    # typed frozen-write rejection (the specific gate, not the generic one)
    rec = C.expect_rejection(
        lambda: apply_candidate(ri, bad),
        BridgeRejectionCode.CANDIDATE_FROZEN_WRITE,
    )
    assert rec.detail.get("index") == frozen


def test_illegal_candidate_invalid_token_rejected(one_projected):
    r = one_projected
    ri, cands = _candidates_for(r)
    writable = next(i for i in range(GRID_SIZE) if r.writable_mask[i])
    # token 1 (INPUT) is operational, never placeable by a set candidate
    bad = CandidateMoveV1(move=("set", writable, int(BasisToken.INPUT)),
                          enum_index=0)
    C.expect_rejection(
        lambda: apply_candidate(ri, bad),
        BridgeRejectionCode.CANDIDATE_MALFORMED,
    )


def test_candidate_malformed_op_rejected(one_projected):
    r = one_projected
    ri, _ = _candidates_for(r)
    bad = CandidateMoveV1(move=("teleport", 0, 1), enum_index=0)
    C.expect_rejection(
        lambda: apply_candidate(ri, bad),
        BridgeRejectionCode.CANDIDATE_ILLEGAL_TOKEN,
    )


def test_candidate_out_of_range_locus_rejected(one_projected):
    r = one_projected
    ri, _ = _candidates_for(r)
    bad = CandidateMoveV1(move=("set", 81, int(BasisToken.MEMORY)),
                          enum_index=0)
    C.expect_rejection(
        lambda: apply_candidate(ri, bad),
        BridgeRejectionCode.CANDIDATE_MALFORMED,
    )


def test_projector_stronger_mask_excludes_d01_legal_move():
    """Regression (real ABI boundary): the projector freezes loci the D0.1
    degenerate schema leaves writable. A D0.1-legal ``move`` out of a
    FROZEN operational locus must be excluded from the bridge candidate set
    (it would write a frozen locus under validate_transition).

    This proves the bridge candidate domain is the D0.1 enumeration
    INTERSECTED with the projector-mask transition contract, not the D0.1
    enumeration alone.
    """
    from c2r6p0 import fixtures as F, projector
    from c2r6p0.rules import load_ruleset
    from _vendored_authority import decoder as _dec

    rs = load_ruleset()
    # A single-op fixture: one operational token at a frozen rank-0 locus.
    # The D0.1 mask leaves that lane fully writable, so D0.1 enumerates a
    # move out of it; the projector mask freezes the source -> excluded.
    for fx in F._named():
        r = projector.project(C.wrap(fx.graph, request_id=fx.name), rs)
        if r.status != ProjectionStatus.PROJECTED.value:
            continue
        ri = adapt_projection_to_refiner_input(r)
        dec = _dec()
        d01_moves = dec.legal_moves(list(r.grid81), list(ri.writable_mask))
        if not d01_moves:
            continue
        # find a D0.1 move that the bridge must EXCLUDE (writes frozen)
        excluded = []
        for m in d01_moves:
            after = dec.apply_move(list(ri.grid81), m)
            try:
                validate_transition(ri.grid81, tuple(after), ri.structural_schema)
            except Exception:
                excluded.append(m)
        if excluded:
            bridge_moves = [c.move for c in legal_candidates(ri)]
            for m in excluded:
                assert m not in bridge_moves, (
                    f"D0.1-legal move {m} that writes a frozen locus was "
                    f"offered by the bridge (fx={fx.name})"
                )
            return
    raise AssertionError(
        "no fixture exercised the projector-stronger-mask exclusion"
    )


def test_enumeration_order_is_canonical(one_projected):
    r = one_projected
    ri, cands = _candidates_for(r)
    # enum_index is the canonical enumeration position: strictly increasing
    # and contiguous from 0
    idxs = [c.enum_index for c in cands]
    assert idxs == list(range(len(cands)))
    # re-deriving gives the identical ordering (deterministic)
    ri2 = adapt_projection_to_refiner_input(r)
    cands2 = legal_candidates(ri2)
    assert [c.move for c in cands] == [c.move for c in cands2]
