from __future__ import annotations

import json

from DarwinianMatrix.projector.constraints import (
    ClampOperation,
    ClampProposal,
    ClampState,
    ClampTransaction,
    apply_clamp_transaction,
)
from elpis_p0.canonical import digest
from elpis_p0.contracts import ArtifactCandidate, RequestContext
from elpis_p0.factory import build_default_controller
from elpis_p0.semantic_space import (
    P0_ALLOWED_D4_ELEMENTS,
    P0_SEMANTIC_SPACE,
    P0_SEMANTIC_SPACE_DIGEST,
    P0_VALIDATOR_FAILURE_ROLE_BY_KEY,
    validator_failure_cell_index,
    validator_failure_role,
)
from elpis_reference.p0_validator_ingress import (
    bind_p0_validator_ingress_to_controller,
    build_p0_projection_trace,
)
from elpis_reference.projector_release import (
    MAX_RELEASE_CELLS_PER_TRAVERSAL,
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
        request_id="c2r6b-semantic-topology-e2e",
        prompt="write deterministic typed python solution and validate without imports",
        domain="python",
        entrypoint="solution",
        parameters=("x",),
    )
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    ingress = bind_p0_validator_ingress_to_controller(controller)
    result = controller.run(ctx)

    if result.accepted:
        raise RuntimeError("rejecting fixture unexpectedly accepted")
    if result.projection.semantic_space != P0_SEMANTIC_SPACE:
        raise RuntimeError("projection did not carry P0 semantic space")
    if result.projection.semantic_space_digest != P0_SEMANTIC_SPACE_DIGEST:
        raise RuntimeError("projection semantic-space digest mismatch")
    if P0_ALLOWED_D4_ELEMENTS != ("IDENTITY",):
        raise RuntimeError("P0 admitted a non-identity D4 semantic symmetry")
    if MAX_RELEASE_CELLS_PER_TRAVERSAL != 1:
        raise RuntimeError("release cardinality widened")

    authorized = controller.authorized_artifact_lineage(
        result, validator_index=0
    )
    trace = build_p0_projection_trace(
        projection_digest=result.projection.digest,
        grid81=result.projection.grid81,
        semantic_rows=result.projection.semantic_rows,
    )

    state = ClampState.empty(ctx.request_id)
    support_proposals = []
    binding_specs = []

    for validator_id, code in sorted(P0_VALIDATOR_FAILURE_ROLE_BY_KEY):
        role = validator_failure_role(validator_id, code)
        cell = validator_failure_cell_index(validator_id, code)
        if result.projection.grid81[cell] == 0:
            raise RuntimeError(f"repair locus is VOID: {role}")
        owner = "p0.validation.repair." + code.lower()
        support_proposals.append(
            ClampProposal(
                proposal_id="support-" + code.lower(),
                operation=ClampOperation.ASSERT,
                slot_id=owner,
                evidence_digest=trace.trace_digest,
                cell_index=cell,
                value=result.projection.grid81[cell],
            )
        )
        binding_specs.append((cell, owner, role))

    unrelated = next(
        cell for cell in range(0, 63) if result.projection.grid81[cell] != 0
    )
    support_proposals.append(
        ClampProposal(
            proposal_id="unrelated",
            operation=ClampOperation.ASSERT,
            slot_id="p0.unrelated.support",
            evidence_digest=trace.trace_digest,
            cell_index=unrelated,
            value=result.projection.grid81[unrelated],
        )
    )

    initial = apply_clamp_transaction(
        state=state,
        transaction=ClampTransaction(
            transaction_id="precommit-all-validator-repair-loci",
            episode_id=state.episode_id,
            expected_state_digest=state.digest(),
            proposals=tuple(support_proposals),
        ),
    )
    if not initial.accepted:
        raise RuntimeError("failed to precommit all validator repair loci")

    bindings = ReleaseBindingTableV1(
        episode_id=initial.state.episode_id,
        clamp_state_digest=initial.state.digest(),
        targets=tuple(
            ReleaseBindingTargetV1(
                cell_index=cell,
                owner=owner,
                locus_namespace=SEMANTIC_OBJECT,
                locus_identity=trace.semantic_digest_for_role(role),
            )
            for cell, owner, role in binding_specs
        ),
    )

    evidence = result.evidence[0]
    diagnostic = ingress.task_diagnostic_from_validator_failure(
        task_scope_id=ctx.request_id,
        frame_index=0,
        artifact_digest=result.artifact.digest,
        evidence=evidence,
        projection_trace=trace,
        authorized=authorized,
    )
    residual = diagnostic.to_task_residual()
    resolved = trace.reverse_trace_index().resolve(residual)

    target = validator_failure_cell_index(
        evidence.validator_id, evidence.code
    )
    if resolved.P7_cell_indices != (target,):
        raise RuntimeError(
            f"failure resolved to {resolved.P7_cell_indices}, expected {(target,)}"
        )

    plan, tx = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=initial.state,
        release_bindings=bindings,
    )
    if tx is None or plan.target_cells != (target,):
        raise RuntimeError("bounded release did not select exact failed sub-locus")

    released = apply_clamp_transaction(state=initial.state, transaction=tx)
    if not released.accepted:
        raise RuntimeError("canonical Projector rejected exact sub-locus release")

    for cell, _, _ in binding_specs:
        if cell == target:
            if bool(released.state.active_mask[cell]):
                raise RuntimeError("failed repair locus remained active")
        elif not bool(released.state.active_mask[cell]):
            raise RuntimeError("unrelated validator repair locus was released")
    if not bool(released.state.active_mask[unrelated]):
        raise RuntimeError("unrelated non-validator support was released")

    report = {
        "schema": "elpis.public-c2r6b-p0-semantic-topology.v1",
        "status": "PASS",
        "semantic_space": {
            "name": P0_SEMANTIC_SPACE,
            "digest": P0_SEMANTIC_SPACE_DIGEST,
            "allowed_d4_elements": list(P0_ALLOWED_D4_ELEMENTS),
        },
        "validator_failure": {
            "validator_id": evidence.validator_id,
            "code": evidence.code,
            "target_cell": target,
            "resolved_cells": list(resolved.P7_cell_indices),
            "active_repair_loci_before": len(binding_specs),
            "active_repair_loci_after": sum(
                bool(released.state.active_mask[cell])
                for cell, _, _ in binding_specs
            ),
        },
        "claims": {
            "p0_semantic_space_distinct_from_generic_structural_space": True,
            "p0_token_row_column_meaning_digest_bound": True,
            "p0_d4_semantic_stabilizer_identity_only": True,
            "validator_code_selects_predeclared_sublocus": True,
            "multi_active_validation_support_resolvable": True,
            "release_cap_remains_one": True,
            "controller_associated_ingress_authority_required": True,
            "external_lineage_authority_root": False,
            "semantic_decomposition_improved": False,
            "production_learned_reproposal": False,
            "runtime_admission": False,
        },
    }
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
