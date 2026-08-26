from __future__ import annotations

from dataclasses import replace

import pytest

from elpis_p0.canonical import digest
from elpis_p0.contracts import ArtifactCandidate, RequestContext
from elpis_p0.factory import build_default_controller
from elpis_p0.projector import DeterministicPythonProjector
from elpis_p0.semantic_binding import (
    P0SemanticSidecarBindingError,
    SemanticSidecarPythonProjector,
)
from elpis_p0.semantic_ir import (
    SemanticConstraintV1,
    SemanticDependencyV1,
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticQuantityV1,
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


def graph(
    *,
    reverse=False,
    negated=False,
    count=5,
    data_type="str",
):
    return build_semantic_request_v1(
        request_id="c2r7b",
        entities=(
            SemanticEntityV1(
                "source", "resource", "file", data_type
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
                "arity",
                "read",
                "input_arity",
                "eq",
                count,
            ),
        ),
        output_entity_ids=("value",),
    )


def context(semantic_request=None):
    return RequestContext(
        request_id="c2r7b",
        prompt="read a file and then write a database",
        parameters=("source", "sink"),
        semantic_request=semantic_request,
    )


def test_graphless_sidecar_projector_is_exact_legacy_projection():
    legacy = DeterministicPythonProjector().project(
        context()
    )
    sidecar = SemanticSidecarPythonProjector().project(
        context()
    )
    assert sidecar == legacy


def test_structured_projection_preserves_grid_and_features():
    structured = SemanticSidecarPythonProjector().project(
        context(graph())
    )
    legacy = DeterministicPythonProjector().project(
        context()
    )
    assert structured.grid81 == legacy.grid81
    assert structured.semantic_rows == legacy.semantic_rows
    assert structured.features == legacy.features
    assert (
        structured.structural_projection_digest
        == legacy.digest
    )
    assert structured.semantic_request_digest == graph().digest
    assert structured.semantic_binding_digest
    assert structured.digest != legacy.digest


@pytest.mark.parametrize(
    "mutation",
    (
        {"reverse": True},
        {"negated": True},
        {"count": 6},
        {"data_type": "bytes"},
    ),
)
def test_graph_mutation_changes_binding_not_grid(mutation):
    projector = SemanticSidecarPythonProjector()
    first = projector.project(context(graph()))
    second = projector.project(context(graph(**mutation)))

    assert first.grid81 == second.grid81
    assert first.features == second.features
    assert (
        first.structural_projection_digest
        == second.structural_projection_digest
    )
    assert (
        first.semantic_request_digest
        != second.semantic_request_digest
    )
    assert (
        first.semantic_binding_digest
        != second.semantic_binding_digest
    )
    assert first.digest != second.digest


def test_sidecar_tamper_fails_closed():
    projection = SemanticSidecarPythonProjector().project(
        context(graph())
    )
    for forged in (
        replace(
            projection,
            semantic_request_digest="0" * 64,
        ),
        replace(
            projection,
            semantic_binding_digest="0" * 64,
        ),
        replace(
            projection,
            grid81=(
                (0,)
                + projection.grid81[1:]
            ),
        ),
    ):
        with pytest.raises(
            P0SemanticSidecarBindingError
        ):
            forged.validate()


def test_legacy_projector_still_refuses_structured_graph():
    with pytest.raises(
        ValueError,
        match="legacy keyword projector refuses",
    ):
        DeterministicPythonProjector().project(
            context(graph())
        )


def test_default_controller_uses_explicit_sidecar_binding():
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    result = controller.run(context(graph()))
    assert result.projection.semantic_request_digest == graph().digest
    assert result.trm_proposal.input_digest == result.projection.digest
    assert (
        result.decoder_plan.structural_digest
        == result.projection.digest
    )
    assert result.result_digest
    assert not result.accepted


def test_same_grid_different_graph_changes_downstream_identity():
    first_controller = build_default_controller()
    first_controller.decoder = RejectingDecoder()
    first = first_controller.run(context(graph()))

    second_controller = build_default_controller()
    second_controller.decoder = RejectingDecoder()
    second = second_controller.run(
        context(graph(reverse=True))
    )

    assert first.projection.grid81 == second.projection.grid81
    assert first.projection.digest != second.projection.digest
    assert first.trm_proposal.digest != second.trm_proposal.digest
    assert (
        first.decoder_plan.plan_digest
        != second.decoder_plan.plan_digest
    )
    assert first.artifact.digest != second.artifact.digest
    assert first.result_digest != second.result_digest


def test_authority_lineage_exposes_semantic_request_digest():
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    result = controller.run(context(graph()))
    authorized = controller.authorized_artifact_lineage(
        result,
        validator_index=0,
    )
    assert (
        authorized.lineage.semantic_request_digest
        == result.projection.semantic_request_digest
    )


def test_projection_trace_semantic_digest_is_required_at_ingress():
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    result = controller.run(context(graph()))
    authorized = controller.authorized_artifact_lineage(
        result,
        validator_index=0,
    )
    ingress = bind_p0_validator_ingress_to_controller(
        controller
    )

    omitted = build_p0_projection_trace(
        projection_digest=result.projection.digest,
        grid81=result.projection.grid81,
        semantic_rows=result.projection.semantic_rows,
    )
    with pytest.raises(
        ValueError,
        match="semantic request",
    ):
        ingress.task_diagnostic_from_validator_failure(
            task_scope_id=result.request_id,
            frame_index=0,
            artifact_digest=result.artifact.digest,
            evidence=result.evidence[0],
            projection_trace=omitted,
            authorized=authorized,
        )

    correct = build_p0_projection_trace(
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
        projection_trace=correct,
        authorized=authorized,
    )
    assert diagnostic.subject_digest == result.artifact.digest


def test_graph_request_id_mismatch_fails_before_projection():
    wrong = replace(
        graph(),
        request_id="other",
    )
    # Digest is now stale as well; validation must fail closed.
    with pytest.raises(Exception):
        SemanticSidecarPythonProjector().project(
            context(wrong)
        )
