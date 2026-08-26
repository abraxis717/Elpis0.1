from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from DarwinianMatrix.projector.constraints import (
    ClampOperation,
    ClampProposal,
    ClampState,
    ClampTransaction,
    apply_clamp_transaction,
)
from elpis_p0.canonical import digest as p0_digest
from elpis_p0.contracts import RequestContext
from elpis_p0.projector import DeterministicPythonProjector
from elpis_p0.refinement_validation import RefinementValidationRecordV1
from elpis_p0.semantic_space import (
    P0_VALIDATOR_FAILURE_ROLE_BY_KEY,
    validator_failure_cell_index,
    validator_failure_role,
)
from elpis_runtime_r0.adapters import run_ast_validator_evidence
from elpis_reference.p0_validator_ingress import (
    P0_ARTIFACT_PROPOSAL_LINEAGE_DOMAIN,
    P0_VALIDATION_SEMANTIC_ROW,
    P0_VALIDATOR_EVIDENCE_DOMAIN,
    P0ValidatorIngressContractError,
    build_p0_projection_trace,
    structural_diagnostic_from_p0_refinement_rejection,
    task_diagnostic_from_p0_validator_failure,
)
from elpis_reference.projector_release import (
    ReleaseBindingTableV1,
    ReleaseBindingTargetV1,
    build_release_transaction,
)
from elpis_reference.semantic_refinement import (
    SEMANTIC_OBJECT,
    STRUCTURAL_REJECTION,
    TASK_REJECTION,
    domain_digest,
)


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def projection():
    ctx = RequestContext(
        request_id="c2r6b-p0",
        prompt="write deterministic typed python solution and validate without imports",
        domain="python",
        entrypoint="solution",
        parameters=("x",),
    )
    return ctx, DeterministicPythonProjector().project(ctx)


def trace(p):
    return build_p0_projection_trace(
        projection_digest=p.digest,
        grid81=p.grid81,
        semantic_rows=p.semantic_rows,
    )


def rejected(ctx):
    source = "def solution(:\n    return 1\n"
    digest, evidence = run_ast_validator_evidence(
        request_id=ctx.request_id,
        prompt=ctx.prompt,
        entrypoint=ctx.entrypoint,
        artifact_source=source,
    )
    return source, digest, evidence


def evidence_digest(evidence):
    return domain_digest(
        P0_VALIDATOR_EVIDENCE_DOMAIN,
        {
            "code": evidence.code,
            "details": [[str(k), v] for k, v in evidence.details],
            "message": evidence.message,
            "passed": bool(evidence.passed),
            "validator_id": evidence.validator_id,
        },
    )


def lineage(ctx, p, digest, evidence, **overrides):
    payload = {
        "artifact_digest": digest,
        "decoder_plan_digest": h("plan"),
        "p0_result_digest": h("result"),
        "projection_digest": p.digest,
        "request_id": ctx.request_id,
        "structural_proposal_digest": h("structural-proposal"),
        "validator_code": evidence.code,
        "validator_evidence_digest": evidence_digest(evidence),
        "validator_id": evidence.validator_id,
        "validator_index": 0,
    }
    payload.update(overrides)
    return SimpleNamespace(
        **payload,
        lineage_digest=domain_digest(
            P0_ARTIFACT_PROPOSAL_LINEAGE_DOMAIN,
            payload,
        ),
    )


def synthetic_evidence(code: str):
    return SimpleNamespace(
        validator_id="python.ast.v1",
        passed=False,
        code=code,
        message=f"synthetic {code}",
        details=(),
    )


def test_real_validator_failure_binds_to_preexisting_repair_sublocus():
    ctx, p = projection()
    t = trace(p)
    source, digest, evidence = rejected(ctx)
    assert digest == p0_digest({"source": source})
    assert not evidence.passed
    assert evidence.code == "SYNTAX_ERROR"

    diagnostic = task_diagnostic_from_p0_validator_failure(
        task_scope_id=ctx.request_id,
        frame_index=0,
        artifact_digest=digest,
        evidence=evidence,
        projection_trace=t,
        lineage=lineage(ctx, p, digest, evidence),
    )
    role = validator_failure_role(evidence.validator_id, evidence.code)
    assert diagnostic.diagnostic_class == TASK_REJECTION
    assert diagnostic.subject_digest == digest
    assert diagnostic.locus_namespace == SEMANTIC_OBJECT
    assert diagnostic.locus_identity == t.semantic_digest_for_role(role)


def test_each_supported_validator_failure_resolves_exactly_one_distinct_cell():
    ctx, p = projection()
    t = trace(p)
    cells = []
    for validator_id, code in sorted(P0_VALIDATOR_FAILURE_ROLE_BY_KEY):
        evidence = synthetic_evidence(code)
        artifact_digest = h("artifact-" + code)
        diagnostic = task_diagnostic_from_p0_validator_failure(
            task_scope_id=ctx.request_id,
            frame_index=0,
            artifact_digest=artifact_digest,
            evidence=evidence,
            projection_trace=t,
            lineage=lineage(ctx, p, artifact_digest, evidence),
        )
        resolved = t.reverse_trace_index().resolve(
            diagnostic.to_task_residual()
        )
        expected = validator_failure_cell_index(validator_id, code)
        assert resolved.P7_cell_indices == (expected,)
        assert len(resolved.trace_proof_digests) == 1
        cells.append(expected)
    assert len(cells) == len(set(cells)) == 6


def test_multi_active_validation_support_still_releases_only_failed_sublocus():
    ctx, p = projection()
    t = trace(p)

    state = ClampState.empty(ctx.request_id)
    proposals = []
    bindings = []

    for validator_id, code in sorted(P0_VALIDATOR_FAILURE_ROLE_BY_KEY):
        role = validator_failure_role(validator_id, code)
        cell = validator_failure_cell_index(validator_id, code)
        owner = "p0.validation.repair." + code.lower()
        proposals.append(
            ClampProposal(
                proposal_id="support-" + code.lower(),
                operation=ClampOperation.ASSERT,
                slot_id=owner,
                evidence_digest=t.trace_digest,
                cell_index=cell,
                value=p.grid81[cell],
            )
        )

    unrelated = next(
        cell for cell in range(0, 63) if p.grid81[cell] != 0
    )
    proposals.append(
        ClampProposal(
            proposal_id="unrelated",
            operation=ClampOperation.ASSERT,
            slot_id="p0.unrelated.support",
            evidence_digest=t.trace_digest,
            cell_index=unrelated,
            value=p.grid81[unrelated],
        )
    )

    initial = apply_clamp_transaction(
        state=state,
        transaction=ClampTransaction(
            transaction_id="all-validation-repair-support",
            episode_id=state.episode_id,
            expected_state_digest=state.digest(),
            proposals=tuple(proposals),
        ),
    )
    assert initial.accepted

    for validator_id, code in sorted(P0_VALIDATOR_FAILURE_ROLE_BY_KEY):
        role = validator_failure_role(validator_id, code)
        cell = validator_failure_cell_index(validator_id, code)
        bindings.append(
            ReleaseBindingTargetV1(
                cell_index=cell,
                owner="p0.validation.repair." + code.lower(),
                locus_namespace=SEMANTIC_OBJECT,
                locus_identity=t.semantic_digest_for_role(role),
            )
        )

    table = ReleaseBindingTableV1(
        episode_id=initial.state.episode_id,
        clamp_state_digest=initial.state.digest(),
        targets=tuple(bindings),
    )

    _, digest, evidence = rejected(ctx)
    diagnostic = task_diagnostic_from_p0_validator_failure(
        task_scope_id=ctx.request_id,
        frame_index=0,
        artifact_digest=digest,
        evidence=evidence,
        projection_trace=t,
        lineage=lineage(ctx, p, digest, evidence),
    )
    residual = diagnostic.to_task_residual()
    resolved = t.reverse_trace_index().resolve(residual)

    syntax_cell = validator_failure_cell_index(
        evidence.validator_id, evidence.code
    )
    assert resolved.P7_cell_indices == (syntax_cell,)

    plan, tx = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=initial.state,
        release_bindings=table,
    )
    assert plan.target_cells == (syntax_cell,)
    assert tx is not None

    released = apply_clamp_transaction(
        state=initial.state,
        transaction=tx,
    )
    assert released.accepted
    assert not bool(released.state.active_mask[syntax_cell])
    assert bool(released.state.active_mask[unrelated])

    for validator_id, code in sorted(P0_VALIDATOR_FAILURE_ROLE_BY_KEY):
        cell = validator_failure_cell_index(validator_id, code)
        if cell != syntax_cell:
            assert bool(released.state.active_mask[cell])


def test_unknown_validator_code_fails_closed_before_locus_selection():
    ctx, p = projection()
    t = trace(p)
    evidence = synthetic_evidence("UNKNOWN_FAILURE")
    artifact_digest = h("unknown-artifact")
    with pytest.raises(
        P0ValidatorIngressContractError,
        match="unsupported P0 validator failure locus",
    ):
        task_diagnostic_from_p0_validator_failure(
            task_scope_id=ctx.request_id,
            frame_index=0,
            artifact_digest=artifact_digest,
            evidence=evidence,
            projection_trace=t,
            lineage=lineage(ctx, p, artifact_digest, evidence),
        )


def test_structural_scope_rejection_stays_structural():
    ctx, p = projection()
    t = trace(p)
    validation = RefinementValidationRecordV1(
        envelope_digest=h("env"),
        proposal_digest=h("proposal"),
        transition_kind="LOCKED_CELL_WRITE",
        changed_cells=(63,),
        scope_validity="FAIL",
        status="REJECTED_P0_REFINEMENT_LOCKED_CELL_WRITE",
    )
    diagnostic = structural_diagnostic_from_p0_refinement_rejection(
        task_scope_id=ctx.request_id,
        frame_index=0,
        validation=validation,
        projection_trace=t,
    )
    assert diagnostic.diagnostic_class == STRUCTURAL_REJECTION
    assert diagnostic.locus_identity == t.semantic_digest_for_row(
        P0_VALIDATION_SEMANTIC_ROW
    )
    with pytest.raises(
        ValueError,
        match="structural rejection cannot become a task residual",
    ):
        diagnostic.to_task_residual()


def test_passed_validator_evidence_cannot_enter_rejection_path():
    ctx, p = projection()
    t = trace(p)
    source = "def solution(x):\n    return x + 1\n"
    digest, evidence = run_ast_validator_evidence(
        request_id=ctx.request_id,
        prompt=ctx.prompt,
        entrypoint=ctx.entrypoint,
        artifact_source=source,
    )
    assert evidence.passed
    with pytest.raises(
        ValueError, match="validator evidence must be a rejection"
    ):
        task_diagnostic_from_p0_validator_failure(
            task_scope_id=ctx.request_id,
            frame_index=0,
            artifact_digest=digest,
            evidence=evidence,
            projection_trace=t,
            lineage=lineage(ctx, p, digest, evidence),
        )


def test_artifact_must_match_lineage_before_diagnostic():
    ctx, p = projection()
    t = trace(p)
    _, digest, evidence = rejected(ctx)
    bad = lineage(
        ctx, p, digest, evidence, artifact_digest=h("other-artifact")
    )
    with pytest.raises(
        ValueError, match="artifact digest does not match P0 lineage"
    ):
        task_diagnostic_from_p0_validator_failure(
            task_scope_id=ctx.request_id,
            frame_index=0,
            artifact_digest=digest,
            evidence=evidence,
            projection_trace=t,
            lineage=bad,
        )


def test_projection_must_match_lineage_before_diagnostic():
    ctx, p = projection()
    t = trace(p)
    _, digest, evidence = rejected(ctx)
    bad = lineage(
        ctx, p, digest, evidence, projection_digest=h("other-projection")
    )
    with pytest.raises(
        ValueError, match="projection trace does not match P0 lineage"
    ):
        task_diagnostic_from_p0_validator_failure(
            task_scope_id=ctx.request_id,
            frame_index=0,
            artifact_digest=digest,
            evidence=evidence,
            projection_trace=t,
            lineage=bad,
        )


def test_lineage_digest_tamper_fails_closed():
    ctx, p = projection()
    t = trace(p)
    _, digest, evidence = rejected(ctx)
    good = lineage(ctx, p, digest, evidence)
    bad = SimpleNamespace(
        **{**good.__dict__, "lineage_digest": "0" * 64}
    )
    with pytest.raises(
        ValueError, match="P0 artifact/proposal lineage digest mismatch"
    ):
        task_diagnostic_from_p0_validator_failure(
            task_scope_id=ctx.request_id,
            frame_index=0,
            artifact_digest=digest,
            evidence=evidence,
            projection_trace=t,
            lineage=bad,
        )


def test_exact_validator_evidence_payload_must_match_lineage():
    ctx, p = projection()
    t = trace(p)
    _, digest, evidence = rejected(ctx)
    good = lineage(ctx, p, digest, evidence)
    bad = SimpleNamespace(
        validator_id=evidence.validator_id,
        passed=evidence.passed,
        code=evidence.code,
        message=evidence.message + " tampered",
        details=evidence.details,
    )
    with pytest.raises(
        ValueError, match="validator evidence payload does not match P0 lineage"
    ):
        task_diagnostic_from_p0_validator_failure(
            task_scope_id=ctx.request_id,
            frame_index=0,
            artifact_digest=digest,
            evidence=bad,
            projection_trace=t,
            lineage=good,
        )


def test_noncanonical_validator_details_raise_typed_ingress_error():
    ctx, p = projection()
    t = trace(p)
    _, digest, evidence = rejected(ctx)
    good = lineage(ctx, p, digest, evidence)
    bad = SimpleNamespace(
        validator_id=evidence.validator_id,
        passed=evidence.passed,
        code=evidence.code,
        message=evidence.message,
        details=(("opaque", object()),),
    )
    with pytest.raises(
        P0ValidatorIngressContractError,
        match="not canonical JSON data",
    ):
        task_diagnostic_from_p0_validator_failure(
            task_scope_id=ctx.request_id,
            frame_index=0,
            artifact_digest=digest,
            evidence=bad,
            projection_trace=t,
            lineage=good,
        )
