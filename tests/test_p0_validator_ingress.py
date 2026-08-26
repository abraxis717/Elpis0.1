from __future__ import annotations
import hashlib
from types import SimpleNamespace

import pytest
from DarwinianMatrix.projector.constraints import ClampOperation,ClampProposal,ClampState,ClampTransaction,apply_clamp_transaction
from elpis_p0.canonical import digest as p0_digest
from elpis_p0.contracts import RequestContext
from elpis_p0.projector import DeterministicPythonProjector
from elpis_p0.refinement_validation import RefinementValidationRecordV1
from elpis_runtime_r0.adapters import run_ast_validator_evidence
from elpis_reference.p0_validator_ingress import P0_ARTIFACT_PROPOSAL_LINEAGE_DOMAIN,P0_VALIDATION_SEMANTIC_ROW,P0_VALIDATOR_EVIDENCE_DOMAIN,P0ValidatorIngressContractError,build_p0_projection_trace,structural_diagnostic_from_p0_refinement_rejection,task_diagnostic_from_p0_validator_failure
from elpis_reference.projector_release import ReleaseBindingTableV1,ReleaseBindingTargetV1,build_release_transaction
from elpis_reference.semantic_refinement import SEMANTIC_OBJECT,STRUCTURAL_REJECTION,TASK_REJECTION,domain_digest

def h(s): return hashlib.sha256(s.encode()).hexdigest()
def projection():
    ctx=RequestContext(request_id="c2r5-p0",prompt="write deterministic typed python solution and validate without imports",domain="python",entrypoint="solution",parameters=("x",))
    return ctx,DeterministicPythonProjector().project(ctx)
def trace(p): return build_p0_projection_trace(projection_digest=p.digest,grid81=p.grid81,semantic_rows=p.semantic_rows)
def rejected(ctx):
    source="def solution(:\n    return 1\n"; digest,e=run_ast_validator_evidence(request_id=ctx.request_id,prompt=ctx.prompt,entrypoint=ctx.entrypoint,artifact_source=source); return source,digest,e
def evidence_digest(e):
    return domain_digest(P0_VALIDATOR_EVIDENCE_DOMAIN,{"code":e.code,"details":[[str(k),v] for k,v in e.details],"message":e.message,"passed":bool(e.passed),"validator_id":e.validator_id})
def lineage(ctx,p,digest,e,**overrides):
    payload={
        "artifact_digest":digest,
        "decoder_plan_digest":h("plan"),
        "p0_result_digest":h("result"),
        "projection_digest":p.digest,
        "request_id":ctx.request_id,
        "structural_proposal_digest":h("structural-proposal"),
        "validator_code":e.code,
        "validator_evidence_digest":evidence_digest(e),
        "validator_id":e.validator_id,
        "validator_index":0,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload,lineage_digest=domain_digest(P0_ARTIFACT_PROPOSAL_LINEAGE_DOMAIN,payload))

def test_real_validator_failure_binds_to_preexisting_validation_semantics():
    ctx,p=projection(); t=trace(p); source,digest,e=rejected(ctx)
    assert digest==p0_digest({"source":source}) and not e.passed and e.code=="SYNTAX_ERROR"
    ln=lineage(ctx,p,digest,e)
    d=task_diagnostic_from_p0_validator_failure(task_scope_id=ctx.request_id,frame_index=0,artifact_digest=digest,evidence=e,projection_trace=t,lineage=ln)
    assert d.diagnostic_class==TASK_REJECTION
    assert d.subject_digest==digest
    assert d.locus_namespace==SEMANTIC_OBJECT
    assert d.locus_identity==t.semantic_digest_for_row(P0_VALIDATION_SEMANTIC_ROW)
    assert set(d.payload())=={"details_digest","diagnostic_class","frame_index","locus_identity","locus_namespace","producer_id","reason_codes","subject_digest","task_scope_id"}

def test_projection_trace_resolves_validation_row_to_nine_prevalidation_cells():
    ctx,p=projection(); t=trace(p); _,digest,e=rejected(ctx)
    d=task_diagnostic_from_p0_validator_failure(task_scope_id=ctx.request_id,frame_index=0,artifact_digest=digest,evidence=e,projection_trace=t,lineage=lineage(ctx,p,digest,e))
    r=t.reverse_trace_index().resolve(d.to_task_residual())
    assert r.P7_cell_indices==tuple(range(63,72)) and len(r.trace_proof_digests)==9

def test_production_validator_releases_one_prebound_active_support_only():
    ctx,p=projection(); t=trace(p)
    validation_locus=t.semantic_digest_for_row(P0_VALIDATION_SEMANTIC_ROW)
    target=next(cell for cell in range(63,72) if p.grid81[cell]!=0)
    unrelated=next(cell for cell in range(0,63) if p.grid81[cell]!=0)
    state=ClampState.empty(ctx.request_id)
    props=(ClampProposal(proposal_id="validation-support",operation=ClampOperation.ASSERT,slot_id="p0.validation.support",evidence_digest=t.trace_digest,cell_index=target,value=p.grid81[target]),ClampProposal(proposal_id="unrelated",operation=ClampOperation.ASSERT,slot_id="p0.unrelated.support",evidence_digest=t.trace_digest,cell_index=unrelated,value=p.grid81[unrelated]))
    initial=apply_clamp_transaction(state=state,transaction=ClampTransaction(transaction_id="support",episode_id=state.episode_id,expected_state_digest=state.digest(),proposals=props)); assert initial.accepted
    bindings=ReleaseBindingTableV1(episode_id=initial.state.episode_id,clamp_state_digest=initial.state.digest(),targets=(ReleaseBindingTargetV1(cell_index=target,owner="p0.validation.support",locus_namespace=SEMANTIC_OBJECT,locus_identity=validation_locus),))
    _,digest,e=rejected(ctx)
    d=task_diagnostic_from_p0_validator_failure(task_scope_id=ctx.request_id,frame_index=0,artifact_digest=digest,evidence=e,projection_trace=t,lineage=lineage(ctx,p,digest,e))
    residual=d.to_task_residual(); resolved=t.reverse_trace_index().resolve(residual)
    plan,tx=build_release_transaction(residual=residual,resolved=resolved,clamp_state=initial.state,release_bindings=bindings)
    assert plan.target_cells==(target,) and tx is not None
    released=apply_clamp_transaction(state=initial.state,transaction=tx); assert released.accepted
    assert not bool(released.state.active_mask[target]) and bool(released.state.active_mask[unrelated])

def test_structural_scope_rejection_stays_structural():
    ctx,p=projection(); t=trace(p)
    v=RefinementValidationRecordV1(envelope_digest=h("env"),proposal_digest=h("proposal"),transition_kind="LOCKED_CELL_WRITE",changed_cells=(63,),scope_validity="FAIL",status="REJECTED_P0_REFINEMENT_LOCKED_CELL_WRITE")
    d=structural_diagnostic_from_p0_refinement_rejection(task_scope_id=ctx.request_id,frame_index=0,validation=v,projection_trace=t)
    assert d.diagnostic_class==STRUCTURAL_REJECTION
    with pytest.raises(ValueError,match="structural rejection cannot become a task residual"): d.to_task_residual()

def test_passed_validator_evidence_cannot_enter_rejection_path():
    ctx,p=projection(); t=trace(p); source="def solution(x):\n    return x + 1\n"; digest,e=run_ast_validator_evidence(request_id=ctx.request_id,prompt=ctx.prompt,entrypoint=ctx.entrypoint,artifact_source=source); assert e.passed
    with pytest.raises(ValueError,match="validator evidence must be a rejection"):
        task_diagnostic_from_p0_validator_failure(task_scope_id=ctx.request_id,frame_index=0,artifact_digest=digest,evidence=e,projection_trace=t,lineage=lineage(ctx,p,digest,e))

def test_artifact_must_match_lineage_before_diagnostic():
    ctx,p=projection(); t=trace(p); _,digest,e=rejected(ctx)
    bad=lineage(ctx,p,digest,e,artifact_digest=h("other-artifact"))
    with pytest.raises(ValueError,match="artifact digest does not match P0 lineage"):
        task_diagnostic_from_p0_validator_failure(task_scope_id=ctx.request_id,frame_index=0,artifact_digest=digest,evidence=e,projection_trace=t,lineage=bad)

def test_projection_must_match_lineage_before_diagnostic():
    ctx,p=projection(); t=trace(p); _,digest,e=rejected(ctx)
    bad=lineage(ctx,p,digest,e,projection_digest=h("other-projection"))
    with pytest.raises(ValueError,match="projection trace does not match P0 lineage"):
        task_diagnostic_from_p0_validator_failure(task_scope_id=ctx.request_id,frame_index=0,artifact_digest=digest,evidence=e,projection_trace=t,lineage=bad)

def test_lineage_digest_tamper_fails_closed():
    ctx,p=projection(); t=trace(p); _,digest,e=rejected(ctx)
    ln=lineage(ctx,p,digest,e)
    bad=SimpleNamespace(**{**ln.__dict__,"lineage_digest":"0"*64})
    with pytest.raises(ValueError,match="P0 artifact/proposal lineage digest mismatch"):
        task_diagnostic_from_p0_validator_failure(task_scope_id=ctx.request_id,frame_index=0,artifact_digest=digest,evidence=e,projection_trace=t,lineage=bad)

def test_exact_validator_evidence_payload_must_match_lineage():
    ctx,p=projection(); t=trace(p); _,digest,e=rejected(ctx)
    good=lineage(ctx,p,digest,e)
    bad=SimpleNamespace(validator_id=e.validator_id,passed=e.passed,code=e.code,message=e.message+" tampered",details=e.details)
    with pytest.raises(ValueError,match="validator evidence payload does not match P0 lineage"):
        task_diagnostic_from_p0_validator_failure(task_scope_id=ctx.request_id,frame_index=0,artifact_digest=digest,evidence=bad,projection_trace=t,lineage=good)


def test_noncanonical_validator_details_raise_typed_ingress_error():
    ctx,p=projection(); t=trace(p); _,digest,e=rejected(ctx)
    good=lineage(ctx,p,digest,e)
    bad=SimpleNamespace(
        validator_id=e.validator_id,
        passed=e.passed,
        code=e.code,
        message=e.message,
        details=(("opaque", object()),),
    )
    with pytest.raises(P0ValidatorIngressContractError,match="not canonical JSON data"):
        task_diagnostic_from_p0_validator_failure(
            task_scope_id=ctx.request_id,
            frame_index=0,
            artifact_digest=digest,
            evidence=bad,
            projection_trace=t,
            lineage=good,
        )
