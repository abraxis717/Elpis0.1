from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from Grid81.canonical_reader import load_current_grid81
from elpis_grid81_application_executor import DurableApplicationLedger
from elpis_grid81_candidate_constructor import (
    CandidateConstructionError,
    construct_candidate,
)
from elpis_grid81_consumption_compiler import canonical_digest
from elpis_grid81_promotion_authority import issue_promotion_capability
from elpis_grid81_promotion_planner.canonical import (
    CanonicalPromotionPlan,
    PhaseEvidence,
    PromotionDecision,
    SourceChain,
)
from elpis_grid81_promotion_planner.decision import DECISION_READY
from elpis_grid81_canonical_publisher import publish_candidate


REPO = Path(__file__).resolve().parents[3]
SOURCE_GRID81 = (
    REPO / "components" / "Grid81" / "state" / "Canonical" / "Grid81"
)

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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_root(base: Path, name: str) -> Path:
    root = base / name
    (root / "Canonical").mkdir(parents=True)
    shutil.copytree(SOURCE_GRID81, root / "Canonical" / "Grid81")
    return root


def _tree_map(grid: Path) -> dict[str, str]:
    return {
        path.relative_to(grid).as_posix(): _sha(path)
        for path in sorted(grid.rglob("*"))
        if path.is_file()
    }


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


def _artifact() -> dict:
    proposals = sorted({_h("proposal-A"), _h("proposal-B")})
    source_capability = _h("structural-capability")

    bindings = []
    for proposal in proposals:
        payload = {
            "proposal_digest": proposal,
            "source_capability_digest": source_capability,
        }
        bindings.append({
            "schema_version": "structural-influence-proposal-binding.v1",
            "proposal_digest": proposal,
            "source_capability_digest": source_capability,
            "binding_state": "INCLUDED_UNAPPLIED",
            "binding_digest": canonical_digest(payload),
        })

    scope = canonical_digest({
        "authorized_proposal_digests": proposals,
        "proposal_binding_digests": sorted(
            item["binding_digest"] for item in bindings
        ),
        "source_capability_digest": source_capability,
    })

    artifact = {
        "schema_version": "structural-influence-artifact.v1",
        "artifact_class": "BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1",
        "materialization_class": (
            "MATERIALIZE_AUTHORIZED_STRUCTURAL_INFLUENCE_SET_V1"
        ),
        "target_domain_class": "GRID81_STRUCTURAL_PROPOSAL_DOMAIN_V1",
        "source_capability_digest": source_capability,
        "source_capability_semantic_digest": _h(
            "structural-capability-semantic"
        ),
        "source_request_digest": _h("source-request"),
        "source_adjudication_record_digest": _h("adjudication"),
        "source_proposal_set_digest": _h("proposal-set"),
        "authorized_proposal_digests": proposals,
        "proposal_bindings": bindings,
        "structural_influence_scope_digest": scope,
        "consumer_class": "STRUCTURAL_INFLUENCE_COMPILER_V1",
        "consumer_contract_digest": _h("consumer-contract"),
        "consumption_request_digest": _h("consumption-request"),
        "consumption_receipt_digest": "",
        "logical_tick": 0,
        "application_state": "UNAPPLIED",
        "compiler_contract_digest": _h("compiler-contract"),
        "artifact_semantic_digest": "",
        "artifact_digest": "",
        "claims_not_made": sorted([
            "artifact does not activate runtime components",
            "artifact does not choose a preferred proposal",
            "artifact does not dispatch execution",
            "artifact does not enforce structural influence",
            "artifact does not evaluate proposal quality",
            "artifact does not load adapters",
            "artifact does not load models",
            "artifact does not order proposals by preference",
        ]),
    }

    semantic_payload = {
        "artifact_class": artifact["artifact_class"],
        "authorized_proposal_digests": artifact[
            "authorized_proposal_digests"
        ],
        "consumer_class": artifact["consumer_class"],
        "materialization_class": artifact["materialization_class"],
        "target_domain_class": artifact["target_domain_class"],
        "application_state": artifact["application_state"],
        "source_capability_digest": artifact["source_capability_digest"],
        "source_capability_semantic_digest": artifact[
            "source_capability_semantic_digest"
        ],
        "structural_influence_scope_digest": artifact[
            "structural_influence_scope_digest"
        ],
        "proposal_bindings": artifact["proposal_bindings"],
        "consumption_request_digest": artifact[
            "consumption_request_digest"
        ],
        "compiler_contract_digest": artifact[
            "compiler_contract_digest"
        ],
    }
    artifact["artifact_semantic_digest"] = canonical_digest(
        semantic_payload
    )
    artifact["artifact_digest"] = canonical_digest({
        key: value
        for key, value in artifact.items()
        if key != "artifact_digest"
    })
    return artifact


def _authority_objects(
    artifact_digest: str,
    structural_capability_digest: str | None = None,
):
    if structural_capability_digest is None:
        structural_capability_digest = _h("structural-capability")
    chain = SourceChain(
        g53b1=_phase("G5.3B.1"),
        g53c=_phase(
            "G5.3C",
            artifact_digest=artifact_digest,
            capability_digest=structural_capability_digest,
            lifecycle_state="GRANTED_UNCONSUMED",
            receipt=_h("application-receipt"),
            state=_h("resulting-state"),
            ledger=_h("source-application-ledger"),
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


def _issue(current: Path, ledger, artifact: dict):
    chain, decision, plan = _authority_objects(
        artifact["artifact_digest"]
    )
    return issue_promotion_capability(
        plan=plan,
        decision=decision,
        chain=chain,
        project_root=current,
        operator_approval_digest=_h("operator-approval"),
        expected_publication_ledger_head=ledger.head,
    )


@pytest.fixture
def current(tmp_path):
    return _copy_root(tmp_path / "live", "state")


@pytest.fixture
def ledger(tmp_path):
    with DurableApplicationLedger(
        tmp_path / "publication-ledger.sqlite3"
    ) as value:
        yield value


def test_constructor_builds_reader_valid_successor_without_live_mutation(
    current, ledger, tmp_path
):
    artifact = _artifact()
    cap = _issue(current, ledger, artifact)
    candidate = tmp_path / "candidate"
    live_grid = current / "Canonical" / "Grid81"
    before = _tree_map(live_grid)
    old_generation = (
        live_grid / "generations" / "000001.json"
    ).read_bytes()

    receipt = construct_candidate(
        project_root=current,
        candidate_root=candidate,
        promotion_capability=cap,
        structural_artifact=artifact,
    )

    after = _tree_map(live_grid)
    assert after == before
    assert ledger.is_empty

    state = load_current_grid81(candidate)
    assert state.generation_number == 2
    assert state.transaction_id == cap["target_bindings"]["transaction_id"]
    assert state.capability_id == cap["capability_id"]
    assert state.structural_schema == "elpis.grid81.canonical-generation.v2"
    assert receipt.candidate_canonical_digest == state.canonical_digest

    candidate_grid = candidate / "Canonical" / "Grid81"
    assert (
        candidate_grid / "generations" / "000001.json"
    ).read_bytes() == old_generation

    gen2 = json.loads(
        (candidate_grid / "generations" / "000002.json").read_text()
    )
    assert gen2["prior_generation_binding"] == (
        load_current_grid81(current).generation_semantic_digest
    )
    assert gen2["source_capability_digest"] == cap["capability_digest"]
    assert gen2["source_artifact_record"]["artifact_digest"] == (
        artifact["artifact_digest"]
    )
    assert gen2["ecs_world_write_applied"] is False

    consumed = json.loads(
        (candidate_grid / ".consumed_capability.json").read_text()
    )
    expected = copy.deepcopy(cap)
    expected["lifecycle"] = {
        "state": "CONSUMED",
        "consumed": True,
        "consumption_count": 1,
        "replay_permitted": False,
    }
    assert consumed == expected


def test_construction_is_byte_deterministic(current, ledger, tmp_path):
    artifact = _artifact()
    cap = _issue(current, ledger, artifact)

    first = tmp_path / "candidate-a"
    second = tmp_path / "candidate-b"

    r1 = construct_candidate(
        project_root=current,
        candidate_root=first,
        promotion_capability=cap,
        structural_artifact=artifact,
    )
    r2 = construct_candidate(
        project_root=current,
        candidate_root=second,
        promotion_capability=cap,
        structural_artifact=artifact,
    )

    assert _tree_map(first / "Canonical" / "Grid81") == _tree_map(
        second / "Canonical" / "Grid81"
    )
    assert r1.candidate_canonical_digest == r2.candidate_canonical_digest
    assert r1.candidate_tree_digest == r2.candidate_tree_digest


def test_tampered_artifact_rejected_without_output(current, ledger, tmp_path):
    artifact = _artifact()
    cap = _issue(current, ledger, artifact)
    artifact = copy.deepcopy(artifact)
    artifact["claims_not_made"].append("tamper")
    candidate = tmp_path / "candidate"

    with pytest.raises(
        CandidateConstructionError,
        match="ARTIFACT_DIGEST_MISMATCH",
    ):
        construct_candidate(
            project_root=current,
            candidate_root=candidate,
            promotion_capability=cap,
            structural_artifact=artifact,
        )

    assert not candidate.exists()
    assert ledger.is_empty


def test_applied_artifact_rejected_without_output(current, ledger, tmp_path):
    artifact = _artifact()
    cap = _issue(current, ledger, artifact)
    artifact = copy.deepcopy(artifact)
    artifact["application_state"] = "APPLIED"
    candidate = tmp_path / "candidate"

    with pytest.raises(
        CandidateConstructionError,
        match="ARTIFACT_INVARIANTS",
    ):
        construct_candidate(
            project_root=current,
            candidate_root=candidate,
            promotion_capability=cap,
            structural_artifact=artifact,
        )

    assert not candidate.exists()


def test_candidate_root_inside_live_project_is_rejected(
    current, ledger
):
    artifact = _artifact()
    cap = _issue(current, ledger, artifact)
    candidate = current / "scratch-candidate"

    with pytest.raises(
        CandidateConstructionError,
        match="CANDIDATE_ROOT_INSIDE_PROJECT_ROOT",
    ):
        construct_candidate(
            project_root=current,
            candidate_root=candidate,
            promotion_capability=cap,
            structural_artifact=artifact,
        )
    assert not candidate.exists()


def test_existing_candidate_root_is_never_overwritten(
    current, ledger, tmp_path
):
    artifact = _artifact()
    cap = _issue(current, ledger, artifact)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    marker = candidate / "KEEP"
    marker.write_text("preserve", encoding="utf-8")

    with pytest.raises(
        CandidateConstructionError,
        match="CANDIDATE_ROOT_EXISTS",
    ):
        construct_candidate(
            project_root=current,
            candidate_root=candidate,
            promotion_capability=cap,
            structural_artifact=artifact,
        )

    assert marker.read_text(encoding="utf-8") == "preserve"


def test_constructor_output_is_directly_publishable(
    current, ledger, tmp_path
):
    artifact = _artifact()
    cap = _issue(current, ledger, artifact)
    candidate = tmp_path / "candidate"

    constructed = construct_candidate(
        project_root=current,
        candidate_root=candidate,
        promotion_capability=cap,
        structural_artifact=artifact,
    )
    before = load_current_grid81(current)

    published = publish_candidate(
        project_root=current,
        candidate_root=candidate,
        ledger=ledger,
        promotion_capability=cap,
        lock_path=tmp_path / "publisher.lock",
    )

    after = load_current_grid81(current)
    assert published.status == "COMMITTED"
    assert after.generation_number == before.generation_number + 1
    assert after.canonical_digest == constructed.candidate_canonical_digest
    assert ledger.has_receipt(artifact["artifact_digest"])
    assert ledger.to_dict()["count"] == 1


def test_manifest_authenticates_all_six_ordinary_files(
    current, ledger, tmp_path
):
    artifact = _artifact()
    cap = _issue(current, ledger, artifact)
    candidate = tmp_path / "candidate"

    construct_candidate(
        project_root=current,
        candidate_root=candidate,
        promotion_capability=cap,
        structural_artifact=artifact,
    )

    grid = candidate / "Canonical" / "Grid81"
    manifest = json.loads(
        (grid / ".transaction_manifest.json").read_text()
    )
    entries = {
        item["artifact_role"]: item
        for item in manifest["artifact_inventory"]
    }

    expected = {
        "authority_audit": grid / ".authority_audit.json",
        "consumed_capability": grid / ".consumed_capability.json",
        "consumption_receipt": grid / ".consumption_receipt.json",
        "source_nonmutation_audit": grid / ".source_nonmutation_audit.json",
        "canonical_head": grid / "HEAD.json",
        "canonical_generation": grid / "generations" / "000002.json",
    }

    for role, path in expected.items():
        assert entries[role]["sha256"] == _sha(path)

    assert entries["transaction_manifest"]["sha256"] == ""
    assert load_current_grid81(candidate).generation_number == 2


def test_artifact_must_match_authorized_structural_capability(
    current, ledger, tmp_path
):
    artifact = _artifact()
    chain, decision, plan = _authority_objects(
        artifact["artifact_digest"],
        structural_capability_digest=_h("different-structural-capability"),
    )
    cap = issue_promotion_capability(
        plan=plan,
        decision=decision,
        chain=chain,
        project_root=current,
        operator_approval_digest=_h("operator-approval"),
        expected_publication_ledger_head=ledger.head,
    )
    candidate = tmp_path / "candidate"

    with pytest.raises(
        CandidateConstructionError,
        match="ARTIFACT_STRUCTURAL_CAPABILITY_BINDING_MISMATCH",
    ):
        construct_candidate(
            project_root=current,
            candidate_root=candidate,
            promotion_capability=cap,
            structural_artifact=artifact,
        )

    assert not candidate.exists()
    assert ledger.is_empty
