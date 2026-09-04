"""Authority non-widening (mission 5).

For every cell: refiner_writable[i] <= projector_writable[i]. The adapter
may never convert frozen -> writable. Proof:
  * the refiner schema's writable mask == the projector's (never broader);
  * every projector-frozen locus stays frozen under validate_transition
    (a write to a frozen locus is rejected, for EVERY BasisToken).
"""
from __future__ import annotations

from dataclasses import replace

import conftest as C

from c2r6p0.contracts import ProjectionStatus
from c2r6p1_bridge import (
    BridgeRejectionCode,
    BridgeRejectionError,
    adapt_projection_to_refiner_input,
    apply_candidate,
    legal_candidates,
)
from elpis_p0.contracts import BasisToken
from elpis_p0.structural_residual import (
    GRID_SIZE,
    TERMINAL_CELL,
    validate_transition,
)

ALL_TOKENS = tuple(int(t) for t in BasisToken)


def test_refiner_mask_never_wider_than_projector(project):
    from c2r6p0 import fixtures as F

    checked = 0
    s = 0
    while checked < 50 and s < 400:
        g = F.gen_valid(s)
        r = project(C.wrap(g, request_id=f"nw_{s}"))
        if r.status == ProjectionStatus.PROJECTED.value:
            ri = adapt_projection_to_refiner_input(r)
            for i in range(GRID_SIZE):
                # refiner writable <= projector writable (equality by
                # construction, but never wider)
                assert ri.structural_schema.writable_mask[i] <= r.writable_mask[i]
                # projector frozen => refiner frozen
                if r.frozen_mask[i]:
                    assert ri.structural_schema.writable_mask[i] == 0
            checked += 1
        s += 1
    assert checked >= 50


def test_projector_frozen_locus_immutable_under_validate_transition(
    one_projected,
):
    """Mutation test: attempt EVERY BasisToken write to representative
    frozen cells -> rejection under validate_transition."""
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    frozen_cells = [i for i in range(GRID_SIZE) if r.frozen_mask[i]]
    assert frozen_cells, "need at least one frozen locus"
    # representative frozen loci: every frozen cell, capped for cost
    reps = frozen_cells[:40] + [TERMINAL_CELL]
    reps = sorted(set(reps))
    tried = 0
    for i in reps:
        assert r.frozen_mask[i] == 1
        for token in ALL_TOKENS:
            if token == r.grid81[i]:
                continue  # a no-op write is trivially allowed
            after = list(r.grid81)
            after[i] = token
            try:
                validate_transition(
                    r.grid81, tuple(after), ri.structural_schema
                )
                raise AssertionError(
                    f"frozen locus {i} accepted token {token}"
                )
            except AssertionError:
                raise
            except Exception:
                tried += 1
    assert tried > 0


def test_terminal_cell_frozen(one_projected):
    r = one_projected
    ri = adapt_projection_to_refiner_input(r)
    assert r.frozen_mask[TERMINAL_CELL] == 1
    assert ri.structural_schema.writable_mask[TERMINAL_CELL] == 0


def test_adapter_rejects_frozen_writable_overlap(one_projected):
    r = one_projected
    # force an overlap: writable where frozen
    fm = list(r.frozen_mask)
    wm = list(r.writable_mask)
    i = next(i for i in range(GRID_SIZE) if fm[i] == 1)
    wm[i] = 1
    bad = replace(r, frozen_mask=tuple(fm), writable_mask=tuple(wm))
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(bad),
        BridgeRejectionCode.FROZEN_WRITABLE_OVERLAP,
    )


def test_adapter_rejects_masks_not_covering(one_projected):
    r = one_projected
    fm = list(r.frozen_mask)
    wm = list(r.writable_mask)
    i = next(i for i in range(GRID_SIZE) if fm[i] == 1)
    fm[i] = 0
    wm[i] = 0  # neither
    bad = replace(r, frozen_mask=tuple(fm), writable_mask=tuple(wm))
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(bad),
        BridgeRejectionCode.MASKS_DO_NOT_COVER,
    )


def test_adapter_rejects_mask_wrong_length(one_projected):
    r = one_projected
    bad = replace(r, writable_mask=r.writable_mask[:80])
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(bad),
        BridgeRejectionCode.MASK_WRONG_WIDTH,
    )


def test_adapter_rejects_grid_wrong_width(one_projected):
    r = one_projected
    bad = replace(r, grid81=r.grid81[:80])
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(bad),
        BridgeRejectionCode.GRID_WRONG_WIDTH,
    )


def test_adapter_rejects_terminal_writable(one_projected):
    r = one_projected
    wm = list(r.writable_mask)
    fm = list(r.frozen_mask)
    wm[TERMINAL_CELL] = 1
    fm[TERMINAL_CELL] = 0
    bad = replace(r, writable_mask=tuple(wm), frozen_mask=tuple(fm))
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(bad),
        BridgeRejectionCode.TERMINAL_NOT_FROZEN,
    )


def test_adapter_rejects_no_schema(one_projected):
    r = one_projected
    bad = replace(r, structural_schema=None)
    C.expect_rejection(
        lambda: adapt_projection_to_refiner_input(bad),
        BridgeRejectionCode.NO_AUTHORITY_SCHEMA,
    )
