"""Grid81 deterministic canonical candidate constructor R0.

This component constructs an immediate-successor canonical candidate in an
isolated output directory. It does not publish, mutate live canonical state,
or consume the durable publication ledger.

The constructor binds:
* a valid one-use ATOMIC_GRID81_CANONICAL_PROMOTION capability;
* the exact inert G5.3B structural-influence artifact named by that capability;
* the production-reader-verified current Grid81 state; and
* a new explicit canonical-generation.v2 semantic digest contract.

The output is a complete reader-valid Canonical/Grid81 tree suitable for the
authority-gated atomic publisher.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from Grid81.canonical_reader import CanonicalReadError, load_current_grid81
from elpis_grid81_consumption_compiler import (
    canonical_digest as artifact_canonical_digest,
    validate_artifact_invariants,
)
from elpis_grid81_promotion_authority import (
    PromotionAuthorityError,
    require_promotion_capability,
)


_HEX64 = re.compile(r"^[0-9a-f]{64}$")

_EXPECTED_TOP_LEVEL = frozenset({
    ".authority_audit.json",
    ".consumed_capability.json",
    ".consumption_receipt.json",
    ".source_nonmutation_audit.json",
    ".transaction_manifest.json",
    "HEAD.json",
    "generations",
})

_ARTIFACT_FIELDS = frozenset({
    "schema_version",
    "artifact_class",
    "materialization_class",
    "target_domain_class",
    "source_capability_digest",
    "source_capability_semantic_digest",
    "source_request_digest",
    "source_adjudication_record_digest",
    "source_proposal_set_digest",
    "authorized_proposal_digests",
    "proposal_bindings",
    "structural_influence_scope_digest",
    "consumer_class",
    "consumer_contract_digest",
    "consumption_request_digest",
    "consumption_receipt_digest",
    "logical_tick",
    "application_state",
    "compiler_contract_digest",
    "artifact_semantic_digest",
    "artifact_digest",
    "claims_not_made",
})


class CandidateConstructionError(ValueError):
    """Fail-closed candidate-construction rejection."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}:{detail}")


@dataclass(frozen=True)
class CandidateConstructionReceipt:
    candidate_root: str
    generation_number: int
    generation_path: str
    generation_raw_sha256: str
    generation_semantic_digest: str
    transaction_id: str
    capability_id: str
    capability_digest: str
    artifact_digest: str
    source_canonical_digest: str
    candidate_canonical_digest: str
    source_tree_digest: str
    candidate_tree_digest: str


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise CandidateConstructionError(code, detail)


def _hex64(value: Any) -> bool:
    return type(value) is str and _HEX64.fullmatch(value) is not None


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _domain_digest(domain: str, value: Any) -> str:
    return hashlib.sha256(
        domain.encode("ascii") + b"\0" + _canonical_bytes(value)
    ).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _tree_inventory(root: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise CandidateConstructionError(
                "SOURCE_SYMLINK_REJECTED",
                path.relative_to(root).as_posix(),
            )
        if path.is_file():
            records.append({
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha(path),
                "size": path.stat().st_size,
            })
    return records


def _tree_digest(root: Path) -> str:
    return _domain_digest(
        "elpis.grid81.canonical-tree.v1",
        _tree_inventory(root),
    )


def _validate_structural_artifact(
    artifact: dict,
    expected_digest: str,
    expected_structural_capability_digest: str,
) -> None:
    _require(type(artifact) is dict, "ARTIFACT_TYPE")
    _require(set(artifact) == _ARTIFACT_FIELDS, "ARTIFACT_FIELDS")
    _require(
        artifact.get("schema_version") == "structural-influence-artifact.v1",
        "ARTIFACT_SCHEMA",
    )

    valid, issues = validate_artifact_invariants(artifact)
    _require(
        valid,
        "ARTIFACT_INVARIANTS",
        issues[0] if issues else "unknown",
    )

    for field in (
        "source_capability_digest",
        "source_capability_semantic_digest",
        "source_request_digest",
        "source_adjudication_record_digest",
        "source_proposal_set_digest",
        "structural_influence_scope_digest",
        "consumer_contract_digest",
        "consumption_request_digest",
        "compiler_contract_digest",
        "artifact_semantic_digest",
        "artifact_digest",
    ):
        _require(_hex64(artifact.get(field)), f"ARTIFACT_{field.upper()}")

    receipt_digest = artifact.get("consumption_receipt_digest")
    _require(
        receipt_digest == "" or _hex64(receipt_digest),
        "ARTIFACT_CONSUMPTION_RECEIPT_DIGEST",
    )

    proposals = artifact.get("authorized_proposal_digests")
    _require(
        type(proposals) is list
        and proposals
        and proposals == sorted(set(proposals))
        and all(_hex64(item) for item in proposals),
        "ARTIFACT_PROPOSAL_SET",
    )

    bindings = artifact.get("proposal_bindings")
    _require(
        type(bindings) is list and len(bindings) == len(proposals),
        "ARTIFACT_PROPOSAL_BINDINGS",
    )

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
    _require(
        artifact["artifact_semantic_digest"]
        == artifact_canonical_digest(semantic_payload),
        "ARTIFACT_SEMANTIC_DIGEST_MISMATCH",
    )

    digest_payload = {
        key: value
        for key, value in artifact.items()
        if key != "artifact_digest"
    }
    _require(
        artifact["artifact_digest"]
        == artifact_canonical_digest(digest_payload),
        "ARTIFACT_DIGEST_MISMATCH",
    )
    _require(
        artifact["artifact_digest"] == expected_digest,
        "ARTIFACT_AUTHORITY_BINDING_MISMATCH",
    )
    _require(
        artifact["source_capability_digest"]
        == expected_structural_capability_digest,
        "ARTIFACT_STRUCTURAL_CAPABILITY_BINDING_MISMATCH",
    )


def _validate_authority_against_current(capability: dict, current: Any) -> None:
    target = capability["target_bindings"]

    _require(target["ledger"] == "Grid81", "AUTHORITY_LEDGER_MISMATCH")
    _require(
        target["source_generation"] == current.generation_number,
        "AUTHORITY_SOURCE_GENERATION_MISMATCH",
    )
    _require(
        target["target_generation"] == current.generation_number + 1,
        "AUTHORITY_TARGET_GENERATION_MISMATCH",
    )
    _require(
        target["source_canonical_digest"] == current.canonical_digest,
        "AUTHORITY_SOURCE_CANONICAL_DIGEST_MISMATCH",
    )
    _require(
        target["source_generation_semantic_digest"]
        == current.generation_semantic_digest,
        "AUTHORITY_SOURCE_SEMANTIC_DIGEST_MISMATCH",
    )
    _require(
        target["generation_target"]
        == (
            "Canonical/Grid81/generations/"
            f"{target['target_generation']:06d}.json"
        ),
        "AUTHORITY_GENERATION_TARGET_MISMATCH",
    )
    _require(
        target["head_target"] == "Canonical/Grid81/HEAD.json",
        "AUTHORITY_HEAD_TARGET_MISMATCH",
    )


def _generation_record(
    *,
    current: Any,
    capability: dict,
    artifact: dict,
) -> dict:
    source = capability["source_bindings"]
    target = capability["target_bindings"]

    generation = {
        "abi_version": "2.0.0",
        "authority_record": {
            "schema": "elpis.grid81.promotion-authority-binding.v1",
            "role": "canonical_candidate_construction",
            "capability_id": capability["capability_id"],
            "capability_digest": capability["capability_digest"],
            "authority_policy_digest": capability[
                "authority_policy_digest"
            ],
            "operator_approval_digest": capability[
                "operator_approval_digest"
            ],
            "promotion_plan_digest": source["promotion_plan_digest"],
            "promotion_decision_digest": source[
                "promotion_decision_digest"
            ],
        },
        "capability_consumption_record": {
            "schema": "elpis.grid81.capability-consumption-binding.v1",
            "capability_id": capability["capability_id"],
            "capability_digest": capability["capability_digest"],
            "consumed": True,
            "consumption_count": 1,
            "one_use": True,
        },
        "ecs_world_write_applied": False,
        "generation_number": target["target_generation"],
        "prior_generation_binding": current.generation_semantic_digest,
        "publication_reservation": {
            "expected_publication_ledger_head": target[
                "expected_publication_ledger_head"
            ],
            "transaction_id": target["transaction_id"],
        },
        "schema": "elpis.grid81.canonical-generation.v2",
        "shadow_promotion_evidence": {
            "application_receipt_digest": source[
                "application_receipt_digest"
            ],
            "resulting_state_digest": source["resulting_state_digest"],
            "source_application_ledger_head": source[
                "source_application_ledger_head"
            ],
        },
        "source_artifact_record": {
            "schema": "elpis.grid81.structural-artifact-binding.v1",
            "artifact_digest": artifact["artifact_digest"],
            "artifact_semantic_digest": artifact[
                "artifact_semantic_digest"
            ],
            "source_structural_capability_digest": artifact[
                "source_capability_digest"
            ],
            "source_proposal_set_digest": artifact[
                "source_proposal_set_digest"
            ],
            "application_state": artifact["application_state"],
        },
        "source_capability_digest": capability["capability_digest"],
        "source_chain_digest": source["source_chain_digest"],
        "transaction_id": target["transaction_id"],
        "type": "append_only_canonical_promotion",
    }

    generation["generation_semantic_digest"] = _domain_digest(
        "elpis.grid81.canonical-generation.v2.semantic",
        generation,
    )
    return generation


def _head_record(
    *,
    current: Any,
    capability: dict,
    generation: dict,
    generation_hash: str,
) -> dict:
    return {
        "append_only": True,
        "capability_consumed_id": capability["capability_id"],
        "capability_id": capability["capability_id"],
        "ecs_world_write_applied": False,
        "generation": generation["generation_number"],
        "generation_file_sha256": generation_hash,
        "generation_path": capability["target_bindings"][
            "generation_target"
        ],
        "generation_semantic_digest": generation[
            "generation_semantic_digest"
        ],
        "ledger": "Grid81",
        "previous_generation_binding": current.generation_semantic_digest,
        "schema": "elpis.grid81.canonical-head.v2",
        "transaction_id": capability["target_bindings"]["transaction_id"],
    }


def _consumed_projection(capability: dict) -> dict:
    consumed = copy.deepcopy(capability)
    consumed["lifecycle"] = {
        "state": "CONSUMED",
        "consumed": True,
        "consumption_count": 1,
        "replay_permitted": False,
    }
    return consumed


def construct_candidate(
    *,
    project_root: Path | str,
    candidate_root: Path | str,
    promotion_capability: dict,
    structural_artifact: dict,
) -> CandidateConstructionReceipt:
    """Construct one isolated immediate-successor Grid81 candidate."""

    project_root = Path(project_root).resolve()
    candidate_root = Path(candidate_root).resolve()

    try:
        capability = require_promotion_capability(promotion_capability)
    except PromotionAuthorityError as exc:
        raise CandidateConstructionError(
            "PROMOTION_CAPABILITY_INVALID",
            exc.detail or exc.code,
        ) from exc

    _validate_structural_artifact(
        structural_artifact,
        capability["source_bindings"]["artifact_digest"],
        capability["source_bindings"]["structural_capability_digest"],
    )

    try:
        current = load_current_grid81(project_root)
    except CanonicalReadError as exc:
        raise CandidateConstructionError(
            "CURRENT_CANONICAL_READER_REJECTED",
            exc.code,
        ) from exc

    _validate_authority_against_current(capability, current)

    live_grid = project_root / "Canonical" / "Grid81"
    _require(live_grid.is_dir(), "LIVE_GRID81_NOT_FOUND")
    _require(
        {path.name for path in live_grid.iterdir()} == _EXPECTED_TOP_LEVEL,
        "LIVE_GRID81_TOP_LEVEL_CONTRACT",
    )

    try:
        candidate_root.relative_to(project_root)
    except ValueError:
        pass
    else:
        raise CandidateConstructionError(
            "CANDIDATE_ROOT_INSIDE_PROJECT_ROOT"
        )

    _require(not candidate_root.exists(), "CANDIDATE_ROOT_EXISTS")
    candidate_root.parent.mkdir(parents=True, exist_ok=True)

    source_tree_before = _tree_digest(live_grid)
    source_inventory_before = _tree_inventory(live_grid)

    temp_root = Path(tempfile.mkdtemp(
        prefix=f".{candidate_root.name}.build.",
        dir=candidate_root.parent,
    ))

    try:
        candidate_grid = temp_root / "Canonical" / "Grid81"
        shutil.copytree(
            live_grid,
            candidate_grid,
            copy_function=shutil.copy2,
        )

        target = capability["target_bindings"]
        source = capability["source_bindings"]

        generation = _generation_record(
            current=current,
            capability=capability,
            artifact=structural_artifact,
        )
        generation_path = temp_root / target["generation_target"]
        _require(
            not generation_path.exists(),
            "TARGET_GENERATION_ALREADY_EXISTS",
        )
        _write_json(generation_path, generation)
        generation_hash = _sha(generation_path)

        consumed_path = candidate_grid / ".consumed_capability.json"
        consumed = _consumed_projection(capability)
        _write_json(consumed_path, consumed)
        consumed_hash = _sha(consumed_path)

        head_path = candidate_grid / "HEAD.json"
        head = _head_record(
            current=current,
            capability=capability,
            generation=generation,
            generation_hash=generation_hash,
        )
        _write_json(head_path, head)
        head_hash = _sha(head_path)

        receipt_path = candidate_grid / ".consumption_receipt.json"
        receipt = {
            "schema": "elpis.grid81.canonical-consumption-receipt.v2",
            "authorization_digest": capability[
                "authority_policy_digest"
            ],
            "capability_consumed": True,
            "capability_digest": capability["capability_digest"],
            "capability_id": capability["capability_id"],
            "commit_status": "COMMITTED",
            "consumed_capability_sha256": consumed_hash,
            "consumption_count": 1,
            "consumption_receipt": True,
            "ecs_world_write_applied": False,
            "generation_file_sha256": generation_hash,
            "head_file_sha256": head_hash,
            "one_use": True,
            "source_chain_digest": source["source_chain_digest"],
            "source_artifact_digest": structural_artifact[
                "artifact_digest"
            ],
            "transaction_id": target["transaction_id"],
        }
        _write_json(receipt_path, receipt)
        receipt_hash = _sha(receipt_path)

        source_tree_after = _tree_digest(live_grid)
        source_inventory_after = _tree_inventory(live_grid)
        _require(
            source_tree_after == source_tree_before
            and source_inventory_after == source_inventory_before,
            "SOURCE_CANONICAL_MUTATED_DURING_CONSTRUCTION",
        )

        source_audit_path = (
            candidate_grid / ".source_nonmutation_audit.json"
        )
        source_audit = {
            "schema": "elpis.grid81.source-nonmutation-audit.v2",
            "live_canonical_modified": False,
            "source_tree_digest_before": source_tree_before,
            "source_tree_digest_after": source_tree_after,
            "source_artifact_digest": structural_artifact[
                "artifact_digest"
            ],
            "promotion_capability_digest": capability[
                "capability_digest"
            ],
            "transaction_id": target["transaction_id"],
        }
        _write_json(source_audit_path, source_audit)
        source_audit_hash = _sha(source_audit_path)

        authority_audit_path = candidate_grid / ".authority_audit.json"
        authority_audit = {
            "schema": "elpis.grid81.promotion-authority-audit.v2",
            "authorization_valid": True,
            "candidate_only": True,
            "canonical_write_applied": False,
            "ecs_world_write_applied": False,
            "promotion_capability_digest": capability[
                "capability_digest"
            ],
            "capability_id": capability["capability_id"],
            "authority_policy_digest": capability[
                "authority_policy_digest"
            ],
            "operator_approval_digest": capability[
                "operator_approval_digest"
            ],
            "source_artifact_digest": structural_artifact[
                "artifact_digest"
            ],
            "source_canonical_digest": current.canonical_digest,
            "source_generation": current.generation_number,
            "target_generation": target["target_generation"],
            "transaction_id": target["transaction_id"],
        }
        _write_json(authority_audit_path, authority_audit)
        authority_audit_hash = _sha(authority_audit_path)

        manifest_path = candidate_grid / ".transaction_manifest.json"
        manifest = {
            "schema": "elpis.grid81.canonical-transaction-manifest.v2",
            "artifact_inventory": [
                {
                    "artifact_role": "authority_audit",
                    "byte_size": authority_audit_path.stat().st_size,
                    "generation_order": 1,
                    "relative_path": (
                        "Canonical/Grid81/.authority_audit.json"
                    ),
                    "sha256": authority_audit_hash,
                },
                {
                    "artifact_role": "consumed_capability",
                    "byte_size": consumed_path.stat().st_size,
                    "generation_order": 2,
                    "relative_path": (
                        "Canonical/Grid81/.consumed_capability.json"
                    ),
                    "sha256": consumed_hash,
                },
                {
                    "artifact_role": "consumption_receipt",
                    "byte_size": receipt_path.stat().st_size,
                    "generation_order": 3,
                    "relative_path": (
                        "Canonical/Grid81/.consumption_receipt.json"
                    ),
                    "sha256": receipt_hash,
                },
                {
                    "artifact_role": "source_nonmutation_audit",
                    "byte_size": source_audit_path.stat().st_size,
                    "generation_order": 4,
                    "relative_path": (
                        "Canonical/Grid81/.source_nonmutation_audit.json"
                    ),
                    "sha256": source_audit_hash,
                },
                {
                    "artifact_role": "transaction_manifest",
                    "byte_size": 0,
                    "generation_order": 5,
                    "relative_path": (
                        "Canonical/Grid81/.transaction_manifest.json"
                    ),
                    "sha256": "",
                },
                {
                    "artifact_role": "canonical_head",
                    "byte_size": head_path.stat().st_size,
                    "generation_order": 6,
                    "relative_path": "Canonical/Grid81/HEAD.json",
                    "sha256": head_hash,
                },
                {
                    "artifact_role": "canonical_generation",
                    "byte_size": generation_path.stat().st_size,
                    "generation_order": 7,
                    "relative_path": target["generation_target"],
                    "sha256": generation_hash,
                },
            ],
            "authorization_digest": capability[
                "authority_policy_digest"
            ],
            "capability_id": capability["capability_id"],
            "commit_point": (
                "atomic directory exchange after durable "
                "publication-ledger reservation"
            ),
            "generation": target["target_generation"],
            "ordered_actions": [
                "validate_promotion_capability",
                "validate_structural_artifact",
                "verify_live_canonical_source",
                "construct_isolated_candidate",
                "verify_reader_valid_candidate",
                "reserve_publication_ledger_receipt",
                "atomic_directory_exchange",
                "verify_committed_state",
            ],
            "promotion_capability_digest": capability[
                "capability_digest"
            ],
            "source_artifact_digest": structural_artifact[
                "artifact_digest"
            ],
            "transaction_id": target["transaction_id"],
            "transaction_state": "PREPARED",
        }
        _write_json(manifest_path, manifest)

        try:
            candidate_state = load_current_grid81(temp_root)
        except CanonicalReadError as exc:
            raise CandidateConstructionError(
                "CANDIDATE_READER_REJECTED",
                exc.code,
            ) from exc

        _require(
            candidate_state.generation_number
            == target["target_generation"],
            "CANDIDATE_GENERATION_VERIFY_MISMATCH",
        )
        _require(
            candidate_state.transaction_id == target["transaction_id"],
            "CANDIDATE_TRANSACTION_VERIFY_MISMATCH",
        )
        _require(
            candidate_state.capability_id == capability["capability_id"],
            "CANDIDATE_CAPABILITY_VERIFY_MISMATCH",
        )

        source_tree_final = _tree_digest(live_grid)
        _require(
            source_tree_final == source_tree_before,
            "SOURCE_CANONICAL_MUTATED_AFTER_VERIFY",
        )

        candidate_tree_digest = _tree_digest(candidate_grid)
        os.replace(temp_root, candidate_root)

        final_state = load_current_grid81(candidate_root)
        _require(
            final_state.canonical_digest
            == candidate_state.canonical_digest,
            "CANDIDATE_RENAME_CHANGED_IDENTITY",
        )

        return CandidateConstructionReceipt(
            candidate_root=str(candidate_root),
            generation_number=final_state.generation_number,
            generation_path=final_state.generation_path,
            generation_raw_sha256=final_state.generation_raw_sha256,
            generation_semantic_digest=(
                final_state.generation_semantic_digest
            ),
            transaction_id=final_state.transaction_id,
            capability_id=final_state.capability_id,
            capability_digest=capability["capability_digest"],
            artifact_digest=structural_artifact["artifact_digest"],
            source_canonical_digest=current.canonical_digest,
            candidate_canonical_digest=final_state.canonical_digest,
            source_tree_digest=source_tree_before,
            candidate_tree_digest=candidate_tree_digest,
        )

    except Exception:
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
        raise
