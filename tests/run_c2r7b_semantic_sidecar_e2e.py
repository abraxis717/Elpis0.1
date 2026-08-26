from __future__ import annotations

import json

from elpis_p0.canonical import digest
from elpis_p0.contracts import ArtifactCandidate, RequestContext
from elpis_p0.factory import build_default_controller
from elpis_p0.projector import DeterministicPythonProjector
from elpis_p0.semantic_binding import (
    SemanticSidecarPythonProjector,
)
from elpis_p0.semantic_ir import (
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticRelationV1,
    build_semantic_request_v1,
)
from elpis_reference.p0_validator_ingress import (
    bind_p0_validator_ingress_to_controller,
    build_p0_projection_trace,
)


class RejectingDecoder:
    def decode(self, context, plan):
        source = "def solution(:\n    return 1\n"
        return ArtifactCandidate(
            language="python",
            source=source,
            digest=digest(
                {
                    "plan_digest": plan.plan_digest,
                    "source": source,
                }
            ),
        )


def graph(reverse=False):
    return build_semantic_request_v1(
        request_id="c2r7b-e2e",
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
                "order", "read", "write"
            ),
        ),
        output_entity_ids=("value",),
    )


def ctx(g=None):
    return RequestContext(
        request_id="c2r7b-e2e",
        prompt="read a file and then write a database",
        parameters=("source", "sink"),
        semantic_request=g,
    )


def main():
    legacy = DeterministicPythonProjector().project(ctx())
    first_projection = SemanticSidecarPythonProjector().project(
        ctx(graph())
    )
    second_projection = SemanticSidecarPythonProjector().project(
        ctx(graph(reverse=True))
    )

    if first_projection.grid81 != legacy.grid81:
        raise RuntimeError("semantic sidecar changed Grid81")
    if first_projection.features != legacy.features:
        raise RuntimeError("semantic sidecar changed legacy features")
    if (
        first_projection.structural_projection_digest
        != legacy.digest
    ):
        raise RuntimeError("legacy structural identity not retained")
    if first_projection.grid81 != second_projection.grid81:
        raise RuntimeError("graph mutation changed structural Grid81")
    if first_projection.digest == second_projection.digest:
        raise RuntimeError("different semantic graphs collapsed")

    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    result = controller.run(ctx(graph()))
    authorized = controller.authorized_artifact_lineage(
        result,
        validator_index=0,
    )
    if (
        authorized.lineage.semantic_request_digest
        != graph().digest
    ):
        raise RuntimeError("lineage lost semantic graph identity")

    ingress = bind_p0_validator_ingress_to_controller(
        controller
    )
    trace = build_p0_projection_trace(
        projection_digest=result.projection.digest,
        grid81=result.projection.grid81,
        semantic_rows=result.projection.semantic_rows,
        semantic_request_digest=(
            result.projection.semantic_request_digest
        ),
    )
    diagnostic = ingress.task_diagnostic_from_validator_failure(
        task_scope_id=result.request_id,
        frame_index=0,
        artifact_digest=result.artifact.digest,
        evidence=result.evidence[0],
        projection_trace=trace,
        authorized=authorized,
    )

    print(
        json.dumps(
            {
                "schema": (
                    "elpis.public-c2r7b-semantic-sidecar-binding.v1"
                ),
                "status": "PASS",
                "claims": {
                    "semantic_graph_digest_bound_to_projection": True,
                    "legacy_grid81_payload_preserved": True,
                    "semantic_graph_has_no_cell_mapping_authority": True,
                    "semantic_identity_propagates_to_controller_lineage": True,
                    "ingress_requires_matching_semantic_trace_identity": True,
                    "natural_language_semantic_extractor": False,
                    "graph_grid81_lossless_encoding": False,
                    "semantic_reconstruction_quality": False,
                    "relational_ecs_decomposition": False,
                    "learned_semantic_compiler": False,
                    "runtime_admission": False,
                },
                "projection": {
                    "structural_projection_digest": (
                        result.projection.structural_projection_digest
                    ),
                    "semantic_request_digest": (
                        result.projection.semantic_request_digest
                    ),
                    "semantic_binding_digest": (
                        result.projection.semantic_binding_digest
                    ),
                    "bound_projection_digest": (
                        result.projection.digest
                    ),
                },
                "lineage_digest": (
                    authorized.lineage.lineage_digest
                ),
                "diagnostic_digest": diagnostic.details_digest,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
