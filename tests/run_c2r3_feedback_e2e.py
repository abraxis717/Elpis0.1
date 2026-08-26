from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from DarwinianMatrix.projector.constraints import (
    ClampOperation, ClampProposal, ClampState, ClampTransaction, apply_clamp_transaction,
)
from elpis_reference.feedback_refinement import FEEDBACK_REPROPOSED, execute_samsung_feedback_step, samsung_proposal_digest
from elpis_reference.projector_release import ReleaseBindingTableV1, ReleaseBindingTargetV1
from elpis_reference.semantic_refinement import SEMANTIC_OBJECT, TASK_REJECTION, ReverseTraceIndex, StructuralObservationRecord, TaskDiagnosticV1
from elpis_reference.sudoku import parse_puzzle, validate

FIXTURE_SOLUTION_TEXT=("534678912672195348198342567859761423426853791713924856" "961537284287419635345286179")
FIXTURE_SOLUTION=parse_puzzle(FIXTURE_SOLUTION_TEXT)

def h(text): return hashlib.sha256(text.encode()).hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--model",type=Path,required=True); ap.add_argument("--device",default="cpu"); args=ap.parse_args()
    one_blank=parse_puzzle("."+FIXTURE_SOLUTION_TEXT[1:])
    state=ClampState.empty("c2r4-reference-e2e")
    hypothesis_owner="c2r4-fixture-derived-hypothesis"
    assertions=[]
    for cell,value in enumerate(FIXTURE_SOLUTION):
        owner=hypothesis_owner if cell==0 else "c2r4-immutable-puzzle-givens"
        assertions.append(ClampProposal(
            proposal_id=f"support-{cell:02d}", operation=ClampOperation.ASSERT,
            slot_id=owner, evidence_digest=h(f"fixture-support-{cell}"),
            cell_index=cell, value=value,
        ))
    initial=apply_clamp_transaction(state=state, transaction=ClampTransaction(
        transaction_id="initial-support", episode_id=state.episode_id,
        expected_state_digest=state.digest(), proposals=tuple(assertions),
    ))
    if not initial.accepted: raise RuntimeError("canonical Projector rejected fixture support")
    state0=initial.state
    semantic=h("c2r4-fixture-derived-hypothesis-locus")
    observation=StructuralObservationRecord.create(
        source_semantic_object_digest=semantic, topology_vertex_digest=h("topology-0"),
        P7_capsule_digest=h("capsule-0"), P7_primary_cell_index=0,
    )
    bindings=ReleaseBindingTableV1(
        episode_id=state0.episode_id, clamp_state_digest=state0.digest(),
        targets=(ReleaseBindingTargetV1(cell_index=0, owner=hypothesis_owner,
            locus_namespace=SEMANTIC_OBJECT, locus_identity=semantic),),
    )
    diagnostic=TaskDiagnosticV1(
        diagnostic_class=TASK_REJECTION, task_scope_id=state0.episode_id, frame_index=0,
        subject_digest=samsung_proposal_digest(FIXTURE_SOLUTION), producer_id="c2r4.fixture-task-validator.v1",
        locus_namespace=SEMANTIC_OBJECT, locus_identity=semantic,
        reason_codes=("TASK_REQUIREMENT_UNSATISFIED",), details_digest=h("fixture-task-evidence"),
    )
    traversal=execute_samsung_feedback_step(
        run_id="c2r4-reference-e2e", refinement_step_index=0, prior_proposal=FIXTURE_SOLUTION,
        diagnostic=diagnostic, reverse_trace=ReverseTraceIndex((observation,)), clamp_state=state0,
        release_bindings=bindings, immutable_givens=one_blank,
        model_path=args.model.resolve(), device=args.device, max_model_steps=16,
    )
    if traversal.status != FEEDBACK_REPROPOSED: raise RuntimeError(f"unexpected status {traversal.status}")
    if traversal.released_cells != (0,): raise RuntimeError("release was not exactly the fixture-derived hypothesis")
    if traversal.learned_input != one_blank: raise RuntimeError("release did not produce the one-blank fixture")
    if traversal.learned_status != "SOLVED" or traversal.learned_solution is None: raise RuntimeError("learned re-proposal failed")
    if not validate(one_blank, traversal.learned_solution).valid: raise RuntimeError("learned proposal violated immutable givens")
    surviving=all(traversal.learned_solution[cell]==FIXTURE_SOLUTION[cell] for cell in range(1,81))
    if not surviving: raise RuntimeError("surviving immutable support was not preserved")
    report={
      "schema":"elpis.public-c2r4-redteam-feedback-control.v1","status":"PASS","role":"MECHANISM_CONTROL_NOT_COMPETENCE_EVAL",
      "released_value_source":"deterministic_solution_fixture_not_model_output",
      "release":{"cells":list(traversal.released_cells),"cardinality":len(traversal.released_cells),"binding_table_digest":bindings.binding_table_digest},
      "checks":{"release_cardinality_is_one":len(traversal.released_cells)==1,"surviving_immutable_givens_preserved":surviving,"learned_solution_valid_against_original_givens":validate(one_blank,traversal.learned_solution).valid},
      "claims":{"feedback_mechanism_executed":traversal.status==FEEDBACK_REPROPOSED,"model_competence_evaluated":False,"generalization_proven":False,"runtime_admission":False},
    }
    print(json.dumps(report,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
