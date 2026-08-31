"""Metamorphic tests (mission 24)."""
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
from c2r6p0 import fixtures as FX


def _rich_graph(request_id: str = "t") -> object:
    return build_semantic_request_v1(
        request_id=request_id,
        entities=(
            SemanticEntityV1("in0", "input", "v", "str"),
            SemanticEntityV1("st0", "state", "v", "dict"),
            SemanticEntityV1("api", "interface", "http", ""),
            SemanticEntityV1("out0", "output", "o", "str"),
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
                output_entity_ids=("out0",),
            ),
        ),
        dependencies=(
            SemanticDependencyV1("d1", "a", "b"),
            SemanticDependencyV1("d2", "b", "c"),
        ),
        relations=(
            SemanticRelationV1("rt1", "a", "route", "c"),
            SemanticRelationV1("if1", "api", "interface", "b"),
        ),
        constraints=(
            SemanticConstraintV1("hc1", "bounded", "a", hard=True),
        ),
        output_entity_ids=("out0",),
    )


class TestInputOrderInvariance:
    """A: permuting non-semantic list/dict insertion order -> identical
    projection bytes, identical trace, identical fingerprint."""

    def test_permute_collections(self, project):
        base = _rich_graph()
        r1 = project(wrap(base))
        assert r1.status == "PROJECTED"
        g2 = build_semantic_request_v1(
            request_id="t",
            entities=tuple(reversed(base.entities)),
            operations=tuple(reversed(base.operations)),
            dependencies=tuple(reversed(base.dependencies)),
            relations=tuple(reversed(base.relations)),
            constraints=tuple(reversed(base.constraints)),
            output_entity_ids=tuple(reversed(base.output_entity_ids)),
        )
        r2 = project(wrap(g2))
        assert r2.status == "PROJECTED"
        assert r1.to_canonical_bytes() == r2.to_canonical_bytes()
        assert r1.trace.trace_digest == r2.trace.trace_digest
        assert r1.structural_input_fingerprint == r2.structural_input_fingerprint
        assert r1.semantic_input_digest == r2.semantic_input_digest

    def test_generated_corpus_order_invariance(self, project):
        rng = random.Random(4242)
        for seed in (51, 52, 53):
            base = FX.gen_valid(seed)
            r1 = project(wrap(base))
            if r1.status != "PROJECTED":
                continue
            # permute every collection with a seeded rng
            p_ents = list(base.entities); rng.shuffle(p_ents)
            p_ops = list(base.operations); rng.shuffle(p_ops)
            p_deps = list(base.dependencies); rng.shuffle(p_deps)
            p_rels = list(base.relations); rng.shuffle(p_rels)
            p_cons = list(base.constraints); rng.shuffle(p_cons)
            p_out = list(base.output_entity_ids); rng.shuffle(p_out)
            g2 = build_semantic_request_v1(
                request_id="x",
                entities=tuple(p_ents),
                operations=tuple(p_ops),
                dependencies=tuple(p_deps),
                relations=tuple(p_rels),
                constraints=tuple(p_cons),
                output_entity_ids=tuple(p_out),
            )
            r2 = project(wrap(g2))
            assert r2.status == "PROJECTED"
            assert r1.to_canonical_bytes() == r2.to_canonical_bytes()


class TestDebugIdInsensitivity:
    """B: changing irrelevant request/debug identity -> identical
    projection (canonical identity excludes request_id)."""

    def test_request_id_neutral(self, project):
        g1 = _rich_graph(request_id="req-alpha")
        g2 = _rich_graph(request_id="req-beta")
        r1 = project(wrap(g1))
        r2 = project(wrap(g2))
        assert r1.status == r2.status == "PROJECTED"
        assert r1.to_canonical_bytes() == r2.to_canonical_bytes()
        assert r1.semantic_input_digest == r2.semantic_input_digest

    def test_wrapper_debug_metadata_neutral(self, project):
        g = _rich_graph()
        r1 = project(wrap(g))
        r2 = project(wrap(g, debug_tag="totally-irrelevant-debug-id"))
        assert r1.to_canonical_bytes() == r2.to_canonical_bytes()


class TestSemanticIdSensitivity:
    """C: changing a material bound semantic identity -> binding identity
    and structural fingerprint change where semantically relevant."""

    def test_entity_identity_change_changes_fingerprint(self, project):
        # change the semantic identity (the `identity` field) of an entity
        # that is bound in the sidecar: topology may stay equal, but the
        # binding sidecar and fingerprint must change.
        base = _rich_graph()
        ents = list(base.entities)
        ents[0] = SemanticEntityV1("in0", "input", "CHANGED", "str")
        g2 = build_semantic_request_v1(
            request_id="t",
            entities=tuple(ents),
            operations=base.operations,
            dependencies=base.dependencies,
            relations=base.relations,
            constraints=base.constraints,
            output_entity_ids=base.output_entity_ids,
        )
        r1 = project(wrap(base))
        r2 = project(wrap(g2))
        assert r1.status == r2.status == "PROJECTED"
        # topology identical (same graph shape)
        assert r1.grid81 == r2.grid81
        # but the semantic input digest and fingerprint differ
        assert r1.semantic_input_digest != r2.semantic_input_digest
        assert r1.structural_input_fingerprint != r2.structural_input_fingerprint

    def test_operation_rename_changes_topology_identity(self, project):
        # renaming an operation is a material semantic identity change:
        # the lane binding identity changes and the fingerprint changes.
        base = _rich_graph()
        ops = list(base.operations)
        # rename op "a" -> "a2" and its dependency reference
        ops[0] = SemanticOperationV1(
            "a2", "s", input_entity_ids=("in0",),
            output_entity_ids=("st0",),
        )
        deps = [
            SemanticDependencyV1(
                d.dependency_id,
                "a2" if d.predecessor_operation_id == "a"
                else d.predecessor_operation_id,
                d.successor_operation_id,
            )
            for d in base.dependencies
        ]
        # route relation also references "a"
        rels = [
            SemanticRelationV1(
                r.relation_id,
                "a2" if r.source_id == "a" else r.source_id,
                r.predicate,
                r.target_id,
            )
            for r in base.relations
        ]
        cons = [
            SemanticConstraintV1(
                "hc1", "bounded",
                "a2" if c.subject_id == "a" else c.subject_id,
                hard=True,
            )
            for c in base.constraints
        ]
        g2 = build_semantic_request_v1(
            request_id="t",
            entities=base.entities,
            operations=tuple(ops),
            dependencies=tuple(deps),
            relations=tuple(rels),
            constraints=tuple(cons),
            output_entity_ids=base.output_entity_ids,
        )
        r1 = project(wrap(base))
        r2 = project(wrap(g2))
        assert r1.status == r2.status == "PROJECTED"
        ids1 = {b.semantic_id for b in r1.bindings.op_bindings}
        ids2 = {b.semantic_id for b in r2.bindings.op_bindings}
        assert ids1 != ids2
        assert r1.structural_input_fingerprint != r2.structural_input_fingerprint


class TestDependencySensitivity:
    """D: changing A->B to A->C changes topology/route/trace appropriately."""

    def test_dependency_target_change(self, project):
        base = _rich_graph()
        # redirect d2: b->c becomes a->c (a skips b)
        deps = tuple(
            SemanticDependencyV1("d2", "a", "c") if d.dependency_id == "d2"
            else d
            for d in base.dependencies
        )
        g2 = build_semantic_request_v1(
            request_id="t",
            entities=base.entities,
            operations=base.operations,
            dependencies=deps,
            relations=base.relations,
            constraints=base.constraints,
            output_entity_ids=base.output_entity_ids,
        )
        r1 = project(wrap(base))
        r2 = project(wrap(g2))
        assert r1.status == "PROJECTED"
        # the trace must differ (a different dependency accepted)
        assert r1.trace.trace_digest != r2.trace.trace_digest


class TestTypeSensitivity:
    """E: changing an explicit material type -> binding/fingerprint change
    or deterministic rejection."""

    def test_entity_datatype_change(self, project):
        base = _rich_graph()
        ents = list(base.entities)
        ents[0] = SemanticEntityV1("in0", "input", "v", "CHANGED_TYPE")
        g2 = build_semantic_request_v1(
            request_id="t",
            entities=tuple(ents),
            operations=base.operations,
            dependencies=base.dependencies,
            relations=base.relations,
            constraints=base.constraints,
            output_entity_ids=base.output_entity_ids,
        )
        r1 = project(wrap(base))
        r2 = project(wrap(g2))
        assert r1.status == "PROJECTED"
        # fingerprint changes (type is material in the sidecar)
        assert r1.structural_input_fingerprint != r2.structural_input_fingerprint


class TestConstraintSensitivity:
    """F: adding/removing an explicit constraint changes declared
    structure / residual appropriately."""

    def test_adding_constraint_changes_declared_features(self, project):
        base = _rich_graph()
        r1 = project(wrap(base))
        assert r1.status == "PROJECTED"
        # ADD the constraint (do not replace): declared feature count
        # strictly increases — a new CONSTRAINT locus is placed and its
        # declared invariant adds a feature bit.
        g2 = build_semantic_request_v1(
            request_id="t",
            entities=base.entities,
            operations=base.operations,
            dependencies=base.dependencies,
            relations=base.relations,
            constraints=(
                *base.constraints,
                SemanticConstraintV1("hcX", "bounded", "c", hard=True),
            ),
            output_entity_ids=base.output_entity_ids,
        )
        r2 = project(wrap(g2))
        assert r2.status == "PROJECTED"
        # a new CONSTRAINT locus + a new declared feature bit
        assert sum(r2.declared_features) > sum(r1.declared_features)
        assert r2.structural_input_fingerprint != r1.structural_input_fingerprint

    def test_removing_constraint_changes_residual(self, project):
        base = _rich_graph()
        r1 = project(wrap(base))
        assert r1.status == "PROJECTED"
        g2 = build_semantic_request_v1(
            request_id="t",
            entities=base.entities,
            operations=base.operations,
            dependencies=base.dependencies,
            relations=base.relations,
            constraints=(),
            output_entity_ids=base.output_entity_ids,
        )
        r2 = project(wrap(g2))
        assert r2.status == "PROJECTED"
        assert sum(r2.declared_features) < sum(r1.declared_features)


class TestInterfaceSensitivity:
    """G: changing interface binding -> binding/fingerprint changes
    deterministically."""

    def test_interface_rebinding_changes_fingerprint(self, project):
        base = _rich_graph()
        # bind the interface to op "c" instead of op "b"
        rels = tuple(
            SemanticRelationV1("if1", "api", "interface", "c")
            if r.relation_id == "if1"
            else r
            for r in base.relations
        )
        g2 = build_semantic_request_v1(
            request_id="t",
            entities=base.entities,
            operations=base.operations,
            dependencies=base.dependencies,
            relations=rels,
            constraints=base.constraints,
            output_entity_ids=base.output_entity_ids,
        )
        r1 = project(wrap(base))
        r2 = project(wrap(g2))
        assert r1.status == r2.status == "PROJECTED"
        b1 = [
            e for e in r1.bindings.edge_bindings
            if e.structural_kind == "interface"
        ]
        b2 = [
            e for e in r2.bindings.edge_bindings
            if e.structural_kind == "interface"
        ]
        assert b1[0].payload["bound_op"] == "b"
        assert b2[0].payload["bound_op"] == "c"
        assert r1.structural_input_fingerprint != r2.structural_input_fingerprint
