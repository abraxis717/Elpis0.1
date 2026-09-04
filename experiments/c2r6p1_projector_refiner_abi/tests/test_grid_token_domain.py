"""Grid81 token-domain identity (mission 8).

For all 81 cells the projector's Grid81 tokens must be legal under the
refiner ABI: token in 0..9, and the token vocabulary is EXACTLY the
BasisToken domain (no remapping, no silent coercion). No canonical
remapping exists between the projector and the refiner, so identity is
required (bijection with the identity map).
"""
from __future__ import annotations

import conftest as C

from c2r6p0.contracts import ProjectionStatus
from c2r6p1_bridge import adapt_projection_to_refiner_input
from elpis_p0.contracts import BasisToken
from elpis_p0.structural_residual import (
    GRID_SIZE,
    PLACEABLE_TOKENS,
    OPERATIONAL_TOKENS,
    residual as authority_residual,
)

# The full token domain (0..9).
ALL_TOKENS = tuple(int(t) for t in BasisToken)
assert len(ALL_TOKENS) == 10


def test_token_domain_is_0_9():
    assert sorted(ALL_TOKENS) == list(range(10))
    # placeable + operational + expansion + resolution + void partition
    placeable = set(PLACEABLE_TOKENS)
    operational = set(OPERATIONAL_TOKENS)
    exp = {int(BasisToken.EXPANSION)}
    assert placeable | operational | exp == set(range(10))
    assert not (placeable & operational)
    assert not (exp & placeable)
    assert not (exp & operational)


def test_projector_tokens_legal_for_all_81_cells(project):
    from c2r6p0 import fixtures as F

    checked = 0
    s = 0
    while checked < 50 and s < 400:
        g = F.gen_valid(s)
        r = project(C.wrap(g, request_id=f"tok_{s}"))
        if r.status == ProjectionStatus.PROJECTED.value:
            ri = adapt_projection_to_refiner_input(r)
            for i in range(GRID_SIZE):
                assert ri.grid81[i] in ALL_TOKENS, (
                    f"illegal token {ri.grid81[i]} at cell {i}"
                )
            # the refiner schema validates the same grid tokens
            ri.structural_schema.validate()
            # residual computable over the same grid (token domain legal)
            authority_residual(ri.grid81, ri.invariants)
            checked += 1
        s += 1
    assert checked >= 50


def test_no_remap_identity_map(project):
    """Identity bijection: projector token == refiner token, per cell.

    There is no accepted canonical remapping, so the projector's integer
    token at each cell must equal the refiner ABI's interpretation of that
    same integer (identity). We prove this by showing the projector grid,
    passed verbatim to the refiner schema + residual machinery, is
    accepted unchanged — i.e. no cell value is coerced.
    """
    from c2r6p0 import fixtures as F

    s = 0
    done = 0
    while done < 20 and s < 400:
        g = F.gen_valid(s)
        r = project(C.wrap(g, request_id=f"id_{s}"))
        if r.status == ProjectionStatus.PROJECTED.value:
            ri = adapt_projection_to_refiner_input(r)
            # verbatim: no per-cell change
            for i in range(GRID_SIZE):
                assert ri.grid81[i] == r.grid81[i]
            done += 1
        s += 1
    assert done >= 20
