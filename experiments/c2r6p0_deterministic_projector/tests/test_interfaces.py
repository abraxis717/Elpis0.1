"""Interface compilation tests (mission 17)."""
from __future__ import annotations

import pytest

from elpis_p0.semantic_ir import (
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticRelationV1,
    build_semantic_request_v1,
)

from conftest import wrap
from c2r6p0 import fixtures as FX
from c2r6p0.allocator import INTERFACE


class TestInterfaces:
    def test_interface_placed_after_bound_op(self, project):
        g = build_semantic_request_v1(
            request_id="t",
            entities=(
                SemanticEntityV1("in0", "input", "v", "str"),
                SemanticEntityV1("api", "interface", "http", ""),
            ),
            operations=(
                SemanticOperationV1(
                    "t0", "s", input_entity_ids=("in0",),
                    output_entity_ids=(),
                ),
                SemanticOperationV1("t1", "s"),
            ),
            relations=(
                SemanticRelationV1("if0", "api", "interface", "t0"),
            ),
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        assert INTERFACE in r.grid81
        b = [
            e for e in r.bindings.edge_bindings
            if e.semantic_kind == "relation"
            and e.structural_kind == "interface"
        ]
        assert b and b[0].discharged is True
        cell = b[0].payload["interface_cell"]
        assert r.grid81[cell] == INTERFACE
        assert r.frozen_mask[cell] == 1
        # direction preserved in binding payload
        assert b[0].payload["direction"] == "entity_to_operation"
        # INTERFACE_TERMINAL invariant declared and satisfied
        kinds = {i.kind for i in r.invariants}
        assert "INTERFACE_TERMINAL" in kinds
        assert r.residual_ids == ()

    def test_interface_trace_event(self, project):
        g = next(
            f.graph for f in FX.POSITIVE_FIXTURES
            if f.name == "explicit_interface"
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        events = [
            e for e in r.trace.events if e.event_type == "INTERFACE_ENCODED"
        ]
        assert len(events) == 1
        assert events[0].rule_id.startswith("R12")

    def test_ambiguous_interface_binding_rejected(self, project):
        g = next(
            f.graph for f in FX.POSITIVE_FIXTURES
            if f.name == "ambiguous_interface_binding"
        )
        r = project(wrap(g))
        assert r.status == "AMBIGUOUS_BINDING"
        assert r.error.code == "ERR.AMBIGUOUS_BINDING"

    def test_interface_induced_overflow(self, project):
        g = next(
            f.graph for f in FX.POSITIVE_FIXTURES
            if f.name == "interface_induced_overflow"
        )
        r = project(wrap(g))
        assert r.status == "DECOMPOSITION_REQUIRED"
        assert r.error.rule == "R12.INTERFACE_RANK"

    def test_interface_not_execution_authority(self, project):
        # an INTERFACE locus must not carry TRANSFORM semantics; the
        # interface entity's binding records the interface identity
        g = next(
            f.graph for f in FX.POSITIVE_FIXTURES
            if f.name == "explicit_interface"
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        ent = {e.semantic_id: e for e in r.bindings.entity_bindings}
        assert "api" in ent
        assert ent["api"].semantic_kind == "interface"
