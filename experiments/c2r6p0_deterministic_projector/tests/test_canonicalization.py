"""Canonicalization tests (mission 8): order invariance + deterministic
rejection of malformed semantic IR. No silent repair."""
from __future__ import annotations

import random

from elpis_p0.semantic_ir import (
    P0SemanticRequestV1,
    SemanticConstraintV1,
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticRelationV1,
    build_semantic_request_v1,
)

from conftest import wrap
from c2r6p0.contracts import ProjectionStatus
from c2r6p0.canonicalize import canonicalize, content_digest_of
from c2r6p0 import fixtures as FX
from c2r6p0 import projector as _projector
from c2r6p0.rules import load_ruleset


def _rich_graph(request_id: str) -> P0SemanticRequestV1:
    """A graph exercising every collection the canonicalizer orders."""
    return build_semantic_request_v1(
        request_id=request_id,
        entities=(
            SemanticEntityV1("in0", "input", "a", "str"),
            SemanticEntityV1("in1", "input", "b", "int"),
            SemanticEntityV1("st0", "state", "s", "dict"),
            SemanticEntityV1("api0", "interface", "http", ""),
            SemanticEntityV1("out0", "output", "o", "str"),
        ),
        operations=(
            SemanticOperationV1(
                "p1", "read", input_entity_ids=("in0",),
                output_entity_ids=("st0",),
            ),
            SemanticOperationV1(
                "p2", "read", input_entity_ids=("in1",),
                output_entity_ids=("st0",),
            ),
            SemanticOperationV1(
                "q1", "use", input_entity_ids=("st0",),
                output_entity_ids=("out0",),
            ),
        ),
        dependencies=(
            SemanticDependencyV1("d1", "p1", "q1"),
            SemanticDependencyV1("d2", "p2", "q1"),
        ),
        relations=(
            SemanticRelationV1("r1", "p1", "route", "q1"),
            SemanticRelationV1("r2", "api0", "interface", "q1"),
        ),
        constraints=(
            SemanticConstraintV1("c1", "bounded", "q1"),
            SemanticConstraintV1("c2", "monotone", "p1", negated=True),
        ),
        output_entity_ids=("out0",),
    )


class TestOrderInvariance:
    def test_permuted_collections_project_identically(self, project, ruleset):
        base = _rich_graph("base")
        r_base = project(wrap(base))
        assert r_base.status == "PROJECTED"

        rng = random.Random(1234)
        for trial in range(5):
            ents = list(base.entities)
            deps = list(base.dependencies)
            rels = list(base.relations)
            cons = list(base.constraints)
            ops = list(base.operations)
            rng.shuffle(ents)
            rng.shuffle(deps)
            rng.shuffle(rels)
            rng.shuffle(cons)
            rng.shuffle(ops)
            perm = build_semantic_request_v1(
                request_id=f"perm{trial}",
                entities=tuple(ents),
                operations=tuple(ops),
                dependencies=tuple(deps),
                relations=tuple(rels),
                constraints=tuple(cons),
                output_entity_ids=tuple(reversed(base.output_entity_ids)),
            )
            r = project(wrap(perm))
            assert r.status == "PROJECTED"
            # identical projection BYTES (mission 24A / 25)
            assert r.to_canonical_bytes() == r_base.to_canonical_bytes()
            assert r.structural_input_fingerprint == (
                r_base.structural_input_fingerprint
            )
            assert r.trace.to_canonical_bytes() == (
                r_base.trace.to_canonical_bytes()
            )
            # canonical content digest is input-order independent
            g1, e1 = canonicalize(base, ruleset)
            g2, e2 = canonicalize(perm, ruleset)
            assert e1 is None and e2 is None
            assert g1.content_digest == g2.content_digest

    def test_request_id_not_in_identity(self, project):
        a = _rich_graph("id-a")
        b = _rich_graph("id-b")
        ra = project(wrap(a))
        rb = project(wrap(b))
        assert ra.semantic_input_digest == rb.semantic_input_digest
        assert ra.to_canonical_bytes() == rb.to_canonical_bytes()


class TestRejections:
    def test_dangling_dependency(self, project):
        g = P0SemanticRequestV1(
            request_id="t",
            entities=(SemanticEntityV1("e0", "input", "v", "str"),),
            operations=(
                SemanticOperationV1("a", "s"),
                SemanticOperationV1("b", "s"),
            ),
            dependencies=(
                SemanticDependencyV1("d1", "a", "b"),
                SemanticDependencyV1("d2", "b", "ghost"),
            ),
            digest="",
        )
        r = project(wrap(g))
        assert r.status == ProjectionStatus.INVALID_SEMANTIC_IR.value
        assert r.error.rule == "R3.DANGLING_REFERENCE"

    def test_duplicate_incompatible_identity(self, project):
        g = P0SemanticRequestV1(
            request_id="t",
            entities=(SemanticEntityV1("e0", "input", "v", "str"),),
            operations=(
                SemanticOperationV1("a", "op1"),
                SemanticOperationV1("a", "op2"),
            ),
            digest="",
        )
        r = project(wrap(g))
        assert r.status == ProjectionStatus.INVALID_SEMANTIC_IR.value
        assert r.error.rule == "R3.DUPLICATE_IDENTITY"
        assert r.error.detail["reason"] == "duplicate_incompatible_identity"

    def test_duplicate_identical_identity(self, project):
        g = P0SemanticRequestV1(
            request_id="t",
            entities=(SemanticEntityV1("e0", "input", "v", "str"),),
            operations=(
                SemanticOperationV1("a", "op1"),
                SemanticOperationV1("a", "op1"),
            ),
            digest="",
        )
        r = project(wrap(g))
        assert r.status == ProjectionStatus.INVALID_SEMANTIC_IR.value
        assert r.error.rule == "R3.DUPLICATE_IDENTITY"

    def test_malformed_type(self, project):
        g = P0SemanticRequestV1(
            request_id="t",
            entities=(SemanticEntityV1(3, "input", "v", "str"),),  # type: ignore[arg-type]
            operations=(SemanticOperationV1("a", "s"),),
            digest="",
        )
        r = project(wrap(g))
        assert r.status == ProjectionStatus.INVALID_SEMANTIC_IR.value

    def test_dependency_cycle_rejected_not_broken(self, project):
        g = P0SemanticRequestV1(
            request_id="t",
            entities=(SemanticEntityV1("e0", "input", "v", "str"),),
            operations=(
                SemanticOperationV1("a", "s"),
                SemanticOperationV1("b", "s"),
            ),
            dependencies=(
                SemanticDependencyV1("d1", "a", "b"),
                SemanticDependencyV1("d2", "b", "a"),
            ),
            digest="",
        )
        r = project(wrap(g))
        assert r.status == ProjectionStatus.INVALID_SEMANTIC_IR.value
        assert r.error.rule == "R5.ILLEGAL_CYCLE"
        assert r.error.detail["reason"] == "dependency_cycle"

    def test_schedule_cycle(self, project):
        # A precedes B, B state_feeds A: a cycle across relation kinds.
        g = build_semantic_request_v1(
            request_id="t",
            entities=(SemanticEntityV1("s0", "state", "v", "dict"),),
            operations=(
                SemanticOperationV1(
                    "a", "s", input_entity_ids=("s0",),
                    output_entity_ids=("s0",),
                ),
                SemanticOperationV1("b", "s"),
            ),
            dependencies=(SemanticDependencyV1("d1", "a", "b"),),
            relations=(
                SemanticRelationV1("r1", "b", "state_feeds", "a"),
            ),
        )
        r = project(wrap(g))
        assert r.status == ProjectionStatus.STRUCTURAL_CONTRADICTION.value
        assert r.error.rule == "R5.ILLEGAL_CYCLE"
        assert r.error.detail["reason"] == "schedule_dag_cycle"

    def test_no_silent_repair(self, project):
        # dangling must not be repaired into a projection
        g = P0SemanticRequestV1(
            request_id="t",
            entities=(SemanticEntityV1("e0", "input", "v", "str"),),
            operations=(
                SemanticOperationV1("a", "s"),
                SemanticOperationV1("b", "s"),
            ),
            relations=(
                SemanticRelationV1("r1", "a", "route", "nope"),
            ),
            digest="",
        )
        r = project(wrap(g))
        assert r.status != ProjectionStatus.PROJECTED.value


class TestInputDigestContentSensitivity:
    """The semantic input digest must bind the graph CONTENT.

    Relabeling a request is identity-neutral (mission 5), but changing
    any material semantic content must change the digest — a constant
    or request-only digest would collapse distinct graphs.
    """

    def test_distinct_graphs_distinct_digests(self):
        d1 = content_digest_of(FX.gen_valid(seed=700))
        d2 = content_digest_of(FX.gen_valid(seed=701))
        assert len(d1) == 64 and len(d2) == 64
        assert d1 != d2, "digest must be sensitive to graph content"

    def test_result_digests_sensitive_to_content(self, project):
        rules = load_ruleset()
        r1 = _projector.project(
            wrap(FX.gen_valid(seed=710), request_id="c1"), rules
        )
        r2 = _projector.project(
            wrap(FX.gen_valid(seed=711), request_id="c1"), rules
        )
        assert r1.status == r2.status == ProjectionStatus.PROJECTED.value
        assert r1.semantic_input_digest != r2.semantic_input_digest
        assert r1.projection_digest != r2.projection_digest
