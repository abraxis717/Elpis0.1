"""Capacity / decomposition tests (mission 27)."""
from __future__ import annotations

from elpis_p0.semantic_ir import (
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticRelationV1,
    SemanticConstraintV1,
    build_semantic_request_v1,
)

from conftest import wrap
from c2r6p0 import fixtures as FX
from c2r6p0.contracts import ProjectionStatus
from c2r6p0.rules import load_ruleset


def _independent_ops(n: int) -> object:
    ents = tuple(
        SemanticEntityV1(f"in{i}", "input", f"v{i}", "str") for i in range(n)
    )
    ops = tuple(
        SemanticOperationV1(
            f"op{i}", "s", input_entity_ids=(f"in{i}",),
        )
        for i in range(n)
    )
    return build_semantic_request_v1(
        request_id="t",
        entities=ents,
        operations=ops,
    )


class TestCapacityBoundary:
    def test_exactly_fitting(self, project):
        # MAX_SEMANTIC_LANES independent ops fits exactly
        rs = load_ruleset()
        n = rs.max_semantic_lanes
        r = project(wrap(_independent_ops(n)))
        assert r.status == "PROJECTED"
        lanes = {b.lane for b in r.bindings.op_bindings}
        assert len(lanes) == n

    def test_one_unit_overflow(self, project):
        rs = load_ruleset()
        n = rs.max_semantic_lanes + 1
        r = project(wrap(_independent_ops(n)))
        assert r.status == ProjectionStatus.DECOMPOSITION_REQUIRED.value
        assert r.error.rule == "R15.CAPACITY_LANES"
        assert r.error.code == "ERR.DECOMPOSITION_REQUIRED"
        # capacity record: authoritative well-founded measure
        assert r.capacity is not None
        assert r.capacity["lanes_required"] == n
        assert r.capacity["decomposition_measure"] >= n
        # error detail carries the same capacity block
        assert r.error.detail["capacity"]["lanes_required"] == n

    def test_rank_boundary(self, project):
        # Rank capacity is reachable only through gap-2 route edges: a
        # pure chain of RANKS ops trips the LANE check first (RANKS=9 >
        # MAX_SEMANTIC_LANES=8). A route chain schedules dist = 2n-1:
        # n=5 -> dist 9 fits (max rank 8); n=6 -> dist 11 >= RANKS ->
        # R15.CAPACITY_RANKS.
        def route_chain(n):
            return build_semantic_request_v1(
                request_id="t",
                entities=tuple(
                    SemanticEntityV1(f"e{i}", "input", f"e{i}", "str")
                    for i in range(n)
                ),
                operations=tuple(
                    SemanticOperationV1(
                        f"op{i}", "s", input_entity_ids=(f"e{i}",)
                    )
                    for i in range(n)
                ),
                relations=tuple(
                    SemanticRelationV1(
                        f"rt{i}", f"op{i}", "route", f"op{i+1}"
                    )
                    for i in range(n - 1)
                ),
            )
        r = project(wrap(route_chain(5)))
        assert r.status == "PROJECTED"
        r2 = project(wrap(route_chain(6)))
        assert r2.status == ProjectionStatus.DECOMPOSITION_REQUIRED.value
        assert r2.error.rule == "R15.CAPACITY_RANKS"

    def test_route_induced_overflow(self, project):
        g = next(f.graph for f in FX.POSITIVE_FIXTURES
                 if f.name == "route_induced_overflow")
        r = project(wrap(g))
        assert r.status == ProjectionStatus.DECOMPOSITION_REQUIRED.value
        assert r.error.rule == "R9.ROUTE_RANK"

    def test_interface_induced_overflow(self, project):
        g = next(f.graph for f in FX.POSITIVE_FIXTURES
                 if f.name == "interface_induced_overflow")
        r = project(wrap(g))
        assert r.status == ProjectionStatus.DECOMPOSITION_REQUIRED.value
        assert r.error.rule == "R12.INTERFACE_RANK"

    def test_constraint_induced_overflow(self, project):
        g = next(f.graph for f in FX.POSITIVE_FIXTURES
                 if f.name == "constraint_induced_overflow")
        r = project(wrap(g))
        assert r.status == ProjectionStatus.DECOMPOSITION_REQUIRED.value
        assert r.error.rule in (
            "R11.CONSTRAINT_RANK", "R15.CAPACITY_RANKS",
        )

    def test_no_silent_truncation(self, project):
        # overflow: the rejection trace cites the decomposition rule and
        # the result carries a full typed error (no partial grid claim)
        rs = load_ruleset()
        r = project(wrap(_independent_ops(rs.max_semantic_lanes + 3)))
        assert r.status == ProjectionStatus.DECOMPOSITION_REQUIRED.value
        ev = r.trace.events[-1]
        assert ev.event_type == "REJECTION"
        assert ev.rule_id == "R15.DECOMPOSITION_TRACE"
        # capacity record is present and consistent
        assert r.capacity is not None
        assert r.capacity["lanes_required"] > rs.max_semantic_lanes

    def test_fitted_graph_not_decomposed(self, project):
        # near-capacity named fixture still projects
        g = next(f.graph for f in FX.POSITIVE_FIXTURES
                 if f.name == "near_capacity_eight_lanes")
        r = project(wrap(g))
        assert r.status == "PROJECTED"
