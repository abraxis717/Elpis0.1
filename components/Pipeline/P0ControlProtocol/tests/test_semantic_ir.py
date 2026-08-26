from __future__ import annotations

from dataclasses import replace

import pytest

from elpis_p0.contracts import RequestContext
from elpis_p0.projector import DeterministicPythonProjector
from elpis_p0.semantic_ir import (
    P0SemanticRequestContractError,
    SemanticConstraintV1,
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticQuantityV1,
    SemanticRelationV1,
    build_semantic_request_v1,
)


def graph(
    *,
    reverse_relation=False,
    reverse_dependency=False,
    negated=False,
    count=5,
    data_type="str",
    input_order=("path", "dsn"),
    declaration_reversed=False,
):
    entities = (
        SemanticEntityV1("path", "resource", "file", data_type),
        SemanticEntityV1("dsn", "resource", "database", data_type),
        SemanticEntityV1("record", "value", "record", "dict"),
    )
    operations = (
        SemanticOperationV1(
            "read",
            "read",
            input_entity_ids=input_order,
            output_entity_ids=("record",),
        ),
        SemanticOperationV1(
            "write",
            "write",
            input_entity_ids=("record", "dsn"),
        ),
    )
    constraints = (
        SemanticConstraintV1(
            "no_network",
            "network_access",
            "read",
            negated=negated,
        ),
    )
    relations = (
        SemanticRelationV1(
            "resource_relation",
            "dsn" if reverse_relation else "path",
            "feeds",
            "path" if reverse_relation else "dsn",
        ),
    )
    dependencies = (
        SemanticDependencyV1(
            "order",
            "write" if reverse_dependency else "read",
            "read" if reverse_dependency else "write",
        ),
    )
    quantities = (
        SemanticQuantityV1(
            "arity",
            "read",
            "input_arity",
            "eq",
            count,
        ),
    )
    if declaration_reversed:
        entities = tuple(reversed(entities))
        operations = tuple(reversed(operations))

    return build_semantic_request_v1(
        request_id="semantic_case",
        entities=entities,
        operations=operations,
        constraints=constraints,
        relations=relations,
        dependencies=dependencies,
        quantities=quantities,
        output_entity_ids=("record",),
    )


def test_declaration_order_is_canonicalized():
    assert graph().digest == graph(
        declaration_reversed=True
    ).digest


def test_subject_object_direction_changes_digest():
    assert graph().digest != graph(
        reverse_relation=True
    ).digest


def test_dependency_direction_changes_digest():
    assert graph().digest != graph(
        reverse_dependency=True
    ).digest


def test_negation_changes_digest():
    assert graph().digest != graph(negated=True).digest


def test_quantity_above_four_is_preserved():
    assert graph(count=4).digest != graph(count=5).digest
    assert graph(count=5).digest != graph(count=6).digest


def test_entity_type_changes_digest():
    assert graph(data_type="str").digest != graph(
        data_type="bytes"
    ).digest


def test_operation_argument_order_changes_digest():
    assert graph().digest != graph(
        input_order=("dsn", "path")
    ).digest


def test_digest_tampering_rejects():
    request = graph()
    forged = replace(request, digest="0" * 64)
    with pytest.raises(
        P0SemanticRequestContractError,
        match="digest mismatch",
    ):
        forged.validate()


def test_dangling_operation_reference_rejects():
    with pytest.raises(
        P0SemanticRequestContractError,
        match="unknown entity",
    ):
        build_semantic_request_v1(
            request_id="dangling",
            entities=(
                SemanticEntityV1(
                    "known", "value", "known"
                ),
            ),
            operations=(
                SemanticOperationV1(
                    "op",
                    "read",
                    input_entity_ids=("missing",),
                ),
            ),
        )


def test_duplicate_node_identity_rejects():
    with pytest.raises(
        P0SemanticRequestContractError,
        match="globally unique",
    ):
        build_semantic_request_v1(
            request_id="duplicate",
            entities=(
                SemanticEntityV1("same", "value", "a"),
            ),
            operations=(
                SemanticOperationV1("same", "read"),
            ),
        )


def test_dependency_cycle_rejects():
    with pytest.raises(
        P0SemanticRequestContractError,
        match="acyclic",
    ):
        build_semantic_request_v1(
            request_id="cycle",
            entities=(
                SemanticEntityV1("x", "value", "x"),
            ),
            operations=(
                SemanticOperationV1("a", "step"),
                SemanticOperationV1("b", "step"),
            ),
            dependencies=(
                SemanticDependencyV1("ab", "a", "b"),
                SemanticDependencyV1("ba", "b", "a"),
            ),
        )


def test_legacy_keyword_projector_refuses_structured_semantics():
    request = graph()
    context = RequestContext(
        request_id=request.request_id,
        prompt="read a file and then write a database",
        parameters=("path", "dsn"),
        semantic_request=request,
    )
    with pytest.raises(
        ValueError,
        match="structured semantic request",
    ):
        DeterministicPythonProjector().project(context)


def test_semantic_request_id_must_match_context():
    request = graph()
    context = RequestContext(
        request_id="other",
        prompt="read a file and then write a database",
        semantic_request=request,
    )
    with pytest.raises(
        ValueError,
        match="request_id does not match",
    ):
        DeterministicPythonProjector().project(context)


def test_legacy_projector_remains_available_without_semantic_graph():
    context = RequestContext(
        request_id="legacy",
        prompt="write deterministic typed python",
        parameters=("x",),
    )
    first = DeterministicPythonProjector().project(context)
    second = DeterministicPythonProjector().project(context)
    assert first == second
