from __future__ import annotations

import json

from DarwinianMatrix.projector.constraints import (
    ClampOperation,
    ClampProposal,
    ClampState,
    ClampTransaction,
    apply_clamp_transaction,
)
from elpis_p0.artifact_lineage import build_artifact_proposal_lineage
from elpis_p0.canonical import digest
from elpis_p0.contracts import ArtifactCandidate, RequestContext
from elpis_p0.factory import build_default_controller
from elpis_p0.semantic_space import (
    validator_failure_cell_index,
    validator_failure_role,
)
from elpis_reference.p0_validator_ingress import (
    build_p0_projection_trace,
    task_diagnostic_from_p0_validator_failure,
)
from elpis_reference.projector_release import (
    ReleaseBindingTableV1,
    ReleaseBindingTargetV1,
    build_release_transaction,
)
from elpis_reference.semantic_refinement import SEMANTIC_OBJECT


class RejectingDecoder:
    def decode(self, context, plan):
        source = "def solution(:\n    return 1\n"
        return ArtifactCandidate(
            language="python",
            source=source,
            digest=digest({"plan_digest": plan.plan_digest, "source": source}),
        )


def main():
    ctx = RequestContext(
        request_id="c2r5-production-lineage-e2e",
        prompt="write deterministic typed python solution and validate without imports",
        domain="python",
        entrypoint="solution",
        parameters=("x",),
    )
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    result = controller.run(ctx)
    if result.accepted or len(result.evidence) != 1 or result.evidence[0].passed:
        raise RuntimeError("fixture did not produce one rejected production P0 result")

    lineage = build_artifact_proposal_lineage(result, validator_index=0)
    if lineage.structural_proposal_digest != result.trm_proposal.digest:
        raise RuntimeError("lineage lost structural proposal identity")
    if result.decoder_plan.structural_proposal_digest != result.trm_proposal.digest:
        raise RuntimeError("decoder plan lost structural proposal identity")

    trace = build_p0_projection_trace(
        projection_digest=result.projection.digest,
        grid81=result.projection.grid81,
        semantic_rows=result.projection.semantic_rows,
    )
    evidence = result.evidence[0]
    role = validator_failure_role(evidence.validator_id, evidence.code)
    target = validator_failure_cell_index(evidence.validator_id, evidence.code)
    unrelated = next(
        c for c in range(0, 63) if result.projection.grid81[c] != 0
    )

    state = ClampState.empty(ctx.request_id)
    initial = apply_clamp_transaction(
        state=state,
        transaction=ClampTransaction(
            transaction_id="prevalidation-support",
            episode_id=state.episode_id,
            expected_state_digest=state.digest(),
            proposals=(
                ClampProposal(
                    proposal_id="validation",
                    operation=ClampOperation.ASSERT,
                    slot_id="p0.validation.support",
                    evidence_digest=trace.trace_digest,
                    cell_index=target,
                    value=result.projection.grid81[target],
                ),
                ClampProposal(
                    proposal_id="unrelated",
                    operation=ClampOperation.ASSERT,
                    slot_id="p0.unrelated.support",
                    evidence_digest=trace.trace_digest,
                    cell_index=unrelated,
                    value=result.projection.grid81[unrelated],
                ),
            ),
        ),
    )
    if not initial.accepted:
        raise RuntimeError("support assertion failed")

    locus = trace.semantic_digest_for_role(role)
    bindings = ReleaseBindingTableV1(
        episode_id=initial.state.episode_id,
        clamp_state_digest=initial.state.digest(),
        targets=(
            ReleaseBindingTargetV1(
                cell_index=target,
                owner="p0.validation.support",
                locus_namespace=SEMANTIC_OBJECT,
                locus_identity=locus,
            ),
        ),
    )

    diagnostic = task_diagnostic_from_p0_validator_failure(
        task_scope_id=ctx.request_id,
        frame_index=0,
        artifact_digest=result.artifact.digest,
        evidence=evidence,
        projection_trace=trace,
        lineage=lineage,
    )
    residual = diagnostic.to_task_residual()
    resolved = trace.reverse_trace_index().resolve(residual)
    if resolved.P7_cell_indices != (target,):
        raise RuntimeError("validator failure did not resolve to exact repair sub-locus")

    plan, tx = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=initial.state,
        release_bindings=bindings,
    )
    if tx is None or plan.target_cells != (target,):
        raise RuntimeError("release was not exactly one prebound cell")
    released = apply_clamp_transaction(state=initial.state, transaction=tx)
    if not released.accepted or not bool(released.state.active_mask[unrelated]):
        raise RuntimeError("canonical release violated unrelated support")

    report = {
        "schema": "elpis.public-c2r5-artifact-proposal-lineage.v1",
        "status": "PASS",
        "lineage": {
            "p0_result_digest": lineage.p0_result_digest,
            "projection_digest": lineage.projection_digest,
            "structural_proposal_digest": lineage.structural_proposal_digest,
            "decoder_plan_digest": lineage.decoder_plan_digest,
            "artifact_digest": lineage.artifact_digest,
            "validator_evidence_digest": lineage.validator_evidence_digest,
            "lineage_digest": lineage.lineage_digest,
        },
        "release": {
            "target_cells": list(plan.target_cells),
            "unrelated_support_preserved": bool(
                released.state.active_mask[unrelated]
            ),
            "validator_failure_role": role,
            "reverse_trace_cardinality": len(resolved.P7_cell_indices),
        },
        "claims": {
            "p0_result_integrity_verified": True,
            "structural_proposal_bound_to_projection": True,
            "decoder_plan_bound_to_structural_proposal": True,
            "artifact_bound_to_decoder_plan": True,
            "exact_validator_evidence_bound": True,
            "validator_ingress_requires_self_consistent_lineage_record": True,
            "validator_failure_sublocus_cardinality_one": True,
            "lineage_digest_is_external_attestation": False,
            "cryptographic_external_attestation": False,
            "production_learned_reproposal": False,
            "runtime_admission": False,
        },
    }
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
