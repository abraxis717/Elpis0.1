from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from Grid81.canonical_reader import load_current_grid81
from elpis_grid81_application_executor import DurableApplicationLedger
from elpis_grid81_canonical_publisher import PublicationError, publish_candidate
import elpis_grid81_canonical_publisher.publisher as publisher


REPO = Path(__file__).resolve().parents[3]
SOURCE_GRID81 = REPO / "components" / "Grid81" / "state" / "Canonical" / "Grid81"


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


def _make_candidate(current_root: Path, candidate_root: Path, *, salt: str = "A"):
    current = load_current_grid81(current_root)
    grid = candidate_root / "Canonical" / "Grid81"
    gens = grid / "generations"

    transaction_id = hashlib.sha256(f"transaction:{salt}".encode()).hexdigest()
    capability_id = hashlib.sha256(f"capability-id:{salt}".encode()).hexdigest()
    capability_digest = hashlib.sha256(f"capability:{salt}".encode()).hexdigest()

    gen1 = _read(gens / "000001.json")
    gen2 = copy.deepcopy(gen1)
    gen2["generation_number"] = 2
    gen2["prior_generation_binding"] = current.generation_semantic_digest
    gen2["transaction_id"] = transaction_id
    gen2["source_capability_digest"] = capability_digest
    gen2["authority_record"]["capability_id"] = capability_id
    gen2["capability_consumption_record"]["capability_id"] = capability_id
    gen2["capability_consumption_record"]["capability_digest"] = capability_digest
    gen2["artifact_inventory"][0]["logical_path"] = (
        "Canonical/Grid81/generations/000002.json"
    )

    semantic_payload = {
        key: value
        for key, value in gen2.items()
        if key not in ("generation_semantic_digest", "generation_file_sha256")
    }
    gen2["generation_semantic_digest"] = _canonical_digest(semantic_payload)
    gen2["generation_file_sha256"] = _canonical_digest({
        "schema": gen2["schema"],
        "generation_number": 2,
        "generation_semantic_digest": gen2["generation_semantic_digest"],
    })
    _write(gens / "000002.json", gen2)
    generation_hash = _sha(gens / "000002.json")

    consumed_path = grid / ".consumed_capability.json"
    consumed = _read(consumed_path)
    consumed["capability_id"] = capability_id
    consumed["capability_digest"] = capability_digest
    consumed["target_bindings"]["generation"] = 2
    consumed["target_bindings"]["generation_file"] = (
        "Canonical/Grid81/generations/000002.json"
    )
    consumed["target_bindings"]["generation_prestate"] = "ABSENT"
    consumed["target_bindings"]["head_prestate"] = "PRESENT"
    consumed["transaction_binding"]["generation_target"] = (
        "Canonical/Grid81/generations/000002.json"
    )
    consumed["transaction_binding"]["transaction_id"] = transaction_id
    _write(consumed_path, consumed)
    consumed_hash = _sha(consumed_path)

    head_path = grid / "HEAD.json"
    head = _read(head_path)
    head["generation"] = 2
    head["generation_path"] = "Canonical/Grid81/generations/000002.json"
    head["generation_file_sha256"] = generation_hash
    head["generation_semantic_digest"] = gen2["generation_semantic_digest"]
    head["transaction_id"] = transaction_id
    head["capability_id"] = capability_id
    head["capability_consumed_id"] = capability_id
    head["previous_generation_binding"] = current.generation_semantic_digest
    _write(head_path, head)
    head_hash = _sha(head_path)

    receipt_path = grid / ".consumption_receipt.json"
    receipt = _read(receipt_path)
    receipt["capability_id"] = capability_id
    receipt["capability_digest"] = capability_digest
    receipt["transaction_id"] = transaction_id
    receipt["consumed_capability_sha256"] = consumed_hash
    receipt["generation_file_sha256"] = generation_hash
    receipt["head_file_sha256"] = head_hash
    _write(receipt_path, receipt)
    receipt_hash = _sha(receipt_path)

    manifest_path = grid / ".transaction_manifest.json"
    manifest = _read(manifest_path)
    manifest["transaction_id"] = transaction_id
    manifest["capability_id"] = capability_id
    manifest["generation"] = 2
    for artifact in manifest["artifact_inventory"]:
        role = artifact["artifact_role"]
        if role == "consumed_capability":
            artifact["sha256"] = consumed_hash
        elif role == "consumption_receipt":
            artifact["sha256"] = receipt_hash
        elif role == "canonical_head":
            artifact["sha256"] = head_hash
        elif role == "canonical_generation":
            artifact["relative_path"] = (
                "Canonical/Grid81/generations/000002.json"
            )
            artifact["sha256"] = generation_hash
    _write(manifest_path, manifest)

    # Production reader is the candidate-format acceptance oracle.
    return load_current_grid81(candidate_root)


@pytest.fixture
def roots(tmp_path):
    current = _copy_root(tmp_path, "current")
    candidate = _copy_root(tmp_path, "candidate")
    candidate_state = _make_candidate(current, candidate)
    return current, candidate, candidate_state


@pytest.fixture
def ledger(tmp_path):
    with DurableApplicationLedger(tmp_path / "ledger.sqlite3") as value:
        yield value


def _publish(current, candidate, candidate_state, ledger, tmp_path, *, artifact="a" * 64):
    previous = load_current_grid81(current)
    return publish_candidate(
        project_root=current,
        candidate_root=candidate,
        ledger=ledger,
        artifact_digest=artifact,
        expected_current_canonical_digest=previous.canonical_digest,
        expected_ledger_head=ledger.head,
        lock_path=tmp_path / "publisher.lock",
    )


def test_atomic_publish_and_idempotent_replay(roots, ledger, tmp_path):
    current, candidate, candidate_state = roots
    previous = load_current_grid81(current)
    initial_ledger_head = ledger.head

    receipt = publish_candidate(
        project_root=current,
        candidate_root=candidate,
        ledger=ledger,
        artifact_digest="a" * 64,
        expected_current_canonical_digest=previous.canonical_digest,
        expected_ledger_head=initial_ledger_head,
        lock_path=tmp_path / "publisher.lock",
    )

    assert receipt.status == "COMMITTED"
    assert receipt.resumed is False
    assert receipt.generation_number == 2
    assert load_current_grid81(current).canonical_digest == candidate_state.canonical_digest
    assert ledger.has_receipt("a" * 64)
    assert ledger.verify_chain()[0] is True
    assert ledger.to_dict()["count"] == 1

    replay = publish_candidate(
        project_root=current,
        candidate_root=candidate,
        ledger=ledger,
        artifact_digest="a" * 64,
        expected_current_canonical_digest=previous.canonical_digest,
        expected_ledger_head=initial_ledger_head,
        lock_path=tmp_path / "publisher.lock",
    )
    assert replay.status == "ALREADY_COMMITTED"
    assert replay.resumed is True
    assert ledger.to_dict()["count"] == 1


def test_stale_canonical_head_rejects_without_ledger_mutation(roots, ledger, tmp_path):
    current, candidate, _ = roots
    before = ledger.to_dict()
    with pytest.raises(PublicationError, match="STALE_CANONICAL_HEAD"):
        publish_candidate(
            project_root=current,
            candidate_root=candidate,
            ledger=ledger,
            artifact_digest="a" * 64,
            expected_current_canonical_digest="f" * 64,
            expected_ledger_head=ledger.head,
            lock_path=tmp_path / "publisher.lock",
        )
    assert ledger.to_dict() == before
    assert load_current_grid81(current).generation_number == 1


def test_stale_ledger_head_rejects_without_canonical_mutation(roots, ledger, tmp_path):
    current, candidate, _ = roots
    before = load_current_grid81(current)
    with pytest.raises(PublicationError, match="STALE_LEDGER_HEAD"):
        publish_candidate(
            project_root=current,
            candidate_root=candidate,
            ledger=ledger,
            artifact_digest="a" * 64,
            expected_current_canonical_digest=before.canonical_digest,
            expected_ledger_head="f" * 64,
            lock_path=tmp_path / "publisher.lock",
        )
    assert load_current_grid81(current).canonical_digest == before.canonical_digest
    assert ledger.is_empty


def test_historical_generation_mutation_rejected(roots, ledger, tmp_path):
    current, candidate, _ = roots
    path = candidate / "Canonical" / "Grid81" / "generations" / "000001.json"
    path.write_bytes(path.read_bytes() + b"\n")
    previous = load_current_grid81(current)

    # Candidate reader follows HEAD->000002, so publisher must independently
    # protect immutable historical generations.
    with pytest.raises(PublicationError, match="HISTORICAL_GENERATION_MUTATED"):
        publish_candidate(
            project_root=current,
            candidate_root=candidate,
            ledger=ledger,
            artifact_digest="a" * 64,
            expected_current_canonical_digest=previous.canonical_digest,
            expected_ledger_head=ledger.head,
            lock_path=tmp_path / "publisher.lock",
        )
    assert ledger.is_empty


def test_generation_skip_rejected(roots, ledger, tmp_path):
    current, candidate, _ = roots
    grid = candidate / "Canonical" / "Grid81"
    head = _read(grid / "HEAD.json")
    head["generation"] = 3
    _write(grid / "HEAD.json", head)

    # Keep the intentionally skipped candidate reader-valid: the canonical
    # manifest authenticates HEAD bytes, so refresh only that fixture hash.
    manifest_path = grid / ".transaction_manifest.json"
    manifest = _read(manifest_path)
    for artifact in manifest["artifact_inventory"]:
        if artifact["artifact_role"] == "canonical_head":
            artifact["sha256"] = _sha(grid / "HEAD.json")
    _write(manifest_path, manifest)

    assert load_current_grid81(candidate).generation_number == 3
    previous = load_current_grid81(current)
    with pytest.raises(PublicationError, match="GENERATION_NOT_IMMEDIATE_SUCCESSOR"):
        publish_candidate(
            project_root=current,
            candidate_root=candidate,
            ledger=ledger,
            artifact_digest="a" * 64,
            expected_current_canonical_digest=previous.canonical_digest,
            expected_ledger_head=ledger.head,
            lock_path=tmp_path / "publisher.lock",
        )
    assert ledger.is_empty


def test_exact_reservation_resumes_after_exchange_failure(
    roots, ledger, tmp_path, monkeypatch
):
    current, candidate, candidate_state = roots
    previous = load_current_grid81(current)
    initial_head = ledger.head

    real = publisher._commit_exchange

    def injected_failure(left, right):
        raise PublicationError("INJECTED_AFTER_LEDGER_APPEND")

    monkeypatch.setattr(publisher, "_commit_exchange", injected_failure)
    with pytest.raises(PublicationError, match="INJECTED_AFTER_LEDGER_APPEND"):
        publish_candidate(
            project_root=current,
            candidate_root=candidate,
            ledger=ledger,
            artifact_digest="a" * 64,
            expected_current_canonical_digest=previous.canonical_digest,
            expected_ledger_head=initial_head,
            lock_path=tmp_path / "publisher.lock",
        )

    assert ledger.to_dict()["count"] == 1
    assert ledger.has_receipt("a" * 64)
    assert load_current_grid81(current).generation_number == 1

    monkeypatch.setattr(publisher, "_commit_exchange", real)
    resumed = publish_candidate(
        project_root=current,
        candidate_root=candidate,
        ledger=ledger,
        artifact_digest="a" * 64,
        expected_current_canonical_digest=previous.canonical_digest,
        expected_ledger_head=initial_head,
        lock_path=tmp_path / "publisher.lock",
    )
    assert resumed.status == "COMMITTED"
    assert resumed.resumed is True
    assert ledger.to_dict()["count"] == 1
    assert load_current_grid81(current).canonical_digest == candidate_state.canonical_digest


def test_different_receipt_for_consumed_artifact_is_rejected(roots, ledger, tmp_path):
    current, candidate, _ = roots
    previous = load_current_grid81(current)

    # Consume the artifact under an unrelated receipt identity.
    ledger.append(ledger.head, "b" * 64, "a" * 64)
    with pytest.raises(PublicationError, match="ARTIFACT_LEDGER_CONFLICT"):
        publish_candidate(
            project_root=current,
            candidate_root=candidate,
            ledger=ledger,
            artifact_digest="a" * 64,
            expected_current_canonical_digest=previous.canonical_digest,
            expected_ledger_head=ledger.to_dict()["entries"][0]["previous_head"],
            lock_path=tmp_path / "publisher.lock",
        )
    assert load_current_grid81(current).generation_number == 1


def test_atomic_exchange_preflight_failure_does_not_consume(
    roots, ledger, tmp_path, monkeypatch
):
    current, candidate, _ = roots
    previous = load_current_grid81(current)

    def unsupported(left, right):
        raise PublicationError("ATOMIC_EXCHANGE_UNSUPPORTED")

    monkeypatch.setattr(publisher, "_atomic_exchange", unsupported)
    with pytest.raises(PublicationError, match="ATOMIC_EXCHANGE_UNSUPPORTED"):
        publish_candidate(
            project_root=current,
            candidate_root=candidate,
            ledger=ledger,
            artifact_digest="a" * 64,
            expected_current_canonical_digest=previous.canonical_digest,
            expected_ledger_head=ledger.head,
            lock_path=tmp_path / "publisher.lock",
        )

    assert ledger.is_empty
    assert load_current_grid81(current).generation_number == 1
