"""Memory / state-relationship tests (mission 15)."""
from __future__ import annotations

from elpis_p0.semantic_ir import (
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticRelationV1,
    build_semantic_request_v1,
)

from conftest import wrap
from c2r6p0 import fixtures as FX
from c2r6p0.allocator import MEMORY


class TestMemory:
    def test_state_feeds_places_memory(self, project):
        g = build_semantic_request_v1(
            request_id="t",
            entities=(
                SemanticEntityV1("in0", "input", "v", "str"),
                SemanticEntityV1("st0", "state", "v", "dict"),
            ),
            operations=(
                SemanticOperationV1(
                    "prod", "emit", input_entity_ids=("in0",),
                    output_entity_ids=("st0",),
                ),
                SemanticOperationV1(
                    "gap", "step", input_entity_ids=("st0",),
                    output_entity_ids=("st0",),
                ),
                SemanticOperationV1(
                    "cons", "use", input_entity_ids=("st0",),
                    output_entity_ids=(),
                ),
            ),
            dependencies=(
                SemanticDependencyV1("d1", "prod", "gap"),
                SemanticDependencyV1("d2", "gap", "cons"),
            ),
            relations=(
                SemanticRelationV1("sf1", "prod", "state_feeds", "cons"),
            ),
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        # MEMORY token present
        assert MEMORY in r.grid81
        mem = [
            e for e in r.bindings.edge_bindings
            if e.semantic_kind == "relation"
            and e.structural_kind == "state_feeds"
        ]
        assert mem and mem[0].discharged is True
        cell = mem[0].payload["memory_cell"]
        assert r.grid81[cell] == MEMORY
        assert r.frozen_mask[cell] == 1
        # MEMORY_SPAN invariant declared and satisfied
        kinds = {i.kind for i in r.invariants}
        assert "MEMORY_SPAN" in kinds
        assert r.residual_ids == ()

    def test_no_memory_fact_when_absent(self, project):
        # plain chain without state_feeds: no MEMORY locus fabricated
        g = build_semantic_request_v1(
            request_id="t",
            entities=(SemanticEntityV1("in0", "input", "v", "str"),),
            operations=(
                SemanticOperationV1(
                    "a", "s", input_entity_ids=("in0",),
                    output_entity_ids=(),
                ),
                SemanticOperationV1("b", "s"),
            ),
            dependencies=(
                SemanticDependencyV1("d1", "a", "b"),
            ),
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        assert MEMORY not in r.grid81
        kinds = {i.kind for i in r.invariants}
        assert "MEMORY_SPAN" not in kinds

    def test_memory_trace_event(self, project):
        g = next(
            f.graph for f in FX.POSITIVE_FIXTURES
            if f.name == "explicit_memory_state"
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        events = [
            e for e in r.trace.events
            if e.event_type == "MEMORY_RELATION_ENCODED"
        ]
        assert len(events) == 1
        assert events[0].rule_id.startswith("R10")
