"""Regression closure for the Furyan adversarial mathematical audit."""

import hashlib
from pathlib import Path

import pytest

from elpis_reference.structural_guidance._authority.c2r6p0.contracts import (
    ProjectionInputV1,
)
from elpis_reference.structural_guidance._authority.c2r6p0.projector import (
    project,
)
from elpis_reference.structural_guidance._authority.elpis_p0.contracts import (
    BasisToken,
)
from elpis_reference.structural_guidance._authority.elpis_p0.semantic_ir import (
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticRelationV1,
    build_semantic_request_v1,
)
from elpis_reference.structural_guidance._authority.elpis_p0.structural_residual import (
    LaneBindingV1,
    StructuralInvariantV1,
    StructuralSchemaError,
    build_structural_schema,
    capacity_requirements,
    halt_score,
    is_resolved,
    residual_clearance_score,
)


def _project(*, entities=(), relations=(), dependencies=()):
    request = build_semantic_request_v1(
        request_id="math_audit",
        entities=tuple(entities),
        operations=(
            SemanticOperationV1("A", "step"),
            SemanticOperationV1("B", "step"),
        ),
        relations=tuple(relations),
        dependencies=tuple(dependencies),
    )
    return project(ProjectionInputV1.from_signed(request))


@pytest.mark.parametrize(
    ("predicate", "source", "target", "entities"),
    [
        ("route", "A", "B", ()),
        ("state_feeds", "A", "B", ()),
        (
            "interface",
            "E",
            "B",
            (SemanticEntityV1("E", "interface", "E"),),
        ),
        (
            "mutates",
            "A",
            "E",
            (SemanticEntityV1("E", "state", "E"),),
        ),
    ],
)
def test_negated_structural_relations_are_typed_rejections(
    predicate, source, target, entities
):
    result = _project(
        entities=entities,
        relations=(
            SemanticRelationV1(
                "r1",
                source,
                predicate,
                target,
                negated=True,
            ),
        ),
    )
    assert result.status == "UNSUPPORTED_SEMANTIC_SHAPE"
    assert result.error is not None
    assert (
        result.error.detail["reason"]
        == "negated_structural_relation_unsupported"
    )


def test_state_feeds_dependency_is_not_silently_precedence():
    result = _project(
        dependencies=(
            SemanticDependencyV1(
                "d1",
                "A",
                "B",
                kind="state_feeds",
            ),
        ),
    )
    assert result.status == "UNSUPPORTED_SEMANTIC_SHAPE"


def test_state_feeds_relation_remains_memory_span_supported():
    result = _project(
        relations=(
            SemanticRelationV1(
                "r1",
                "A",
                "state_feeds",
                "B",
            ),
        ),
    )
    assert result.status == "PROJECTED", result.error
    assert not result.residual_ids
    edge = next(
        item
        for item in result.bindings.edge_bindings
        if item.semantic_id == "r1"
    )
    assert edge.structural_kind == "state_feeds"
    assert edge.discharged is True
    assert "memory_cell" in edge.payload


@pytest.mark.parametrize(
    ("kind", "lanes"),
    [
        ("LANE_SINGLE_OCCUPANCY", ()),
        ("PRECEDES", (0,)),
        ("CROSS_LANE_ROUTE", (0, 1, 2)),
        ("MEMORY_SPAN", (0,)),
        ("MUTATION_HAZARD", (0, 1)),
        ("CONSTRAINT_AFTER", (0, 1)),
        ("INTERFACE_TERMINAL", ()),
        ("TERMINAL_RESOLUTION", (0,)),
    ],
)
def test_structural_invariant_arity_is_constructor_enforced(kind, lanes):
    with pytest.raises(StructuralSchemaError, match="requires"):
        StructuralInvariantV1(
            invariant_id="bad",
            kind=kind,
            lanes=lanes,
        )


def test_residual_clearance_one_does_not_claim_resolution():
    schema = build_structural_schema(
        semantic_request_digest="0" * 64,
        lane_bindings=(
            LaneBindingV1(
                lane=0,
                semantic_id="A",
                role="operation",
                operational_token=int(BasisToken.INPUT),
            ),
        ),
        invariants=(
            StructuralInvariantV1(
                invariant_id="terminal",
                kind="TERMINAL_RESOLUTION",
                lanes=(),
            ),
        ),
    )
    grid = schema.initial_grid
    assert residual_clearance_score(grid, schema) == 1.0
    assert halt_score(grid, schema) == 1.0
    assert is_resolved(grid, schema) is False


def test_capacity_helper_cannot_be_read_as_infeasibility_certificate():
    doc = capacity_requirements.__doc__ or ""
    assert "never an infeasibility proof" in doc
    assert "must not be interpreted as a mathematical lower" in doc

def test_ruleset_structural_residual_pin_matches_live_authority():
    from elpis_reference.structural_guidance._authority.c2r6p0 import rules
    from elpis_reference.structural_guidance._authority.elpis_p0 import (
        structural_residual,
    )

    live = hashlib.sha256(
        Path(structural_residual.__file__).read_bytes()
    ).hexdigest()

    assert rules.FROZEN_STRUCTURAL_RESIDUAL_SHA256 == live
    assert rules.load_ruleset().structural_residual_sha == live

