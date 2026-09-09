from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests" / "run_authority_preserving_improvement_r0.py"


def _run():
    env = dict(os.environ)
    prefix = os.pathsep.join(
        [
            str(ROOT / "src"),
            str(ROOT / "tests"),
        ]
    )
    env["PYTHONPATH"] = (
        prefix
        + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    )
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_authority_preserving_improvement_witness_r0():
    first = _run()
    assert first.returncode == 0, first.stderr

    second = _run()
    assert second.returncode == 0, second.stderr
    assert first.stdout == second.stdout

    report = json.loads(first.stdout)
    assert report["status"] == "PASS"
    assert report["public_authority"] == (
        "d668760b5d51fd8984eaffcfd13834c0fd5b22f7"
    )

    assert [c["quality_matches"] for c in report["cycles"]] == [27, 54, 81]
    assert all(c["quality_total"] == 81 for c in report["cycles"])
    assert all(c["proposal_authority_granted"] == 0 for c in report["cycles"])
    assert all(c["feedback_authority_granted"] == 0 for c in report["cycles"])
    assert all(c["proposal_execution_authorized"] is False for c in report["cycles"])

    application = report["application_terminal"]
    assert application["status"] == "APPLIED_ONE_P1_TRANSITION"
    assert application["applied_count"] == 1
    assert application["selected_cost"] < application["current_cost"]
    assert application["proposal_queries"] == 1
    assert application["authority_granted_to_proposer"] == 0
    assert application["execution_authorized_to_proposer"] is False
    assert application["application_capability_returned"] is False

    abstention = report["abstention_terminal"]
    assert abstention["status"] == "ABSTAIN_ALREADY_OPTIMAL"
    assert abstention["applied_count"] == 0
    assert abstention["current_cost"] == 0
    assert abstention["authority_granted_to_proposer"] == 0
    assert abstention["execution_authorized_to_proposer"] is False
    assert abstention["application_capability_returned"] is False

    fixture = report["application_fixture"]
    assert fixture == {
        "source": "PUBLIC_PROJECTOR_DERIVED_MUTATION_HAZARD",
        "semantic_request_digest": (
            "de4e1e3e3c9cfdd9e7a58bb2b479026f2c093de86b25fb159428e3ecb697444d"
        ),
        "projection_digest": (
            "3c008b56e72b71e60b583ef2eef703d7bb370754c6f5f7b540836504f8ef5a08"
        ),
        "initial_cost": 1,
        "initial_fingerprint": (
            "bd33bd4d2a9c5568a46e247260958e64ff3d884014e272d0a0253938a6ce765b"
        ),
        "initial_residual_ids": [
            "hazard.producer.consumer.mutator",
        ],
        "legal_mutating_candidate_count": 120,
        "strict_improvement_count": 1,
        "certified_selected_cost": 0,
        "certified_selected_enum_index": 10,
        "certified_selected_move": ["set", 9, 4],
        "certified_transition_digest": (
            "84c8e738524a84f633180a4ad29bea6d900181385561aa2802a6d46da970f343"
        ),
        "certified_after_fingerprint": (
            "722c692af0a94ba5ff18c67d29d29995b0ba2c89c0408453a97ba1c99c258444"
        ),
        "certified_residual_ids_after": [],
    }

    assert report["negative_cases"] == {
        "contract_tamper": "AUTHORITY_CONTRACT_MISMATCH",
        "forged_authorizing_evidence": "PROPOSER_EVIDENCE_INJECTION_REJECTED",
        "adjudicator_selection": "ADJUDICATOR_SELECTION_REJECTED",
        "candidate_selection": "CANDIDATE_INJECTION_REJECTED",
        "authority_claim": "AUTHORITY_ESCALATION_REJECTED",
        "execution_claim": "EXECUTION_AUTHORITY_REJECTED",
        "application_capability_injection": "APPLICATION_CAPABILITY_INJECTION_REJECTED",
        "stale_cycle_replay": "STALE_PROPOSAL_REPLAY_REJECTED",
    }

    claims = report["claims"]
    assert claims["three_deterministic_improvement_cycles"] is True
    assert claims["proposal_quality_strictly_improved"] is True
    assert claims["perfect_final_proposal_quality"] is True
    assert claims["authority_contract_unchanged_across_cycles"] is True
    assert claims["proposer_authority_always_zero"] is True
    assert claims["feedback_authority_always_zero"] is True
    assert claims["quality_did_not_grant_execution_authority"] is True
    assert claims["authority_accumulated_across_cycles"] == 0
    assert claims["bounded_application_observed"] is True
    assert claims["explicit_abstention_observed"] is True
    assert claims["same_improved_packet_cannot_force_application"] is True
    assert claims["production_authority_contract_modified"] is False

    assert all(value is False for value in report["scope_nonclaims"].values())
