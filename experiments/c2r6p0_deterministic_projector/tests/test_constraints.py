"""Constraint compilation tests (mission 16)."""
from __future__ import annotations

import pytest

from elpis_p0.semantic_ir import (
    SemanticConstraintV1,
    SemanticEntityV1,
    SemanticOperationV1,
    build_semantic_request_v1,
)

from conftest import wrap
from c2r6p0 import fixtures as FX
from c2r6p0.allocator import CONSTRAINT


class TestConstraints:
    def test_hard_constraint_placed_after_owner(self, project):
        g = build_semantic_request_v1(
            request_id="t",
            entities=(
                SemanticEntityV1("in0", "input", "v", "str"),
            ),
            operations=(
                SemanticOperationV1(
                    "t0", "s", input_entity_ids=("in0",),
                    output_entity_ids=(),
                ),
                SemanticOperationV1("t1", "s"),
            ),
            dependencies=(
                (lambda: __import__("elpis_p0.semantic_ir", fromlist=["SemanticDependencyV1"]).SemanticDependencyV1("d1", "t0", "t1"))(),
            ),
            constraints=(
                SemanticConstraintV1("hc0", "bounded", "t0", hard=True),
            ),
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        assert CONSTRAINT in r.grid81
        b = [
            e for e in r.bindings.edge_bindings
            if e.semantic_kind == "constraint"
        ]
        assert b and b[0].discharged is True
        cell = b[0].payload["constraint_cell"]
        assert r.grid81[cell] == CONSTRAINT
        assert r.frozen_mask[cell] == 1
        kinds = {i.kind for i in r.invariants}
        assert "CONSTRAINT_AFTER" in kinds
        assert r.residual_ids == ()

    def test_constraint_trace_event(self, project):
        g = build_semantic_request_v1(
            request_id="t",
            entities=(
                SemanticEntityV1("in0", "input", "v", "str"),
            ),
            operations=(
                SemanticOperationV1(
                    "t0", "s", input_entity_ids=("in0",),
                    output_entity_ids=(),
                ),
            ),
            constraints=(
                SemanticConstraintV1("hc0", "bounded", "t0", hard=True),
            ),
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        events = [
            e for e in r.trace.events if e.event_type == "CONSTRAINT_ENCODED"
        ]
        assert len(events) == 1
        assert events[0].rule_id.startswith("R11")

    def test_contradictory_constraints_rejected(self, project):
        g = next(
            f.graph for f in FX.POSITIVE_FIXTURES
            if f.name == "contradictory_constraint"
        )
        r = project(wrap(g))
        assert r.status == "STRUCTURAL_CONTRADICTION"
        assert r.error.code == "ERR.STRUCTURAL_CONTRADICTION"
        assert r.error.rule is not None
        assert isinstance(r.error.detail, dict)

    def test_constraint_absent_no_fact(self, project):
        g = build_semantic_request_v1(
            request_id="t",
            entities=(SemanticEntityV1("in0", "input", "v", "str"),),
            operations=(
                SemanticOperationV1(
                    "t0", "s", input_entity_ids=("in0",),
                    output_entity_ids=(),
                ),
            ),
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        assert CONSTRAINT not in r.grid81


class TestArityComparators:
    """Explicit comparator semantics (R4.ARITY_VIOLATION).

    The named arity fixture only exercises 'eq'; 'gt' and 'lt' must be
    honored with the correct inequality direction.
    """

    def _graph(self, comparator: str, value: int):
        from elpis_p0.semantic_ir import SemanticQuantityV1
        return build_semantic_request_v1(
            request_id="t",
            entities=(SemanticEntityV1("in0", "input", "v", "str"),),
            operations=(SemanticOperationV1(
                "a", "s", input_entity_ids=("in0",), output_entity_ids=(),
            ),),
            quantities=(
                SemanticQuantityV1(
                    "q", "a", "input_arity", comparator, value,
                ),
            ),
        )

    def test_gt_violation_rejected(self, project):
        # declared input arity is 1; 1 > 2 is false
        r = project(wrap(self._graph("gt", 2)))
        assert r.status == "STRUCTURAL_CONTRADICTION"
        assert r.error.rule == "R4.ARITY_VIOLATION"

    def test_gt_satisfied_projects(self, project):
        # declared input arity is 1; 1 > 0 is true
        r = project(wrap(self._graph("gt", 0)))
        assert r.status == "PROJECTED"

    def test_lt_violation_rejected(self, project):
        # declared input arity is 1; 1 < 0 is false
        r = project(wrap(self._graph("lt", 0)))
        assert r.status == "STRUCTURAL_CONTRADICTION"
        assert r.error.rule == "R4.ARITY_VIOLATION"

    def test_lt_satisfied_projects(self, project):
        # declared input arity is 1; 1 < 2 is true
        r = project(wrap(self._graph("lt", 2)))
        assert r.status == "PROJECTED"
