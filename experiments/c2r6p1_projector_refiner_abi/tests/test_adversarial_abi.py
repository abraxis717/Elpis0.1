"""Adversarial ABI cases (mission 19).

Every case fails CLOSED with a typed, deterministic rejection. Negative-test
hygiene: each assertion is made on the typed BridgeRejection object (via
conftest.expect_rejection), never on a bare except that could swallow our
own assertion errors.
"""
from __future__ import annotations

from dataclasses import replace

import conftest as C
from elpis_p0.structural_residual import GRID_SIZE
from c2r6p0.contracts import StructuralInvariantV1
from c2r6p1_bridge import (
    BridgeRejectionCode,
    adapt_projection_to_refiner_input,
)


def _mut(r, **fields):
    return replace(r, **fields)


# --- grid / mask surface ------------------------------------------------

def test_grid_wrong_length(one_projected):
    r = one_projected
    g = tuple(list(r.grid81)[:-1])  # 80 cells
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(_mut(r, grid81=g)),
        BridgeRejectionCode.GRID_WRONG_WIDTH,
    )


def test_illegal_basistoken(one_projected):
    r = one_projected
    g = list(r.grid81)
    g[0] = 12  # outside 0..9
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(_mut(r, grid81=tuple(g))),
        BridgeRejectionCode.GRID_TOKENS,
    )


def test_mask_wrong_length(one_projected):
    r = one_projected
    m = tuple(list(r.frozen_mask)[:-1])  # 80
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(_mut(r, frozen_mask=m)),
        BridgeRejectionCode.MASK_WRONG_WIDTH,
    )


def test_frozen_writable_overlap(one_projected):
    r = one_projected
    # force an overlap at some cell
    i = next(j for j in range(GRID_SIZE) if r.writable_mask[j])
    fm = list(r.frozen_mask)
    fm[i] = 1
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(_mut(r, frozen_mask=tuple(fm))),
        BridgeRejectionCode.FROZEN_WRITABLE_OVERLAP,
    )


def test_neither_frozen_nor_writable(one_projected):
    r = one_projected
    i = next(j for j in range(GRID_SIZE) if r.writable_mask[j])
    fm = list(r.frozen_mask)
    wm = list(r.writable_mask)
    fm[i] = 0
    wm[i] = 0
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(
            _mut(r, frozen_mask=tuple(fm), writable_mask=tuple(wm))
        ),
        BridgeRejectionCode.MASKS_DO_NOT_COVER,
    )


def test_terminal_cell_writable(one_projected):
    r = one_projected
    wm = list(r.writable_mask)
    fm = list(r.frozen_mask)
    wm[80] = 1
    fm[80] = 0
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(
            _mut(r, writable_mask=tuple(wm), frozen_mask=tuple(fm))
        ),
        BridgeRejectionCode.TERMINAL_NOT_FROZEN,
    )


# --- residual / feature surface -----------------------------------------

def test_residual_wrong_width(one_projected):
    r = one_projected
    ar = tuple(list(r.active_residual)[:-1])  # 528
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(_mut(r, active_residual=ar)),
        BridgeRejectionCode.RESIDUAL_WIDTH,
    )


def test_residual_wrong_vocab(one_projected):
    r = one_projected
    ar = list(r.active_residual)
    ar[0] = 2  # not 0/1
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(_mut(r, active_residual=tuple(ar))),
        BridgeRejectionCode.RESIDUAL_VOCABULARY,
    )


def test_stale_residual_direct(one_projected):
    r = one_projected
    # keep the grid, corrupt the stored residual ids: the adapter
    # recomputes the authoritative residual and rejects the stale one.
    bad_ids = ("RESIDUAL_INVARIANT_999_STALE",) + r.residual_ids
    rec = C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(
            _mut(r, residual_ids=tuple(bad_ids))
        ),
        (
            BridgeRejectionCode.STALE_RESIDUAL,
            BridgeRejectionCode.STALE_DECLARED,
        ),
    )
    # the rejection must have recomputed the fresh residual (evidence the
    # fresh path ran, not a width/vocab short-circuit)
    assert "stored" in rec.detail or "fresh" in rec.detail


def test_stale_residual_after_grid_mutation(one_projected):
    r = one_projected
    # mutate the grid but keep the stored residual -> the adapter must
    # recompute the authoritative residual and reject the mismatch. If
    # the flip does not change the unsatisfied invariant set, the global
    # projection-fingerprint recompute still catches the mutated state.
    g = list(r.grid81)
    i = next(j for j in range(GRID_SIZE) if r.writable_mask[j])
    g[i] = 0 if g[i] else 4  # flip a writable cell
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(_mut(r, grid81=tuple(g))),
        (
            BridgeRejectionCode.STALE_RESIDUAL,
            BridgeRejectionCode.STALE_DECLARED,
            BridgeRejectionCode.PROJECTION_FINGERPRINT_MISMATCH,
        ),
    )


# --- binding / lane / invariant surface --------------------------------

def test_binding_references_nonexistent_locus(one_projected):
    r = one_projected
    b = r.bindings
    if not b.op_bindings:
        return
    from c2r6p0.contracts import OpBinding

    op0 = b.op_bindings[0]
    bad = replace(op0, cell=999)  # out of 0..80
    newb = replace(b, op_bindings=(bad, *b.op_bindings[1:]))
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(_mut(r, bindings=newb)),
        BridgeRejectionCode.BINDING_CELL_OUT_OF_RANGE,
    )


def test_lane_binding_mismatch(one_projected):
    r = one_projected
    # drop one lane binding from the projection (schema still has it)
    if not r.lane_bindings:
        return
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(
            _mut(r, lane_bindings=r.lane_bindings[:-1])
        ),
        BridgeRejectionCode.LANE_BINDING_MISMATCH,
    )


def test_invariant_mismatch(one_projected):
    r = one_projected
    # drop one invariant from the projection (schema still has it)
    if not r.invariants:
        return
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(
            _mut(r, invariants=r.invariants[:-1])
        ),
        (
            BridgeRejectionCode.SCHEMA_INVARIANTS_MISMATCH,
            BridgeRejectionCode.STALE_RESIDUAL,
            BridgeRejectionCode.STALE_DECLARED,
        ),
    )


# --- digest / fingerprint surface ---------------------------------------

def test_modified_projection_fingerprint(one_projected):
    r = one_projected
    # corrupt the stored structural_input_fingerprint while keeping the
    # structural state: the adapter recomputes the fingerprint (a pure
    # function of the projected state) and rejects the mismatch.
    rec = C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(
            _mut(r, structural_input_fingerprint="0" * 64)
        ),
        BridgeRejectionCode.PROJECTION_FINGERPRINT_MISMATCH,
    )
    assert rec.detail.get("stored") == "0" * 64
    assert rec.detail.get("fresh") != "0" * 64


# --- non-PROJECTED statuses --------------------------------------------

def test_non_projected_status_rejected(project):
    from c2r6p0 import fixtures as F
    # find a non-PROJECTED fixture deterministically
    for s in range(200):
        g = F.gen_valid(s)
        r = project(C.wrap(g, request_id=f"adv_{s}"))
        if r.status != "PROJECTED":
            C.expect_rejection(
                lambda: adapt_projection_to_refiner_input(r),
                BridgeRejectionCode.NOT_PROJECTED,
            )
            return
    raise AssertionError("no non-PROJECTED fixture found in 200 seeds")


def test_not_a_projection_result_rejected(one_projected):
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input("not a projection"),
        BridgeRejectionCode.SCHEMA_MISMATCH,
    )
