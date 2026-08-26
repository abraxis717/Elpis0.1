from __future__ import annotations

import json

from elpis_p0.contracts import RequestContext
from elpis_p0.projector import DeterministicPythonProjector
from elpis_p0.semantic_ir import (
    SemanticConstraintV1,
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticQuantityV1,
    SemanticRelationV1,
    build_semantic_request_v1,
)


def build(*, negated=False, count=5, reverse=False):
    return build_semantic_request_v1(
        request_id="c2r7a-e2e",
        entities=(
            SemanticEntityV1(
                "source", "resource", "file", "path"
            ),
            SemanticEntityV1(
                "sink", "resource", "database", "dsn"
            ),
            SemanticEntityV1(
                "value", "value", "record", "dict"
            ),
        ),
        operations=(
            SemanticOperationV1(
                "read",
                "read",
                input_entity_ids=("source",),
                output_entity_ids=("value",),
            ),
            SemanticOperationV1(
                "write",
                "write",
                input_entity_ids=("value", "sink"),
            ),
        ),
        constraints=(
            SemanticConstraintV1(
                "network",
                "network_access",
                "read",
                negated=negated,
            ),
        ),
        relations=(
            SemanticRelationV1(
                "flow",
                "sink" if reverse else "source",
                "feeds",
                "source" if reverse else "sink",
            ),
        ),
        dependencies=(
            SemanticDependencyV1(
                "order",
                "read",
                "write",
            ),
        ),
        quantities=(
            SemanticQuantityV1(
                "count",
                "read",
                "input_arity",
                "eq",
                count,
            ),
        ),
        output_entity_ids=("value",),
    )


def main():
    base = build()
    base.validate()

    distinctions = {
        "relation_direction": base.digest != build(
            reverse=True
        ).digest,
        "negation": base.digest != build(
            negated=True
        ).digest,
        "quantity_4_to_5": build(
            count=4
        ).digest != build(count=5).digest,
        "quantity_5_to_6": build(
            count=5
        ).digest != build(count=6).digest,
    }
    if not all(distinctions.values()):
        raise RuntimeError(
            f"semantic distinction collapsed: {distinctions}"
        )

    context = RequestContext(
        request_id=base.request_id,
        prompt="read a file and then write to a database",
        parameters=("source", "sink"),
        semantic_request=base,
    )
    refused = False
    try:
        DeterministicPythonProjector().project(context)
    except ValueError as exc:
        refused = "structured semantic request" in str(exc)
    if not refused:
        raise RuntimeError(
            "legacy keyword projector silently accepted semantic graph"
        )

    print(
        json.dumps(
            {
                "schema": (
                    "elpis.public-c2r7a-relational-semantic-ir.v1"
                ),
                "status": "PASS",
                "claims": {
                    "canonical_relational_task_representation": True,
                    "explicit_entity_identity": True,
                    "explicit_operation_arguments": True,
                    "explicit_constraints_and_negation": True,
                    "explicit_relations": True,
                    "explicit_dependency_direction": True,
                    "explicit_integer_quantities": True,
                    "legacy_keyword_projector_refuses_structured_graph": True,
                    "natural_language_semantic_extractor": False,
                    "semantic_graph_grid81_binding": False,
                    "semantic_reconstruction_quality": False,
                    "relational_ecs_decomposition": False,
                    "learned_semantic_compiler": False,
                    "runtime_admission": False,
                },
                "distinctions": distinctions,
                "semantic_request_digest": base.digest,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
