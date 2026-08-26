#!/usr/bin/env python3
"""Read-only C2R7-B semantic-sidecar binding adversarial diagnostic."""
from __future__ import annotations

from dataclasses import replace
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for rel in (
    "runtime/R0/src",
    "components/TRMFractalSpine/src",
    "components/Grid81DeterministicStructuralAdjudicator/src",
    "components/Grid81StructuralSemantics/src",
    "components/Pipeline/P0ControlProtocol/src",
    "components",
    "src",
):
    sys.path.insert(0, str(REPO / rel))

from elpis_p0.canonical import digest
from elpis_p0.contracts import ArtifactCandidate, RequestContext
from elpis_p0.factory import build_default_controller
from elpis_p0.projector import DeterministicPythonProjector
from elpis_p0.semantic_binding import (
    P0SemanticSidecarBindingError,
    SemanticSidecarPythonProjector,
)
from elpis_p0.semantic_ir import (
    SemanticEntityV1,
    SemanticOperationV1,
    SemanticRelationV1,
    build_semantic_request_v1,
)
from elpis_reference.p0_validator_ingress import (
    bind_p0_validator_ingress_to_controller,
    build_p0_projection_trace,
)

FINDINGS = []
EXPLOITS = []


def record(check, status, detail):
    FINDINGS.append(
        {"check": check, "status": status, "detail": detail}
    )
    if status == "EXPLOIT":
        EXPLOITS.append(check)


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
        request_id="c2r7b-redteam",
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
        output_entity_ids=("value",),
    )


def ctx(g=None):
    return RequestContext(
        request_id="c2r7b-redteam",
        prompt="read a file and then write a database",
        parameters=("source", "sink"),
        semantic_request=g,
    )


def structural_noninterference():
    legacy = DeterministicPythonProjector().project(ctx())
    first = SemanticSidecarPythonProjector().project(
        ctx(graph())
    )
    second = SemanticSidecarPythonProjector().project(
        ctx(graph(reverse=True))
    )
    holds = (
        first.grid81 == legacy.grid81 == second.grid81
        and first.features == legacy.features == second.features
        and first.structural_projection_digest == legacy.digest
        and second.structural_projection_digest == legacy.digest
        and first.digest != second.digest
    )
    record(
        "semantic_identity_without_grid_mutation",
        "DEFENSE_HOLDS" if holds else "EXPLOIT",
        {
            "grid_equal": first.grid81 == second.grid81,
            "legacy_structural_digest_retained": (
                first.structural_projection_digest == legacy.digest
            ),
            "bound_digests_distinct": (
                first.digest != second.digest
            ),
        },
    )


def tamper_rejection():
    projection = SemanticSidecarPythonProjector().project(
        ctx(graph())
    )
    outcomes = {}
    for name, forged in (
        (
            "semantic_request_digest",
            replace(
                projection,
                semantic_request_digest="0" * 64,
            ),
        ),
        (
            "semantic_binding_digest",
            replace(
                projection,
                semantic_binding_digest="0" * 64,
            ),
        ),
        (
            "grid81",
            replace(
                projection,
                grid81=(
                    (0,)
                    + projection.grid81[1:]
                ),
            ),
        ),
    ):
        rejected = False
        try:
            forged.validate()
        except P0SemanticSidecarBindingError:
            rejected = True
        outcomes[name] = rejected

    record(
        "sidecar_tamper_rejected",
        (
            "DEFENSE_HOLDS"
            if all(outcomes.values())
            else "EXPLOIT"
        ),
        outcomes,
    )


def lineage_propagation():
    first_controller = build_default_controller()
    first_controller.decoder = RejectingDecoder()
    first = first_controller.run(ctx(graph()))
    first_auth = first_controller.authorized_artifact_lineage(
        first,
        validator_index=0,
    )

    second_controller = build_default_controller()
    second_controller.decoder = RejectingDecoder()
    second = second_controller.run(ctx(graph(reverse=True)))

    holds = (
        first.projection.grid81 == second.projection.grid81
        and first.projection.digest != second.projection.digest
        and first.trm_proposal.digest != second.trm_proposal.digest
        and first.decoder_plan.plan_digest != second.decoder_plan.plan_digest
        and first.result_digest != second.result_digest
        and first_auth.lineage.semantic_request_digest
        == first.projection.semantic_request_digest
    )
    record(
        "semantic_identity_propagates_downstream",
        "DEFENSE_HOLDS" if holds else "EXPLOIT",
        {
            "same_grid": first.projection.grid81 == second.projection.grid81,
            "projection_distinct": first.projection.digest != second.projection.digest,
            "trm_distinct": first.trm_proposal.digest != second.trm_proposal.digest,
            "plan_distinct": first.decoder_plan.plan_digest != second.decoder_plan.plan_digest,
            "result_distinct": first.result_digest != second.result_digest,
            "lineage_exposes_semantic_digest": (
                first_auth.lineage.semantic_request_digest
                == first.projection.semantic_request_digest
            ),
        },
    )


def ingress_substitution():
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    result = controller.run(ctx(graph()))
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
    rejected = False
    try:
        ingress.task_diagnostic_from_validator_failure(
            task_scope_id=result.request_id,
            frame_index=0,
            artifact_digest=result.artifact.digest,
            evidence=result.evidence[0],
            projection_trace=omitted,
            authorized=authorized,
        )
    except Exception:
        rejected = True

    correct_live = False
    if rejected:
        correct = build_p0_projection_trace(
            projection_digest=result.projection.digest,
            grid81=result.projection.grid81,
            semantic_rows=result.projection.semantic_rows,
            semantic_request_digest=(
                result.projection.semantic_request_digest
            ),
        )
        ingress.task_diagnostic_from_validator_failure(
            task_scope_id=result.request_id,
            frame_index=0,
            artifact_digest=result.artifact.digest,
            evidence=result.evidence[0],
            projection_trace=correct,
            authorized=authorized,
        )
        correct_live = True

    record(
        "semantic_trace_substitution_rejected_before_consumption",
        (
            "DEFENSE_HOLDS"
            if rejected and correct_live
            else "EXPLOIT"
        ),
        {
            "omitted_semantic_digest_rejected": rejected,
            "real_capability_remained_live": correct_live,
        },
    )


def claim_boundary():
    record(
        "graph_prompt_consistency_not_claimed",
        "OBSERVATION",
        {
            "natural_language_extraction": False,
            "prompt_graph_semantic_consistency_proven": False,
            "graph_to_cell_mapping": False,
            "graph_structural_mutation_authority": False,
            "binding_is_identity_only": True,
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    for check in (
        structural_noninterference,
        tamper_rejection,
        lineage_propagation,
        ingress_substitution,
        claim_boundary,
    ):
        try:
            check()
        except Exception as exc:
            record(
                check.__name__,
                "HARNESS_ERROR",
                f"{type(exc).__name__}: {exc}",
            )

    report = {
        "schema": "elpis.redteam-c2r7b-semantic-sidecar-binding.v1",
        "base": "e01ca10a612d506d44304403ae2c48be48c92154",
        "role": "READ_ONLY_ADVERSARIAL_DIAGNOSTIC",
        "findings": FINDINGS,
        "exploits": EXPLOITS,
        "exploit_count": len(EXPLOITS),
        "claim_boundary": {
            "semantic_identity_binding": True,
            "grid81_semantic_encoding": False,
            "natural_language_extraction": False,
            "prompt_graph_consistency": False,
            "semantic_reconstruction": False,
            "relational_ecs_decomposition": False,
            "learned_compiler": False,
            "runtime_admission": False,
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    if not args.quiet:
        print(text)
    return 1 if EXPLOITS else 0


if __name__ == "__main__":
    raise SystemExit(main())
