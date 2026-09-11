from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import copy
import hashlib

import pytest

from Grid81.canonical_reader import load_current_grid81
from elpis_grid81_promotion_planner.canonical import (
    CanonicalPromotionPlan,
    PhaseEvidence,
    PromotionDecision,
    SourceChain,
)
from elpis_grid81_promotion_planner.decision import (
    DECISION_NOT_READY,
    DECISION_READY,
)
from elpis_grid81_promotion_authority import (
    AUTHORITY_POLICY_DIGEST,
    AUTHORIZED_PUBLISHER_CLASS,
    PromotionAuthorityError,
    issue_promotion_capability,
    require_promotion_capability,
    validate_promotion_capability,
)


REPO = Path(__file__).resolve().parents[3]
CANONICAL_ROOT = REPO / "components" / "Grid81" / "state"

INTENTIONS = (
    "VERIFY_CANONICAL_LEDGER_HEAD",
    "VERIFY_CAPABILITY_GRANTED_UNCONSUMED",
    "VERIFY_ARTIFACT_CANONICALLY_UNAPPLIED",
    "RESERVE_TRANSACTION_IDENTIFIER",
    "PERFORM_CANONICAL_APPLICATION",
    "APPEND_CANONICAL_RECEIPT",
    "VERIFY_POST_COMMIT_STATE",
)

PRECONDITIONS = (
    "canonical_ledger_head_verified",
    "capability_granted_and_unconsumed",
    "artifact_canonically_unapplied",
    "transaction_identifier_reserved",
    "post_commit_state_verified",
)


def _h(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _phase(
    phase_id: str,
    *,
    artifact_digest=None,
    capability_digest=None,
    lifecycle_state=None,
    receipt=None,
    state=None,
    ledger=None,
):
    return PhaseEvidence(
        phase_id=phase_id,
        source_directory=f"/evidence/{phase_id}",
        manifest_path=f"/evidence/{phase_id}/manifest.json",
        manifest_digest=_h(f"{phase_id}:manifest"),
        disposition="PASS",
        evidence_files=(("evidence.json", _h(f"{phase_id}:evidence"), 1),),
        artifact_digest=artifact_digest,
        capability_digest=capability_digest,
        lifecycle_state=lifecycle_state,
        shadow_receipt_digest=receipt,
        resulting_state_digest=state,
        resulting_ledger_head=ledger,
        bundle_digest=_h(f"{phase_id}:bundle"),
    )


def _objects():
    chain = SourceChain(
        g53b1=_phase("G5.3B.1"),
        g53c=_phase(
            "G5.3C",
            artifact_digest=_h("artifact"),
            capability_digest=_h("structural-capability"),
            lifecycle_state="GRANTED_UNCONSUMED",
            receipt=_h("application-receipt"),
            state=_h("resulting-state"),
            ledger=_h("durable-ledger-head"),
        ),
        g53d=_phase("G5.3D"),
    )

    decision = PromotionDecision(
        decision=DECISION_READY,
        gate_vector=(_h("gate-1"), _h("gate-2")),
        source_chain_digest=chain.chain_digest,
        expected_canonical_preconditions=PRECONDITIONS,
    )

    plan = CanonicalPromotionPlan(
        intentions=INTENTIONS,
        decision_digest=decision.digest,
        source_chain_digest=chain.chain_digest,
    )
    return chain, decision, plan


def _issue():
    chain, decision, plan = _objects()
    cap = issue_promotion_capability(
        plan=plan,
        decision=decision,
        chain=chain,
        project_root=CANONICAL_ROOT,
        operator_approval_digest=_h("explicit-operator-approval"),
        expected_publication_ledger_head=_h("publication-ledger-head"),
    )
    return cap, chain, decision, plan


def test_issue_binds_exact_source_and_immediate_successor_without_writes():
    before = {
        p.relative_to(CANONICAL_ROOT).as_posix(): hashlib.sha256(
            p.read_bytes()
        ).hexdigest()
        for p in sorted(CANONICAL_ROOT.rglob("*"))
        if p.is_file()
    }

    cap, chain, decision, plan = _issue()
    current = load_current_grid81(CANONICAL_ROOT)

    assert cap["schema"] == (
        "elpis.grid81.atomic-canonical-promotion-capability.v1"
    )
    assert cap["capability_type"] == "ATOMIC_GRID81_CANONICAL_PROMOTION"
    assert cap["authorized_publisher_class"] == AUTHORIZED_PUBLISHER_CLASS
    assert cap["authority_policy_digest"] == AUTHORITY_POLICY_DIGEST
    assert cap["source_bindings"]["promotion_plan_digest"] == plan.digest
    assert cap["source_bindings"]["promotion_decision_digest"] == decision.digest
    assert cap["source_bindings"]["source_chain_digest"] == chain.chain_digest
    assert cap["source_bindings"]["artifact_digest"] == chain.g53c.artifact_digest
    assert cap["source_bindings"]["source_application_ledger_head"] == (
        chain.g53c.resulting_ledger_head
    )
    assert cap["target_bindings"]["expected_publication_ledger_head"] == (
        _h("publication-ledger-head")
    )
    assert len(cap["target_bindings"]["transaction_id"]) == 64
    assert cap["target_bindings"]["source_generation"] == current.generation_number
    assert cap["target_bindings"]["target_generation"] == (
        current.generation_number + 1
    )
    assert cap["target_bindings"]["source_canonical_digest"] == (
        current.canonical_digest
    )
    assert cap["target_bindings"]["generation_target"].endswith("000002.json")
    assert cap["lifecycle"] == {
        "state": "GRANTED_UNCONSUMED",
        "consumed": False,
        "consumption_count": 0,
        "replay_permitted": False,
    }

    valid, issues = validate_promotion_capability(cap)
    assert valid is True
    assert issues == ()
    assert require_promotion_capability(cap) is cap

    after = {
        p.relative_to(CANONICAL_ROOT).as_posix(): hashlib.sha256(
            p.read_bytes()
        ).hexdigest()
        for p in sorted(CANONICAL_ROOT.rglob("*"))
        if p.is_file()
    }
    assert after == before


def test_issuance_is_byte_semantically_deterministic():
    first, *_ = _issue()
    second, *_ = _issue()
    assert first == second
    assert first["capability_id"] == second["capability_id"]
    assert first["capability_digest"] == second["capability_digest"]


@pytest.mark.parametrize("approval", ["", "x" * 64, "a" * 63, None, 1])
def test_operator_approval_digest_is_explicit_and_strict(approval):
    chain, decision, plan = _objects()
    with pytest.raises(
        PromotionAuthorityError,
        match="OPERATOR_APPROVAL_DIGEST_INVALID",
    ):
        issue_promotion_capability(
            plan=plan,
            decision=decision,
            chain=chain,
            project_root=CANONICAL_ROOT,
            operator_approval_digest=approval,
            expected_publication_ledger_head=_h("publication-ledger-head"),
        )


def test_not_ready_decision_never_issues():
    chain, decision, _ = _objects()
    decision = replace(decision, decision=DECISION_NOT_READY)
    plan = CanonicalPromotionPlan(
        intentions=INTENTIONS,
        decision_digest=decision.digest,
        source_chain_digest=chain.chain_digest,
    )
    with pytest.raises(PromotionAuthorityError, match="DECISION_NOT_READY"):
        issue_promotion_capability(
            plan=plan,
            decision=decision,
            chain=chain,
            project_root=CANONICAL_ROOT,
            operator_approval_digest=_h("approval"),
            expected_publication_ledger_head=_h("publication-ledger-head"),
        )


def test_plan_cannot_claim_authority_to_obtain_authority():
    chain, decision, plan = _objects()
    plan = replace(plan, authoritative=True)
    with pytest.raises(
        PromotionAuthorityError,
        match="PLAN_DECISION_MISMATCH|PLAN_AUTHORITY_BOUNDARY_INVALID",
    ):
        issue_promotion_capability(
            plan=plan,
            decision=decision,
            chain=chain,
            project_root=CANONICAL_ROOT,
            operator_approval_digest=_h("approval"),
            expected_publication_ledger_head=_h("publication-ledger-head"),
        )


def test_source_identity_discontinuity_rejects():
    chain, decision, plan = _objects()
    chain = replace(
        chain,
        g53c=replace(chain.g53c, resulting_ledger_head=None),
    )
    decision = replace(decision, source_chain_digest=chain.chain_digest)
    plan = replace(
        plan,
        decision_digest=decision.digest,
        source_chain_digest=chain.chain_digest,
    )
    with pytest.raises(
        PromotionAuthorityError,
        match="SOURCE_SOURCE_APPLICATION_LEDGER_HEAD_INVALID",
    ):
        issue_promotion_capability(
            plan=plan,
            decision=decision,
            chain=chain,
            project_root=CANONICAL_ROOT,
            operator_approval_digest=_h("approval"),
            expected_publication_ledger_head=_h("publication-ledger-head"),
        )


@pytest.mark.parametrize(
    ("path", "value", "issue"),
    [
        (("authorized_publisher_class",), "OTHER", "PUBLISHER_CLASS"),
        (("authority_policy_digest",), "0" * 64, "AUTHORITY_POLICY"),
        (("one_use",), False, "ONE_USE"),
        (("constraints", "append_only"), False, "CONSTRAINTS"),
        (("grants", "ecs_world_commit"), True, "GRANTS"),
        (("lifecycle", "consumed"), True, "LIFECYCLE"),
        (
            ("target_bindings", "target_generation"),
            9,
            "TARGET_GENERATION",
        ),
        (
            ("source_bindings", "artifact_digest"),
            "z" * 64,
            "SOURCE_ARTIFACT_DIGEST",
        ),
        (
            ("target_bindings", "expected_publication_ledger_head"),
            "z" * 64,
            "EXPECTED_PUBLICATION_LEDGER_HEAD",
        ),
        (
            ("target_bindings", "transaction_id"),
            "0" * 64,
            "TRANSACTION_ID_RESERVATION_MISMATCH",
        ),
    ],
)
def test_validator_rejects_authority_or_binding_tamper(path, value, issue):
    cap, *_ = _issue()
    cap = copy.deepcopy(cap)
    target = cap
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    valid, issues = validate_promotion_capability(cap)
    assert valid is False
    assert issue in issues


def test_self_digest_and_id_are_authenticated():
    cap, *_ = _issue()

    altered = copy.deepcopy(cap)
    altered["operator_approval_digest"] = _h("other-approval")
    valid, issues = validate_promotion_capability(altered)
    assert valid is False
    assert "TRANSACTION_ID_RESERVATION_MISMATCH" in issues
    assert "CAPABILITY_ID_MISMATCH" in issues
    assert "CAPABILITY_DIGEST_MISMATCH" in issues

    altered = copy.deepcopy(cap)
    altered["capability_digest"] = "0" * 64
    valid, issues = validate_promotion_capability(altered)
    assert valid is False
    assert "CAPABILITY_DIGEST_MISMATCH" in issues


def test_current_canonical_source_binding_is_real():
    cap, *_ = _issue()
    current = load_current_grid81(CANONICAL_ROOT)
    assert cap["target_bindings"]["source_canonical_digest"] == current.canonical_digest
    assert cap["target_bindings"]["source_generation_semantic_digest"] == (
        current.generation_semantic_digest
    )
