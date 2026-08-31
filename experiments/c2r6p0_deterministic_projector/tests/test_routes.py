"""Route compilation tests (mission 14)."""
from __future__ import annotations

import pytest

from elpis_p0.contracts import BasisToken
from elpis_p0.semantic_ir import (
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticRelationV1,
    build_semantic_request_v1,
)

from conftest import wrap
from c2r6p0.allocator import ROUTE
from c2r6p0 import fixtures as FX
from c2r6p0.contracts import ProjectionStatus


def _route_graph(request_id="t"):
    return build_semantic_request_v1(
        request_id=request_id,
        entities=(
            SemanticEntityV1("in0", "input", "v", "str"),
            SemanticEntityV1("st0", "state", "v", "dict"),
        ),
        operations=(
            SemanticOperationV1(
                "src", "emit", input_entity_ids=("in0",),
                output_entity_ids=("st0",),
            ),
            SemanticOperationV1(
                "mid", "step", input_entity_ids=("st0",),
                output_entity_ids=("st0",),
            ),
            SemanticOperationV1(
                "dst", "consume", input_entity_ids=("st0",),
                output_entity_ids=(),
            ),
        ),
        dependencies=(
            SemanticDependencyV1("d1", "src", "mid"),
            SemanticDependencyV1("d2", "mid", "dst"),
        ),
        relations=(
            SemanticRelationV1("rt1", "src", "route", "dst"),
        ),
    )


class TestRoutes:
    def test_route_placed_between_ranks(self, project):
        g = _route_graph()
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        # a ROUTE token exists in the grid
        assert ROUTE in r.grid81
        # route edge binding discharged with a real locus
        rel = [
            e for e in r.bindings.edge_bindings
            if e.semantic_kind == "relation" and e.structural_kind == "route"
        ]
        assert rel, "no route edge binding"
        assert rel[0].discharged is True
        cell = rel[0].payload["route_cell"]
        assert 0 <= cell < 81
        assert r.grid81[cell] == ROUTE
        # the route locus is frozen (a determined structural fact)
        assert r.frozen_mask[cell] == 1

    def test_route_in_trace(self, project):
        g = _route_graph()
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        events = [
            e for e in r.trace.events if e.event_type == "ROUTE_INSERTED"
        ]
        assert len(events) == 1
        assert events[0].rule_id.startswith("R9")

    def test_route_invariant_declared(self, project):
        g = _route_graph()
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        kinds = {i.kind for i in r.invariants}
        assert "CROSS_LANE_ROUTE" in kinds
        # residual empty: route invariant satisfied
        assert r.residual_ids == ()

    def test_route_induced_overflow(self, project):
        g = next(
            f.graph for f in FX.POSITIVE_FIXTURES
            if f.name == "route_induced_overflow"
        )
        r = project(wrap(g))
        assert r.status == ProjectionStatus.DECOMPOSITION_REQUIRED.value
        assert r.error.rule == "R9.ROUTE_RANK"
