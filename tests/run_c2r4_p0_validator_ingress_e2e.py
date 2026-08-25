from __future__ import annotations
import json
from DarwinianMatrix.projector.constraints import ClampOperation,ClampProposal,ClampState,ClampTransaction,apply_clamp_transaction
from elpis_p0.contracts import RequestContext
from elpis_p0.projector import DeterministicPythonProjector
from elpis_runtime_r0.adapters import run_ast_validator_evidence
from elpis_reference.p0_validator_ingress import P0_VALIDATION_SEMANTIC_ROW,build_p0_projection_trace,task_diagnostic_from_p0_validator_failure
from elpis_reference.projector_release import ReleaseBindingTableV1,ReleaseBindingTargetV1,build_release_transaction
from elpis_reference.semantic_refinement import SEMANTIC_OBJECT

def main():
    ctx=RequestContext(request_id="c2r4-production-validator-e2e",prompt="write deterministic typed python solution and validate without imports",domain="python",entrypoint="solution",parameters=("x",))
    projection=DeterministicPythonProjector().project(ctx)
    trace=build_p0_projection_trace(projection_digest=projection.digest,grid81=projection.grid81,semantic_rows=projection.semantic_rows)
    target=next(c for c in range(63,72) if projection.grid81[c]!=0); unrelated=next(c for c in range(0,63) if projection.grid81[c]!=0)
    state=ClampState.empty(ctx.request_id)
    initial=apply_clamp_transaction(state=state,transaction=ClampTransaction(transaction_id="prevalidation-support",episode_id=state.episode_id,expected_state_digest=state.digest(),proposals=(ClampProposal(proposal_id="validation",operation=ClampOperation.ASSERT,slot_id="p0.validation.support",evidence_digest=trace.trace_digest,cell_index=target,value=projection.grid81[target]),ClampProposal(proposal_id="unrelated",operation=ClampOperation.ASSERT,slot_id="p0.unrelated.support",evidence_digest=trace.trace_digest,cell_index=unrelated,value=projection.grid81[unrelated]))));
    if not initial.accepted: raise RuntimeError("support assertion failed")
    locus=trace.semantic_digest_for_row(P0_VALIDATION_SEMANTIC_ROW)
    bindings=ReleaseBindingTableV1(episode_id=initial.state.episode_id,clamp_state_digest=initial.state.digest(),targets=(ReleaseBindingTargetV1(cell_index=target,owner="p0.validation.support",locus_namespace=SEMANTIC_OBJECT,locus_identity=locus),))
    artifact="def solution(:\n    return 1\n"; artifact_digest,evidence=run_ast_validator_evidence(request_id=ctx.request_id,prompt=ctx.prompt,entrypoint=ctx.entrypoint,artifact_source=artifact)
    if evidence.passed: raise RuntimeError("fixture unexpectedly passed")
    diagnostic=task_diagnostic_from_p0_validator_failure(task_scope_id=ctx.request_id,frame_index=0,artifact_digest=artifact_digest,evidence=evidence,projection_trace=trace)
    residual=diagnostic.to_task_residual(); resolved=trace.reverse_trace_index().resolve(residual)
    plan,tx=build_release_transaction(residual=residual,resolved=resolved,clamp_state=initial.state,release_bindings=bindings)
    if tx is None or plan.target_cells!=(target,): raise RuntimeError("release was not exactly one prebound cell")
    released=apply_clamp_transaction(state=initial.state,transaction=tx)
    if not released.accepted or not bool(released.state.active_mask[unrelated]): raise RuntimeError("canonical release violated unrelated support")
    report={"schema":"elpis.public-c2r4-production-validator-ingress.v2","status":"PASS","validator":{"id":evidence.validator_id,"code":evidence.code,"artifact_digest":artifact_digest},"trace":{"created_before_validator":True,"trace_digest":trace.trace_digest,"semantic_locus":locus,"resolved_cells":list(resolved.P7_cell_indices)},"release":{"binding_table_digest":bindings.binding_table_digest,"target_cells":list(plan.target_cells),"cardinality":len(plan.target_cells),"unrelated_support_preserved":bool(released.state.active_mask[unrelated])},"claims":{"production_validator_ingress":True,"production_prevalidation_trace_binding":True,"single_cell_bound_release":len(plan.target_cells)==1,"cryptographic_trace_attestation":False,"production_learned_reproposal":False,"runtime_admission":False}}
    print(json.dumps(report,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
