"""Frozen vs writable mask tests (mission 13)."""
from __future__ import annotations

import pytest

from conftest import wrap, check_invariants
from c2r6p0 import fixtures as FX


class TestMasks:
    def test_masks_disjoint_and_complete(self, project):
        # every cell is exactly one of frozen / writable / void-free
        r = project(wrap(FX.gen_valid(11)))
        assert r.status == "PROJECTED"
        check_invariants(r)  # asserts frozen & writable == 0
        assert len(r.frozen_mask) == 81
        assert len(r.writable_mask) == 81

    def test_known_semantic_facts_frozen(self, project):
        # op loci and determined auxiliary loci (route/memory/constraint/
        # interface/terminal) are all frozen. Cell addressing is
        # cell(rank, lane) = rank*9 + lane (authoritative geometry).
        r = project(wrap(FX.gen_valid(12)))
        assert r.status == "PROJECTED"
        for b in r.bindings.op_bindings:
            c = b.rank * 9 + b.lane
            assert c == b.cell
            assert r.frozen_mask[c] == 1
            assert r.writable_mask[c] == 0
        for e in r.bindings.edge_bindings:
            if not e.discharged:
                continue
            cell = (
                e.payload.get("route_cell")
                or e.payload.get("memory_cell")
                or e.payload.get("constraint_cell")
                or e.payload.get("interface_cell")
            )
            if cell is not None:
                assert r.frozen_mask[cell] == 1
                assert r.writable_mask[cell] == 0

    def test_no_frozen_guesses(self, project):
        # A frozen cell on a BOUND lane must carry a non-VOID token
        # (no frozen guess in the refiner's own search space). Unbound
        # lanes and the control lane are frozen VOID by design:
        # "nothing binds there" is a known fact, not a guess (mission 13).
        from elpis_p0.structural_residual import CONTROL_LANE
        r = project(wrap(FX.gen_valid(13)))
        assert r.status == "PROJECTED"
        bound = {b.lane for b in r.lane_bindings}
        for c in range(81):
            if not r.frozen_mask[c]:
                continue
            lane = c % 9
            if lane in bound:
                assert r.grid81[c] != 0  # VOID == 0
            elif lane == CONTROL_LANE:
                # control lane: terminal RESOLUTION locus at cell 80,
                # VOID elsewhere
                from elpis_p0.structural_residual import TERMINAL_CELL
                from elpis_p0.contracts import BasisToken
                if c == TERMINAL_CELL:
                    assert r.grid81[c] == int(BasisToken.RESOLUTION)
                else:
                    assert r.grid81[c] == 0
            else:
                # unbound lane: frozen VOID
                assert r.grid81[c] == 0

    def test_writable_cells_are_void(self, project):
        # writable cells are structurally unoccupied (VOID)
        r = project(wrap(FX.gen_valid(14)))
        assert r.status == "PROJECTED"
        for c in range(81):
            if r.writable_mask[c]:
                assert r.grid81[c] == 0

    def test_terminal_resolution_frozen(self, project):
        # the terminal RESOLUTION locus is a known structural fact
        r = project(wrap(FX.gen_valid(15)))
        assert r.status == "PROJECTED"
        assert r.frozen_mask[80] == 1
        from elpis_p0.contracts import BasisToken
        assert r.grid81[80] == int(BasisToken.RESOLUTION)
