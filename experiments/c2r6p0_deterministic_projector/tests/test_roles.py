"""Structural role placement tests (mission 11)."""
from __future__ import annotations

import pytest

from elpis_p0.contracts import BasisToken
from elpis_p0.semantic_ir import (
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
    build_semantic_request_v1,
)

from conftest import wrap
from c2r6p0.allocator import INPUT, OUTPUT, TRANSFORM


class TestRolePlacement:
    def test_single_op_role(self, project):
        # single operation with in+out -> INPUT token? (arity rule)
        g = build_semantic_request_v1(
            request_id="t",
            entities=(
                SemanticEntityV1("in0", "input", "v", "str"),
                SemanticEntityV1("out0", "output", "v", "str"),
            ),
            operations=(
                SemanticOperationV1(
                    "a", "transform",
                    input_entity_ids=("in0",),
                    output_entity_ids=("out0",),
                ),
            ),
            output_entity_ids=("out0",),
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        b = r.bindings.op_bindings[0]
        # R8.ROLE_TOKEN, single-op arity rule: an operation that both
        # consumes AND produces is TRANSFORM (structural, not
        # executable); in-only -> INPUT, out-only -> OUTPUT.
        assert b.token == int(BasisToken.TRANSFORM)
        # and a pure source op is INPUT
        g2 = build_semantic_request_v1(
            request_id="t",
            entities=(SemanticEntityV1("in0", "input", "v", "str"),),
            operations=(
                SemanticOperationV1(
                    "s", "read", input_entity_ids=("in0",),
                    output_entity_ids=(),
                ),
            ),
        )
        r2 = project(wrap(g2))
        assert r2.status == "PROJECTED"
        assert r2.bindings.op_bindings[0].token == int(BasisToken.INPUT)

    def test_transform_is_structural_not_executable(self, project):
        # a chain: source -> transform -> output
        g = build_semantic_request_v1(
            request_id="t",
            entities=(
                SemanticEntityV1("in0", "input", "v", "str"),
                SemanticEntityV1("st0", "state", "v", "dict"),
                SemanticEntityV1("out0", "output", "v", "str"),
            ),
            operations=(
                SemanticOperationV1(
                    "src", "read", input_entity_ids=("in0",),
                    output_entity_ids=("st0",),
                ),
                SemanticOperationV1(
                    "mid", "transform", input_entity_ids=("st0",),
                    output_entity_ids=("st0",),
                ),
                SemanticOperationV1(
                    "sink", "write", input_entity_ids=("st0",),
                    output_entity_ids=("out0",),
                ),
            ),
            dependencies=(
                SemanticDependencyV1("d1", "src", "mid"),
                SemanticDependencyV1("d2", "mid", "sink"),
            ),
            output_entity_ids=("out0",),
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        by_id = {b.semantic_id: b for b in r.bindings.op_bindings}
        # source (indeg 0) -> INPUT
        assert by_id["src"].token == int(BasisToken.INPUT)
        # intermediate -> TRANSFORM (structural, not an executable impl)
        assert by_id["mid"].token == int(BasisToken.TRANSFORM)
        # sink (outdeg 0) -> OUTPUT
        assert by_id["sink"].token == int(BasisToken.OUTPUT)

    def test_role_tokens_in_vocabulary(self, project):
        g = build_semantic_request_v1(
            request_id="t",
            entities=(
                SemanticEntityV1("in0", "input", "v", "str"),
            ),
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
        if r.status != "PROJECTED":
            pytest.skip("decomposed")
        for b in r.bindings.op_bindings:
            assert b.token in {
                int(BasisToken.INPUT),
                int(BasisToken.TRANSFORM),
                int(BasisToken.OUTPUT),
            }
