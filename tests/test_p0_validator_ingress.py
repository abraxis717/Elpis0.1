from __future__ import annotations

from dataclasses import replace
import inspect
from types import SimpleNamespace

import pytest

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
from elpis_p0.lineage_authority import (
    P0AuthorizedArtifactLineageV1,
    P0LineageAuthorityError,
    P0LineageAuthorityReceiptV1,
    RECEIPT_DOMAIN,
    _domain_digest as authority_domain_digest,
)
from elpis_p0.semantic_space import (
    P0_VALIDATOR_FAILURE_ROLE_BY_KEY,
    validator_failure_cell_index,
    validator_failure_role,
)
from elpis_reference import p0_validator_ingress as ingress_module
from elpis_reference.p0_validator_ingress import (
    P0ValidatorIngressContractError,
    P0ValidatorIngressV1,
    bind_p0_validator_ingress_to_controller,
    build_p0_projection_trace,
    structural_diagnostic_from_p0_refinement_rejection,
    validator_failure_locus_from_p0_evidence,
)
from elpis_reference.projector_release import (
    ReleaseBindingTableV1,
    ReleaseBindingTargetV1,
    build_release_transaction,
)
from elpis_reference.semantic_refinement import (
    SEMANTIC_OBJECT,
    STRUCTURAL_REJECTION,
)
from elpis_p0.refinement_validation import RefinementValidationRecordV1


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


def make_context(request_id="c2r6cb-ingress"):
    return RequestContext(
        request_id=request_id,
        prompt="write deterministic typed python solution and validate without imports",
        domain="python",
        entrypoint="solution",
        parameters=("x",),
    )


def rejected(request_id="c2r6cb-ingress"):
    controller = build_default_controller()
    controller.decoder = RejectingDecoder()
    result = controller.run(make_context(request_id))
    assert not result.accepted
    authorized = controller.authorized_artifact_lineage(
        result, validator_index=0
    )
    ingress = bind_p0_validator_ingress_to_controller(controller)
    trace = build_p0_projection_trace(
        projection_digest=result.projection.digest,
        grid81=result.projection.grid81,
        semantic_rows=result.projection.semantic_rows,
    )
    return controller, ingress, result, authorized, trace


def diagnose(ingress, result, authorized, trace, *, evidence=None):
    return ingress.task_diagnostic_from_validator_failure(
        task_scope_id=result.request_id,
        frame_index=0,
        artifact_digest=result.artifact.digest,
        evidence=result.evidence[0] if evidence is None else evidence,
        projection_trace=trace,
        authorized=authorized,
    )


def test_legacy_bare_lineage_production_entrypoint_removed():
    assert not hasattr(
        ingress_module, "task_diagnostic_from_p0_validator_failure"
    )


def test_per_request_ingress_has_no_authority_selector():
    names = set(
        inspect.signature(
            P0ValidatorIngressV1.task_diagnostic_from_validator_failure
        ).parameters
    )
    assert "authorized" in names
    assert not names.intersection(
        {"controller", "verifier", "authority", "authority_consumer", "consume"}
    )


def test_ingress_requires_trusted_composition_binding():
    with pytest.raises(TypeError, match="trusted composition"):
        P0ValidatorIngressV1()
    with pytest.raises(
        P0ValidatorIngressContractError, match="exact P0Controller"
    ):
        bind_p0_validator_ingress_to_controller(object())


def test_valid_authorization_consumes_once():
    _, ingress, result, authorized, trace = rejected()
    diagnostic = diagnose(ingress, result, authorized, trace)
    assert diagnostic.subject_digest == result.artifact.digest
    with pytest.raises(P0LineageAuthorityError, match="not active"):
        diagnose(ingress, result, authorized, trace)


def test_cross_controller_authorization_rejects_without_burning_real_capability():
    _, ingress_a, result_a, authorized_a, trace_a = rejected("c2r6cb-a")
    controller_b = build_default_controller()
    ingress_b = bind_p0_validator_ingress_to_controller(controller_b)
    with pytest.raises(
        P0LineageAuthorityError, match="another authority instance"
    ):
        diagnose(ingress_b, result_a, authorized_a, trace_a)
    assert diagnose(
        ingress_a, result_a, authorized_a, trace_a
    ).subject_digest == result_a.artifact.digest


def test_unsupported_code_rejects_before_consumption():
    _, ingress, result, authorized, trace = rejected()
    bad = replace(result.evidence[0], code="UNKNOWN_FAILURE")
    with pytest.raises(
        P0ValidatorIngressContractError,
        match="unsupported P0 validator failure locus",
    ):
        diagnose(
            ingress, result, authorized, trace, evidence=bad
        )
    diagnose(ingress, result, authorized, trace)


def test_passed_evidence_rejects_before_consumption():
    _, ingress, result, authorized, trace = rejected()
    bad = replace(result.evidence[0], passed=True)
    with pytest.raises(
        ValueError, match="validator evidence must be a rejection"
    ):
        diagnose(
            ingress, result, authorized, trace, evidence=bad
        )
    diagnose(ingress, result, authorized, trace)


def test_lineage_mismatch_rejects_before_consumption():
    _, ingress, result, authorized, trace = rejected()
    bad = replace(
        authorized,
        lineage=replace(
            authorized.lineage,
            artifact_digest="0" * 64,
        ),
    )
    with pytest.raises(
        ValueError, match="artifact digest does not match P0 lineage"
    ):
        diagnose(ingress, result, bad, trace)
    diagnose(ingress, result, authorized, trace)


def test_receipt_lineage_substitution_rejected():
    _, ingress_a, result_a, authorized_a, trace_a = rejected("c2r6cb-sub-a")
    _, _, _, authorized_b, _ = rejected("c2r6cb-sub-b")
    substituted = P0AuthorizedArtifactLineageV1(
        lineage=authorized_a.lineage,
        receipt=authorized_b.receipt,
    )
    with pytest.raises(P0LineageAuthorityError):
        diagnose(ingress_a, result_a, substituted, trace_a)
    diagnose(ingress_a, result_a, authorized_a, trace_a)


def test_self_consistent_unissued_receipt_rejected():
    _, ingress, result, authorized, trace = rejected()
    receipt = authorized.receipt
    base = {
        "authority_instance_id": receipt.authority_instance_id,
        "capability_id": "a" * 64,
        "issuance_sequence": 999,
        "lineage_digest": authorized.lineage.lineage_digest,
        "p0_result_digest": authorized.lineage.p0_result_digest,
        "request_id": authorized.lineage.request_id,
        "validator_evidence_digest": (
            authorized.lineage.validator_evidence_digest
        ),
        "validator_index": authorized.lineage.validator_index,
    }
    fake_receipt = P0LineageAuthorityReceiptV1(
        **base,
        receipt_digest=authority_domain_digest(
            RECEIPT_DOMAIN, base
        ),
    )
    fake = P0AuthorizedArtifactLineageV1(
        lineage=authorized.lineage,
        receipt=fake_receipt,
    )
    with pytest.raises(P0LineageAuthorityError, match="not active"):
        diagnose(ingress, result, fake, trace)
    diagnose(ingress, result, authorized, trace)


def test_supported_validator_failure_loci_remain_six_distinct_cells():
    _, _, _, _, trace = rejected()
    cells = []
    for validator_id, code in sorted(P0_VALIDATOR_FAILURE_ROLE_BY_KEY):
        evidence = SimpleNamespace(
            validator_id=validator_id,
            passed=False,
            code=code,
            message="synthetic",
            details=(),
        )
        role, locus = validator_failure_locus_from_p0_evidence(
            evidence=evidence,
            projection_trace=trace,
        )
        assert role == validator_failure_role(validator_id, code)
        assert locus == trace.semantic_digest_for_role(role)
        cells.append(
            validator_failure_cell_index(validator_id, code)
        )
    assert len(cells) == len(set(cells)) == 6


def test_authorized_failure_still_releases_exactly_one_prebound_cell():
    _, ingress, result, authorized, trace = rejected()
    evidence = result.evidence[0]
    role = validator_failure_role(
        evidence.validator_id, evidence.code
    )
    target = validator_failure_cell_index(
        evidence.validator_id, evidence.code
    )
    unrelated = next(
        cell
        for cell in range(0, 63)
        if result.projection.grid81[cell] != 0
    )

    state = ClampState.empty(result.request_id)
    initial = apply_clamp_transaction(
        state=state,
        transaction=ClampTransaction(
            transaction_id="c2r6cb-support",
            episode_id=state.episode_id,
            expected_state_digest=state.digest(),
            proposals=(
                ClampProposal(
                    proposal_id="target",
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
    assert initial.accepted
    bindings = ReleaseBindingTableV1(
        episode_id=initial.state.episode_id,
        clamp_state_digest=initial.state.digest(),
        targets=(
            ReleaseBindingTargetV1(
                cell_index=target,
                owner="p0.validation.support",
                locus_namespace=SEMANTIC_OBJECT,
                locus_identity=trace.semantic_digest_for_role(role),
            ),
        ),
    )
    residual = diagnose(
        ingress, result, authorized, trace
    ).to_task_residual()
    resolved = trace.reverse_trace_index().resolve(residual)
    assert resolved.P7_cell_indices == (target,)
    plan, transaction = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=initial.state,
        release_bindings=bindings,
    )
    assert transaction is not None
    assert plan.target_cells == (target,)
    released = apply_clamp_transaction(
        state=initial.state, transaction=transaction
    )
    assert released.accepted
    assert not bool(released.state.active_mask[target])
    assert bool(released.state.active_mask[unrelated])


def test_structural_rejection_path_remains_non_task():
    _, _, result, _, trace = rejected()
    validation = RefinementValidationRecordV1(
        envelope_digest="1" * 64,
        proposal_digest="2" * 64,
        transition_kind="LOCKED_CELL_WRITE",
        changed_cells=(63,),
        scope_validity="FAIL",
        status="REJECTED_P0_REFINEMENT_LOCKED_CELL_WRITE",
    )
    diagnostic = structural_diagnostic_from_p0_refinement_rejection(
        task_scope_id=result.request_id,
        frame_index=0,
        validation=validation,
        projection_trace=trace,
    )
    assert diagnostic.diagnostic_class == STRUCTURAL_REJECTION
