from __future__ import annotations

from dataclasses import replace
import inspect
import json

from elpis_p0.canonical import digest
from elpis_p0.contracts import ArtifactCandidate, RequestContext
from elpis_p0.factory import build_default_controller
from elpis_p0.lineage_authority import P0LineageAuthorityError
from elpis_reference import p0_validator_ingress as ingress_module
from elpis_reference.p0_validator_ingress import (
    P0ValidatorIngressContractError,
    P0ValidatorIngressV1,
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
                {"plan_digest": plan.plan_digest, "source": source}
            ),
        )


def main():
    if hasattr(
        ingress_module, "task_diagnostic_from_p0_validator_failure"
    ):
        raise RuntimeError("legacy bare-lineage ingress survived")

    method_names = set(
        inspect.signature(
            P0ValidatorIngressV1.task_diagnostic_from_validator_failure
        ).parameters
    )
    if method_names.intersection(
        {"controller", "verifier", "authority", "authority_consumer", "consume"}
    ):
        raise RuntimeError("per-request authority selector survived")

    ctx = RequestContext(
        request_id="c2r6cb-trusted-controller-ingress",
        prompt="write deterministic typed python solution and validate without imports",
        domain="python",
        entrypoint="solution",
        parameters=("x",),
    )
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    ingress = bind_p0_validator_ingress_to_controller(controller)
    result = controller.run(ctx)
    authorized = controller.authorized_artifact_lineage(
        result, validator_index=0
    )
    trace = build_p0_projection_trace(
        projection_digest=result.projection.digest,
        grid81=result.projection.grid81,
        semantic_rows=result.projection.semantic_rows,
    )

    bad = replace(result.evidence[0], code="UNKNOWN_FAILURE")
    try:
        ingress.task_diagnostic_from_validator_failure(
            task_scope_id=ctx.request_id,
            frame_index=0,
            artifact_digest=result.artifact.digest,
            evidence=bad,
            projection_trace=trace,
            authorized=authorized,
        )
    except P0ValidatorIngressContractError:
        pass
    else:
        raise RuntimeError("unsupported evidence entered consumption")

    diagnostic = ingress.task_diagnostic_from_validator_failure(
        task_scope_id=ctx.request_id,
        frame_index=0,
        artifact_digest=result.artifact.digest,
        evidence=result.evidence[0],
        projection_trace=trace,
        authorized=authorized,
    )

    try:
        ingress.task_diagnostic_from_validator_failure(
            task_scope_id=ctx.request_id,
            frame_index=1,
            artifact_digest=result.artifact.digest,
            evidence=result.evidence[0],
            projection_trace=trace,
            authorized=authorized,
        )
    except P0LineageAuthorityError:
        replay_rejected = True
    else:
        replay_rejected = False
    if not replay_rejected:
        raise RuntimeError("authorization replay accepted")

    print(
        json.dumps(
            {
                "schema": "elpis.public-c2r6cb-trusted-controller-ingress.v1",
                "status": "PASS",
                "claims": {
                    "production_validator_ingress_requires_controller_authorization": True,
                    "per_request_authority_selector_absent": True,
                    "legacy_bare_lineage_ingress_removed": True,
                    "unsupported_evidence_rejects_before_consumption": True,
                    "authorization_consumed_exactly_once": True,
                    "diagnostic_emitted_after_authority_consumption": True,
                    "hostile_same_process_isolation": False,
                    "cross_process_durability": False,
                    "external_attestation": False,
                    "release_binding_temporal_authority_fixed": False,
                    "semantic_decomposition_improved": False,
                    "runtime_admission": False,
                },
                "diagnostic": {
                    "details_digest": diagnostic.details_digest,
                    "locus_identity": diagnostic.locus_identity,
                },
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
