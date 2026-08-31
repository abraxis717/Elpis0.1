"""ProjectionTraceV1 tests (mission 7)."""
from __future__ import annotations

from conftest import wrap
from c2r6p0 import fixtures as FX
from c2r6p0.rules import RULE_IDS


class TestTrace:
    def test_events_cite_known_rules(self, project):
        r = project(wrap(FX.gen_valid(31)))
        assert r.status == "PROJECTED"
        assert r.trace.schema == "c2r6p0.projection-trace.v1"
        for e in r.trace.events:
            assert e.rule_id in RULE_IDS, e.rule_id

    def test_sequence_numbers_contiguous(self, project):
        r = project(wrap(FX.gen_valid(32)))
        assert r.status == "PROJECTED"
        seqs = [e.seq for e in r.trace.events]
        assert seqs == list(range(len(seqs)))

    def test_digest_recompute_matches(self, project):
        # recompute the trace digest from its own events: the digest must
        # be a pure function of the canonical event list + digests
        from c2r6p0.contracts import canonical_bytes, sha256_hex
        r = project(wrap(FX.gen_valid(33)))
        r2 = project(wrap(FX.gen_valid(33)))
        d = sha256_hex(canonical_bytes({
            "schema": "c2r6p0.projection-trace.v1",
            "semantic_input_digest": r.semantic_input_digest,
            "rule_set_digest": r.rule_set_digest,
            "events": [e.to_dict() for e in r.trace.events],
        }))
        assert d == r2.trace.trace_digest

    def test_trace_bytes_deterministic(self, project):
        r1 = project(wrap(FX.gen_valid(34)))
        r2 = project(wrap(FX.gen_valid(34)))
        assert r1.trace.trace_digest == r2.trace.trace_digest
        assert r1.to_canonical_bytes() == r2.to_canonical_bytes()

    def test_route_memory_constraint_interface_events_present(self, project):
        # a rich graph exercises the placement event vocabulary
        from elpis_p0.semantic_ir import (
            SemanticConstraintV1,
            SemanticDependencyV1,
            SemanticEntityV1,
            SemanticOperationV1,
            SemanticRelationV1,
            build_semantic_request_v1,
        )
        g = build_semantic_request_v1(
            request_id="t",
            entities=(
                SemanticEntityV1("in0", "input", "v", "str"),
                SemanticEntityV1("st0", "state", "v", "dict"),
                SemanticEntityV1("api", "interface", "http", ""),
            ),
            operations=(
                SemanticOperationV1(
                    "a", "s", input_entity_ids=("in0",),
                    output_entity_ids=("st0",),
                ),
                SemanticOperationV1(
                    "b", "s", input_entity_ids=("st0",),
                    output_entity_ids=("st0",),
                ),
                SemanticOperationV1(
                    "c", "s", input_entity_ids=("st0",),
                    output_entity_ids=(),
                ),
            ),
            dependencies=(
                SemanticDependencyV1("d1", "a", "b"),
                SemanticDependencyV1("d2", "b", "c"),
            ),
            relations=(
                SemanticRelationV1("rt1", "a", "route", "c"),
                SemanticRelationV1("sf1", "a", "state_feeds", "c"),
                SemanticRelationV1("if1", "api", "interface", "b"),
            ),
            constraints=(
                SemanticConstraintV1("hc1", "bounded", "a", hard=True),
            ),
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        types = {e.event_type for e in r.trace.events}
        for t in (
            "SEMANTIC_NODE_ACCEPTED",
            "LANE_ASSIGNED",
            "ROUTE_INSERTED",
            "MEMORY_RELATION_ENCODED",
            "CONSTRAINT_ENCODED",
            "INTERFACE_ENCODED",
            "FROZEN_LOCUS_DECLARED",
        ):
            assert t in types, t

    def test_rejection_trace_is_typed(self, project):
        g = next(f.graph for f in FX.POSITIVE_FIXTURES
                 if f.name == "dangling_dependency")
        r = project(wrap(g))
        assert r.status != "PROJECTED"
        ev = r.trace.events[-1]
        assert ev.event_type == "REJECTION"
        assert ev.detail["status"] == r.status
        assert ev.detail["code"] == r.error.code
