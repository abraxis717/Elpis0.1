"""Allocator / lane-assignment tests (mission 10)."""
from __future__ import annotations

import pytest

from elpis_p0.semantic_ir import (
    SemanticEntityV1,
    SemanticOperationV1,
    build_semantic_request_v1,
)

from conftest import wrap, check_invariants
from c2r6p0.contracts import ProjectionStatus
from c2r6p0 import fixtures as FX


class TestLaneAllocation:
    def test_deterministic_under_permutation(self, project):
        # two semantically-equal graphs (permuted collections) -> identical
        base = FX.gen_valid(101)
        r1 = project(wrap(base))
        g2 = build_semantic_request_v1(
            request_id="other",
            entities=tuple(reversed(base.entities)),
            operations=tuple(reversed(base.operations)),
            dependencies=tuple(reversed(base.dependencies)),
            relations=tuple(reversed(base.relations)),
            constraints=tuple(reversed(base.constraints)),
            output_entity_ids=tuple(reversed(base.output_entity_ids)),
        )
        r2 = project(wrap(g2))
        assert r1.status == r2.status == "PROJECTED"
        assert r1.grid81 == r2.grid81
        assert r1.to_canonical_bytes() == r2.to_canonical_bytes()

    def test_no_lane_collision(self, project):
        # 8 independent ops -> 8 distinct lanes
        name = "near_capacity_eight_lanes"
        g = next(f.graph for f in FX.POSITIVE_FIXTURES if f.name == name)
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        lanes = {b.lane for b in r.bindings.op_bindings}
        assert len(lanes) == 8
        check_invariants(r)

    def test_capacity_lanes_exceed(self, project):
        name = "lane_overflow_nine"
        g = next(f.graph for f in FX.POSITIVE_FIXTURES if f.name == name)
        r = project(wrap(g))
        assert r.status == ProjectionStatus.DECOMPOSITION_REQUIRED.value
        assert r.error.rule == "R15.CAPACITY_LANES"
        assert r.capacity is not None

    def test_rank_overflow(self, project):
        # rank capacity is reached via gap-2 route edges (a pure chain
        # trips the LANE check first: 9 ops > 8 lanes)
        name = "rank_overflow_route6"
        g = next(f.graph for f in FX.POSITIVE_FIXTURES if f.name == name)
        r = project(wrap(g))
        assert r.status == ProjectionStatus.DECOMPOSITION_REQUIRED.value
        assert r.error.rule == "R15.CAPACITY_RANKS"
        # boundary: one route edge fewer still projects
        g5 = next(f.graph for f in FX.POSITIVE_FIXTURES
                  if f.name == "rank_boundary_route5")
        r5 = project(wrap(g5))
        assert r5.status == "PROJECTED"

    def test_lane_assignment_trace(self, project):
        r = project(wrap(FX.gen_valid(7)))
        if r.status != "PROJECTED":
            pytest.skip("decomposed")
        lane_events = [
            e for e in r.trace.events if e.event_type == "LANE_ASSIGNED"
        ]
        assert len(lane_events) == len(r.bindings.op_bindings)

    def test_independent_branches_get_distinct_lanes(self, project):
        # two roots, no dependency between them
        g = build_semantic_request_v1(
            request_id="t",
            entities=(
                SemanticEntityV1("e0", "input", "v", "str"),
                SemanticEntityV1("e1", "input", "v", "str"),
            ),
            operations=(
                SemanticOperationV1(
                    "a", "s", input_entity_ids=("e0",),
                    output_entity_ids=(),
                ),
                SemanticOperationV1(
                    "b", "s", input_entity_ids=("e1",),
                    output_entity_ids=(),
                ),
            ),
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        lanes = {b.lane for b in r.bindings.op_bindings}
        assert len(lanes) == 2
