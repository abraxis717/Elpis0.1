"""Dependency-graph analysis tests (mission 9)."""
from __future__ import annotations

from elpis_p0.semantic_ir import (
    P0SemanticRequestV1,
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticRelationV1,
    build_semantic_request_v1,
)

from conftest import wrap
from c2r6p0 import canonicalize
from c2r6p0 import fixtures as FX
from c2r6p0 import projector as _projector
from c2r6p0.contracts import ProjectionInputV1
from c2r6p0.graph import analyze
from c2r6p0.rules import load_ruleset


def _payload(graph) -> dict:
    ruleset = load_ruleset()
    g, err = canonicalize.canonicalize(graph, ruleset)
    assert err is None
    assert g is not None
    return g.payload


class TestSignedMalformedRejections:
    """Rejection tests against VALIDLY-DIGESTED malformed graphs.

    The named malformed fixtures carry digest="" so the authority digest
    check fires before the semantic check; the gen_malformed() corpus
    attaches a real authority digest, so these tests prove the
    CANONICALIZER's semantic checks fire (cycle rejection R5, dangling
    output binding R3) rather than the digest gate shadowing them.
    """

    def _project_malformed(self, seed: int):
        g = FX.gen_malformed(seed=seed)
        return _projector.project(
            ProjectionInputV1.from_signed(g, request_id="sg"),
            load_ruleset(),
        )

    def test_signed_cycle_rejected(self):
        # seed 4 -> kind "cycle" (dependency a->b and b->a): a pure
        # dependency cycle, which the AUTHORITY validation catches at the
        # contract level (R5.ILLEGAL_CYCLE).
        r = self._project_malformed(4)
        assert r.status == "INVALID_SEMANTIC_IR"
        assert r.error is not None
        assert r.error.rule == "R5.ILLEGAL_CYCLE"

    def test_signed_schedule_cycle_rejected(self):
        # A MIXED schedule cycle (dependency a->b plus a state_feeds
        # b->a relation) is ACYCLIC as a pure dependency graph, so the
        # authority validation passes it. Only the canonicalizer's own
        # schedule-DAG acyclicity check (canonicalize step 4) catches it.
        # This pins that check: analyze() has an independent (identical)
        # cycle detection downstream, so only a canonicalize()-level
        # assertion distinguishes the check's presence.
        g = FX._signed(P0SemanticRequestV1(
            request_id="sched_cycle",
            entities=(),
            operations=(
                SemanticOperationV1("a", "t"),
                SemanticOperationV1("b", "t"),
            ),
            dependencies=(
                SemanticDependencyV1("d1", "a", "b"),
            ),
            relations=(
                SemanticRelationV1("sf1", "b", "state_feeds", "a"),
            ),
            digest="",
        ))
        cg, err = canonicalize.canonicalize(g, load_ruleset())
        assert cg is None
        assert err is not None
        assert err.status == "STRUCTURAL_CONTRADICTION"
        assert err.rule == "R5.ILLEGAL_CYCLE"
        r = _projector.project(
            ProjectionInputV1.from_signed(g, request_id="sched_cycle"),
            load_ruleset(),
        )
        assert r.status == "STRUCTURAL_CONTRADICTION"
        assert r.error is not None
        assert r.error.rule == "R5.ILLEGAL_CYCLE"

    def test_signed_dangling_output_rejected(self):
        # seed 3 -> kind "dangling_output" (declared output, no producer)
        r = self._project_malformed(3)
        assert r.status == "INVALID_SEMANTIC_IR"
        assert r.error is not None
        assert r.error.rule == "R3.DANGLING_REFERENCE"
        assert r.error.detail["reason"] == "declared_output_without_producer"


class TestTopoAndComponents:
    def test_linear_chain_order(self):
        g = build_semantic_request_v1(
            request_id="t",
            entities=(SemanticEntityV1("e0", "input", "v", "str"),),
            operations=(
                SemanticOperationV1("a", "s", input_entity_ids=("e0",)),
                SemanticOperationV1("b", "s"),
                SemanticOperationV1("c", "s"),
            ),
            dependencies=(
                SemanticDependencyV1("d1", "a", "b"),
                SemanticDependencyV1("d2", "b", "c"),
            ),
        )
        a = analyze(_payload(g))[0]
        assert a is not None
        assert list(a.topo_order) == ["a", "b", "c"]
        assert a.dist == {"a": 0, "b": 1, "c": 2}
        assert a.longest_chain == 3
        assert a.multiple_components is False
        assert a.roots == ("a",)
        assert a.sinks == ("c",)
        assert a.multi_root_note is False
        assert a.multi_sink_note is False

    def test_diamond_is_deterministic(self):
        g = build_semantic_request_v1(
            request_id="t",
            entities=(
                SemanticEntityV1("e0", "input", "v", "str"),
                SemanticEntityV1("s1", "state", "s", "dict"),
                SemanticEntityV1("s2", "state", "s", "dict"),
            ),
            operations=(
                SemanticOperationV1(
                    "top", "s", input_entity_ids=("e0",),
                    output_entity_ids=("s1",),
                ),
                SemanticOperationV1(
                    "left", "s", input_entity_ids=("s1",),
                    output_entity_ids=("s2",),
                ),
                SemanticOperationV1(
                    "right", "s", input_entity_ids=("s1",),
                    output_entity_ids=("s2",),
                ),
                SemanticOperationV1("bot", "s", input_entity_ids=("s2",)),
            ),
            dependencies=(
                SemanticDependencyV1("d1", "top", "left"),
                SemanticDependencyV1("d2", "top", "right"),
                SemanticDependencyV1("d3", "left", "bot"),
                SemanticDependencyV1("d4", "right", "bot"),
            ),
        )
        a1 = analyze(_payload(g))[0]
        a2 = analyze(_payload(g))[0]
        assert a1.topo_order == a2.topo_order
        # lexicographic Kahn: top first, then left before right
        assert a1.topo_order[0] == "top"
        assert a1.topo_order.index("left") < a1.topo_order.index("bot")
        assert a1.topo_order.index("right") < a1.topo_order.index("bot")
        assert a1.dist["bot"] == 2

    def test_independent_components_detected(self):
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
                SemanticOperationV1("c", "s"),
            ),
            dependencies=(SemanticDependencyV1("d1", "a", "c"),),
        )
        a = analyze(_payload(g))[0]
        assert a.multiple_components is True
        assert len(a.components) == 2
        assert a.multi_root_note is True  # a and b both roots

    def test_route_edge_gaps_rank_two(self):
        g = build_semantic_request_v1(
            request_id="t",
            entities=(
                SemanticEntityV1("e0", "input", "v", "str"),
            ),
            operations=(
                SemanticOperationV1(
                    "a", "s", input_entity_ids=("e0",),
                    output_entity_ids=(),
                ),
                SemanticOperationV1("b", "s"),
            ),
            relations=(
                SemanticRelationV1("r1", "a", "route", "b"),
            ),
        )
        a = analyze(_payload(g))[0]
        assert a.dist["b"] == 2  # route edge requires gap 2

    def test_no_operations_rejected(self):
        # A zero-operation graph is rejected at canonicalization (the
        # authority requires >=1 operation); it never reaches analyze().
        from elpis_p0.semantic_ir import semantic_request_payload
        from elpis_p0.semantic_ir import _digest
        g = P0SemanticRequestV1(
            request_id="t",
            entities=(SemanticEntityV1("e0", "input", "v", "str"),),
            operations=(),
            digest=_digest(semantic_request_payload(
                P0SemanticRequestV1(
                    request_id="t",
                    entities=(SemanticEntityV1("e0", "input", "v", "str"),),
                    operations=(),
                    digest="",
                ),
            )),
        )
        out, err = canonicalize.canonicalize(g, load_ruleset())
        assert out is None
        assert err is not None
        assert err.status == "INVALID_SEMANTIC_IR"
