from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path
import shutil

import pytest

from Grid81.canonical_reader import load_current_grid81
from elpis_grid81_application_executor import DurableApplicationLedger
from elpis_grid81_promotion_authority import issue_promotion_capability
from elpis_grid81_promotion_planner.canonical import (
    CanonicalPromotionPlan,
    PhaseEvidence,
    PromotionDecision,
    SourceChain,
)
from elpis_grid81_promotion_planner.decision import DECISION_READY
from elpis_grid81_canonical_publisher import PublicationError, publish_candidate
import elpis_grid81_canonical_publisher.publisher as publisher


REPO = Path(__file__).resolve().parents[3]
SOURCE_GRID81 = REPO / "components" / "Grid81" / "state" / "Canonical" / "Grid81"

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


def _canonical_digest(value) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _copy_root(base: Path, name: str) -> Path:
    root = base / name
    (root / "Canonical").mkdir(parents=True)
    shutil.copytree(SOURCE_GRID81, root / "Canonical" / "Grid81")
    return root


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


def _authority_objects(artifact_digest: str):
    chain = SourceChain(
        g53b1=_phase("G5.3B.1"),
        g53c=_phase(
            "G5.3C",
            artifact_digest=artifact_digest,
            capability_digest=_h("structural-capability"),
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


def _issue(current: Path, ledger, *, approval="approval", artifact=None):
    artifact = artifact or _h("artifact")
    chain, decision, plan = _authority_objects(artifact)
    return issue_promotion_capability(
        plan=plan,
        decision=decision,
        chain=chain,
        project_root=current,
        operator_approval_digest=_h(approval),
        expected_publication_ledger_head=ledger.head,
    )


def _make_candidate(current_root: Path, candidate_root: Path, cap: dict):
    current = load_current_grid81(current_root)
    grid = candidate_root / "Canonical" / "Grid81"
    gens = grid / "generations"

    transaction_id = cap["target_bindings"]["transaction_id"]
    capability_id = cap["capability_id"]
    capability_digest = cap["capability_digest"]

    gen1 = _read(gens / "000001.json")
    gen2 = copy.deepcopy(gen1)
    gen2["generation_number"] = cap["target_bindings"]["target_generation"]
    gen2["prior_generation_binding"] = current.generation_semantic_digest
    gen2["transaction_id"] = transaction_id
    gen2["source_capability_digest"] = capability_digest
    gen2["authority_record"]["capability_id"] = capability_id
    gen2["authority_record"]["authorization_digest"] = cap[
        "authority_policy_digest"
    ]
    gen2["capability_consumption_record"]["capability_id"] = capability_id
    gen2["capability_consumption_record"]["capability_digest"] = capability_digest
    gen2["artifact_inventory"][0]["logical_path"] = (
        cap["target_bindings"]["generation_target"]
    )

    semantic_payload = {
        key: value
        for key, value in gen2.items()
        if key not in ("generation_semantic_digest", "generation_file_sha256")
    }
    gen2["generation_semantic_digest"] = _canonical_digest(semantic_payload)
    gen2["generation_file_sha256"] = _canonical_digest({
        "schema": gen2["schema"],
        "generation_number": gen2["generation_number"],
        "generation_semantic_digest": gen2["generation_semantic_digest"],
    })

    gen_name = f"{gen2['generation_number']:06d}.json"
    gen_path = gens / gen_name
    _write(gen_path, gen2)
    generation_hash = _sha(gen_path)

    consumed_path = grid / ".consumed_capability.json"
    consumed = copy.deepcopy(cap)
    consumed["lifecycle"] = {
        "state": "CONSUMED",
        "consumed": True,
        "consumption_count": 1,
        "replay_permitted": False,
    }
    _write(consumed_path, consumed)
    consumed_hash = _sha(consumed_path)

    head_path = grid / "HEAD.json"
    head = _read(head_path)
    head["generation"] = gen2["generation_number"]
    head["generation_path"] = cap["target_bindings"]["generation_target"]
    head["generation_file_sha256"] = generation_hash
    head["generation_semantic_digest"] = gen2["generation_semantic_digest"]
    head["transaction_id"] = transaction_id
    head["capability_id"] = capability_id
    head["capability_consumed_id"] = capability_id
    head["previous_generation_binding"] = current.generation_semantic_digest
    _write(head_path, head)
    head_hash = _sha(head_path)

    receipt_path = grid / ".consumption_receipt.json"
    receipt = {
        "schema": "elpis.grid81.canonical-publication-consumption-receipt.v1",
        "capability_id": capability_id,
        "capability_digest": capability_digest,
        "transaction_id": transaction_id,
        "commit_status": "COMMITTED",
        "consumption_count": 1,
        "one_use": True,
        "ecs_world_write_applied": False,
        "generation_file_sha256": generation_hash,
        "head_file_sha256": head_hash,
        "consumed_capability_sha256": consumed_hash,
    }
    _write(receipt_path, receipt)
    receipt_hash = _sha(receipt_path)

    manifest_path = grid / ".transaction_manifest.json"
    manifest = _read(manifest_path)
    manifest["transaction_id"] = transaction_id
    manifest["capability_id"] = capability_id
    manifest["generation"] = gen2["generation_number"]
    manifest["transaction_state"] = "PREPARED"
    for item in manifest["artifact_inventory"]:
        role = item["artifact_role"]
        if role == "consumed_capability":
            item["sha256"] = consumed_hash
        elif role == "consumption_receipt":
            item["sha256"] = receipt_hash
        elif role == "canonical_head":
            item["sha256"] = head_hash
        elif role == "canonical_generation":
            item["relative_path"] = cap["target_bindings"]["generation_target"]
            item["sha256"] = generation_hash
    _write(manifest_path, manifest)

    return load_current_grid81(candidate_root)


@pytest.fixture
def current(tmp_path):
    return _copy_root(tmp_path, "current")


@pytest.fixture
def ledger(tmp_path):
    with DurableApplicationLedger(tmp_path / "publication-ledger.sqlite3") as value:
        yield value


def _candidate(tmp_path, current, cap, name="candidate"):
    candidate = _copy_root(tmp_path, name)
    state = _make_candidate(current, candidate, cap)
    return candidate, state


def _publish(current, candidate, ledger, cap, tmp_path):
    return publish_candidate(
        project_root=current,
        candidate_root=candidate,
        ledger=ledger,
        promotion_capability=cap,
        lock_path=current / "Canonical",
    )


def test_public_api_requires_capability_not_bare_hashes():
    params = inspect.signature(publish_candidate).parameters
    assert "promotion_capability" in params
    assert "artifact_digest" not in params
    assert "expected_current_canonical_digest" not in params
    assert "expected_ledger_head" not in params


def test_atomic_publish_consumes_promotion_capability_and_replays_idempotently(
    current, ledger, tmp_path
):
    cap = _issue(current, ledger)
    candidate, candidate_state = _candidate(tmp_path, current, cap)
    original_head = ledger.head

    receipt = _publish(current, candidate, ledger, cap, tmp_path)

    assert receipt.status == "COMMITTED"
    assert receipt.resumed is False
    assert receipt.artifact_digest == cap["source_bindings"]["artifact_digest"]
    assert receipt.promotion_capability_digest == cap["capability_digest"]
    assert load_current_grid81(current).canonical_digest == candidate_state.canonical_digest
    assert ledger.has_receipt(cap["source_bindings"]["artifact_digest"])
    assert not ledger.has_receipt(cap["capability_digest"])
    assert ledger.to_dict()["count"] == 1

    replay = _publish(current, candidate, ledger, cap, tmp_path)
    assert replay.status == "ALREADY_COMMITTED"
    assert replay.resumed is True
    assert ledger.to_dict()["count"] == 1
    assert original_head != ledger.head


def test_tampered_capability_rejected_without_mutation(current, ledger, tmp_path):
    cap = _issue(current, ledger)
    candidate, _ = _candidate(tmp_path, current, cap)
    cap = copy.deepcopy(cap)
    cap["operator_approval_digest"] = _h("tampered")

    before = load_current_grid81(current).canonical_digest
    with pytest.raises(PublicationError, match="PROMOTION_CAPABILITY_INVALID"):
        _publish(current, candidate, ledger, cap, tmp_path)

    assert load_current_grid81(current).canonical_digest == before
    assert ledger.is_empty


def test_candidate_from_different_valid_capability_is_rejected(
    current, ledger, tmp_path
):
    cap_a = _issue(current, ledger, approval="A")
    cap_b = _issue(current, ledger, approval="B")
    candidate, _ = _candidate(tmp_path, current, cap_b)

    with pytest.raises(
        PublicationError,
        match="PROMOTION_TRANSACTION_ID_MISMATCH|PROMOTION_CAPABILITY_ID_MISMATCH",
    ):
        _publish(current, candidate, ledger, cap_a, tmp_path)

    assert load_current_grid81(current).generation_number == 1
    assert ledger.is_empty


def test_stale_publication_ledger_binding_rejects(current, ledger, tmp_path):
    cap = _issue(current, ledger)
    candidate, _ = _candidate(tmp_path, current, cap)

    ledger.append(ledger.head, _h("unrelated-receipt"), _h("unrelated-capability"))

    with pytest.raises(PublicationError, match="STALE_LEDGER_HEAD"):
        _publish(current, candidate, ledger, cap, tmp_path)

    assert load_current_grid81(current).generation_number == 1
    assert ledger.to_dict()["count"] == 1


def test_consumed_projection_tamper_rejected_even_when_reader_valid(
    current, ledger, tmp_path
):
    cap = _issue(current, ledger)
    candidate, _ = _candidate(tmp_path, current, cap)
    grid = candidate / "Canonical" / "Grid81"

    consumed_path = grid / ".consumed_capability.json"
    consumed = _read(consumed_path)
    consumed["claims_not_made"] = sorted(
        consumed["claims_not_made"] + ["tampered-but-reader-opaque"]
    )
    _write(consumed_path, consumed)

    receipt_path = grid / ".consumption_receipt.json"
    receipt = _read(receipt_path)
    receipt["consumed_capability_sha256"] = _sha(consumed_path)
    _write(receipt_path, receipt)

    manifest_path = grid / ".transaction_manifest.json"
    manifest = _read(manifest_path)
    for item in manifest["artifact_inventory"]:
        if item["artifact_role"] == "consumed_capability":
            item["sha256"] = _sha(consumed_path)
        elif item["artifact_role"] == "consumption_receipt":
            item["sha256"] = _sha(receipt_path)
    _write(manifest_path, manifest)

    assert load_current_grid81(candidate).generation_number == 2

    with pytest.raises(
        PublicationError,
        match="CANDIDATE_CONSUMED_CAPABILITY_PROJECTION_MISMATCH",
    ):
        _publish(current, candidate, ledger, cap, tmp_path)

    assert ledger.is_empty


def test_historical_generation_mutation_rejected(current, ledger, tmp_path):
    cap = _issue(current, ledger)
    candidate, _ = _candidate(tmp_path, current, cap)

    path = candidate / "Canonical" / "Grid81" / "generations" / "000001.json"
    path.write_bytes(path.read_bytes() + b"\n")

    with pytest.raises(PublicationError, match="HISTORICAL_GENERATION_MUTATED"):
        _publish(current, candidate, ledger, cap, tmp_path)

    assert ledger.is_empty


def test_exact_capability_reservation_resumes_after_exchange_failure(
    current, ledger, tmp_path, monkeypatch
):
    cap = _issue(current, ledger)
    candidate, candidate_state = _candidate(tmp_path, current, cap)
    real = publisher._commit_exchange

    def injected_failure(left, right):
        raise PublicationError("INJECTED_AFTER_LEDGER_APPEND")

    monkeypatch.setattr(publisher, "_commit_exchange", injected_failure)
    with pytest.raises(PublicationError, match="INJECTED_AFTER_LEDGER_APPEND"):
        _publish(current, candidate, ledger, cap, tmp_path)

    assert ledger.to_dict()["count"] == 1
    assert ledger.has_receipt(cap["source_bindings"]["artifact_digest"])
    assert load_current_grid81(current).generation_number == 1

    monkeypatch.setattr(publisher, "_commit_exchange", real)
    resumed = _publish(current, candidate, ledger, cap, tmp_path)
    assert resumed.status == "COMMITTED"
    assert resumed.resumed is True
    assert ledger.to_dict()["count"] == 1
    assert load_current_grid81(current).canonical_digest == candidate_state.canonical_digest


def test_atomic_exchange_preflight_failure_does_not_consume(
    current, ledger, tmp_path, monkeypatch
):
    cap = _issue(current, ledger)
    candidate, _ = _candidate(tmp_path, current, cap)

    def unsupported(left, right):
        raise PublicationError("ATOMIC_EXCHANGE_UNSUPPORTED")

    monkeypatch.setattr(publisher, "_atomic_exchange", unsupported)
    with pytest.raises(PublicationError, match="ATOMIC_EXCHANGE_UNSUPPORTED"):
        _publish(current, candidate, ledger, cap, tmp_path)

    assert ledger.is_empty
    assert load_current_grid81(current).generation_number == 1


def test_committed_replay_still_requires_exact_original_capability(
    current, ledger, tmp_path
):
    cap_a = _issue(current, ledger, approval="replay-A")
    cap_b = _issue(current, ledger, approval="replay-B")
    candidate, _ = _candidate(tmp_path, current, cap_a, name="candidate-replay")

    committed = _publish(current, candidate, ledger, cap_a, tmp_path)
    assert committed.status == "COMMITTED"
    assert ledger.to_dict()["count"] == 1

    with pytest.raises(
        PublicationError,
        match="PROMOTION_TRANSACTION_ID_MISMATCH|PROMOTION_CAPABILITY_ID_MISMATCH",
    ):
        _publish(current, candidate, ledger, cap_b, tmp_path)

    replay = _publish(current, candidate, ledger, cap_a, tmp_path)
    assert replay.status == "ALREADY_COMMITTED"
    assert replay.resumed is True
    assert ledger.to_dict()["count"] == 1
