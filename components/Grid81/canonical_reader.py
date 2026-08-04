"""
Grid81 Canonical Reader — production-grade, reusable, read-only loader.

Resolves Grid81 canonical state through HEAD-first lookup, verifies all
integrity hashes, and returns a frozen immutable representation suitable
for consumption by Elpis runtime components.

No writes, no phase-harness imports, no report generation.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import dataclass, field
from typing import Any, FrozenSet, Optional


# ---------------------------------------------------------------------------
# Typed rejection
# ---------------------------------------------------------------------------

class CanonicalReadError(Exception):
    """Fail-closed rejection for Grid81 canonical reads."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"[{code}] {detail}")


# ---------------------------------------------------------------------------
# Immutable canonical state
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Grid81CanonicalState:
    """Frozen, immutable representation of Grid81 canonical state.

    All fields are read-only. No internal dicts are mutable.
    """

    generation_number: int
    generation_path: str
    generation_raw_sha256: str
    generation_semantic_digest: str
    transaction_id: str
    capability_id: str
    capability_state: str  # e.g. "CONSUMED"
    consumption_count: int
    replay_permitted: bool
    structural_schema: str

    # Canonical file locations (relative to project root)
    head_path: str
    manifest_path: str

    # Verified manifest hashes (six ordinary files, self-entry unhashed)
    manifest_hash_authority_audit: str
    manifest_hash_consumed_capability: str
    manifest_hash_consumption_receipt: str
    manifest_hash_source_nonmutation_audit: str
    manifest_hash_head: str
    manifest_hash_generation: str

    # Payload reference (full generation payload as frozen dict)
    _payload: dict[str, Any] = field(repr=False, compare=False)

    # Integrity proof
    canonical_digest: str

    @property
    def payload(self) -> FrozenSet:
        """Read-only access — returns frozenset of items to prevent mutation."""
        return frozenset(self._payload.items())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _load_json(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise CanonicalReadError(
            f"INVALID_JSON_{path.name}",
            f"Cannot parse {path}: {exc}",
        ) from exc


def _resolve_no_symlink(path: pathlib.Path, label: str) -> pathlib.Path:
    if path.is_symlink():
        raise CanonicalReadError(
            "SYMLINK_REJECTED",
            f"{label} is a symlink: {path} -> {path.resolve()}",
        )
    real = path.resolve()
    if not str(real).startswith(str(path.parent.resolve())):
        raise CanonicalReadError(
            "PATH_TRAVERSAL_REJECTED",
            f"{label} escapes project root: {path} -> {real}",
        )
    return real


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

# Expected manifest entries (six ordinary; transaction_manifest is self)
_MANIFEST_ROLES: frozenset = frozenset({
    "authority_audit",
    "consumed_capability",
    "consumption_receipt",
    "source_nonmutation_audit",
    "canonical_head",
    "canonical_generation",
})


def load_current_grid81(project_root: pathlib.Path) -> Grid81CanonicalState:
    """Load and verify Grid81 canonical state via HEAD-first resolution.

    Parameters
    ----------
    project_root : pathlib.Path
        Absolute path to the Elpis project root.

    Returns
    -------
    Grid81CanonicalState
        Frozen canonical state ready for runtime consumption.

    Raises
    ------
    CanonicalReadError
        On any verification failure. Fail-closed with typed code.
    """
    root = _resolve_no_symlink(project_root, "project_root")

    # --- 1. Resolve HEAD first ------------------------------------------------
    head_path = root / "Canonical" / "Grid81" / "HEAD.json"
    if not head_path.is_file():
        raise CanonicalReadError(
            "HEAD_NOT_FOUND",
            f"HEAD.json not found at {head_path}",
        )
    _resolve_no_symlink(head_path, "HEAD.json")
    head = _load_json(head_path)

    generation_number = head.get("generation")
    if generation_number is None:
        raise CanonicalReadError("HEAD_MISSING_GENERATION", "HEAD has no 'generation'")

    # --- 2. Reject direct-generation default loading ---------------------------
    head_generation_path = head.get("generation_path")
    if head_generation_path is None:
        raise CanonicalReadError(
            "HEAD_MISSING_GENERATION_PATH",
            "HEAD has no 'generation_path'",
        )

    gen_path = root / head_generation_path
    _resolve_no_symlink(gen_path, "generation")
    if not gen_path.is_file():
        raise CanonicalReadError(
            "GENERATION_NOT_FOUND",
            f"Generation file missing: {gen_path}",
        )

    # --- 3. Verify raw generation hash ----------------------------------------
    raw_hash = _sha256_file(gen_path)
    head_raw_hash = head.get("generation_file_sha256")
    if head_raw_hash != raw_hash:
        raise CanonicalReadError(
            "GENERATION_RAW_HASH_MISMATCH",
            f"HEAD says {head_raw_hash}, actual {raw_hash}",
        )

    # --- 4. Load and verify generation semantic digest -------------------------
    gen = _load_json(gen_path)
    gen_semantic_digest = gen.get("generation_semantic_digest")
    head_semantic_digest = head.get("generation_semantic_digest")
    if gen_semantic_digest != head_semantic_digest:
        raise CanonicalReadError(
            "SEMANTIC_DIGEST_MISMATCH",
            f"Generation {gen_semantic_digest} != HEAD {head_semantic_digest}",
        )

    # --- 5. Verify transaction ID consistency ---------------------------------
    txn_id_head = head.get("transaction_id")
    txn_id_gen = gen.get("transaction_id")
    if txn_id_head != txn_id_gen:
        raise CanonicalReadError(
            "TRANSACTION_ID_MISMATCH",
            f"HEAD {txn_id_head} != generation {txn_id_gen}",
        )

    # --- 6. Verify capability ID consistency ----------------------------------
    cap_id_head = head.get("capability_id")
    cap_id_gen = gen.get("authority_record", {}).get("capability_id", "")
    if cap_id_head != cap_id_gen:
        raise CanonicalReadError(
            "CAPABILITY_ID_MISMATCH",
            f"HEAD {cap_id_head} != generation {cap_id_gen}",
        )

    # --- 7. Load and verify transaction manifest ------------------------------
    manifest_path = root / "Canonical" / "Grid81" / ".transaction_manifest.json"
    _resolve_no_symlink(manifest_path, "transaction_manifest")
    manifest = _load_json(manifest_path)

    manifest_txn = manifest.get("transaction_id")
    if manifest_txn != txn_id_head:
        raise CanonicalReadError(
            "MANIFEST_TRANSACTION_ID_MISMATCH",
            f"Manifest {manifest_txn} != HEAD {txn_id_head}",
        )

    manifest_cap = manifest.get("capability_id")
    if manifest_cap != cap_id_head:
        raise CanonicalReadError(
            "MANIFEST_CAPABILITY_ID_MISMATCH",
            f"Manifest {manifest_cap} != HEAD {cap_id_head}",
        )

    # --- 8. Verify canonical consumed lifecycle --------------------------------
    consumed_cap_path = root / "Canonical" / "Grid81" / ".consumed_capability.json"
    _resolve_no_symlink(consumed_cap_path, "consumed_capability")
    consumed_cap = _load_json(consumed_cap_path)

    lifecycle = consumed_cap.get("lifecycle", {})
    capability_state = lifecycle.get("state", "UNKNOWN")
    if lifecycle.get("consumed") is not True:
        raise CanonicalReadError(
            "CAPABILITY_NOT_CONSUMED",
            f"Capability lifecycle state is {capability_state}, expected CONSUMED",
        )

    consumption_count = lifecycle.get("consumption_count", 0)
    replay_permitted = lifecycle.get("replay_permitted", True)

    # --- 9. Verify consumption receipt ----------------------------------------
    receipt_path = root / "Canonical" / "Grid81" / ".consumption_receipt.json"
    _resolve_no_symlink(receipt_path, "consumption_receipt")
    receipt = _load_json(receipt_path)

    if receipt.get("commit_status") != "COMMITTED":
        raise CanonicalReadError(
            "RECEIPT_NOT_COMMITTED",
            f"Receipt commit_status is {receipt.get('commit_status')}",
        )

    # --- 10. Verify six ordinary manifest hashes (self-entry intentionally unhashed)
    grid81_dir = root / "Canonical" / "Grid81"

    # Build role->expected hash map from manifest
    role_hashes: dict[str, tuple[str, pathlib.Path]] = {}
    for artifact in manifest.get("artifact_inventory", []):
        role = artifact.get("artifact_role")
        rel = artifact.get("relative_path", "")
        expected_hash = artifact.get("sha256", "")

        if role in _MANIFEST_ROLES:
            abs_path = root / rel
            role_hashes[role] = (expected_hash, abs_path)

    # Verify each ordinary file
    for role, (expected_hash, abs_path) in role_hashes.items():
        _resolve_no_symlink(abs_path, role)
        if not abs_path.is_file():
            raise CanonicalReadError(
                f"MANIFEST_FILE_MISSING_{role.upper()}",
                f"Manifest references {role} at {abs_path} but file missing",
            )
        actual_hash = _sha256_file(abs_path)

        # INTENTIONALLY_UNHASHED_SELF_ENTRY: transaction_manifest sha256 is ""
        if expected_hash and actual_hash != expected_hash:
            raise CanonicalReadError(
                f"MANIFEST_HASH_MISMATCH_{role.upper()}",
                f"Expected {expected_hash}, got {actual_hash} for {role}",
            )

    # --- 11. Reject unexpected canonical files --------------------------------
    expected_files: set[str] = {p.name for _, p in role_hashes.values()}
    # Also include the manifest itself and the generations directory
    expected_files.add(".transaction_manifest.json")
    expected_files.add("HEAD.json")
    expected_files.add("generations")

    actual_files = {entry.name for entry in grid81_dir.iterdir()}
    unexpected = actual_files - expected_files
    if unexpected:
        raise CanonicalReadError(
            "UNEXPECTED_CANONICAL_FILES",
            f"Unexpected files in Grid81 directory: {unexpected}",
        )

    # --- 12. Compute canonical digest for determinism --------------------------
    canonical_payload = json.dumps({
        "generation_number": generation_number,
        "generation_raw_sha256": raw_hash,
        "generation_semantic_digest": gen_semantic_digest,
        "transaction_id": txn_id_head,
        "capability_id": cap_id_head,
        "capability_state": capability_state,
    }, sort_keys=True)
    canonical_digest = hashlib.sha256(canonical_payload.encode()).hexdigest()

    # --- 13. Return frozen state -----------------------------------------------
    return Grid81CanonicalState(
        generation_number=generation_number,
        generation_path=head_generation_path,
        generation_raw_sha256=raw_hash,
        generation_semantic_digest=gen_semantic_digest,
        transaction_id=txn_id_head,
        capability_id=cap_id_head,
        capability_state=capability_state,
        consumption_count=consumption_count,
        replay_permitted=replay_permitted,
        structural_schema=gen.get("schema", ""),
        head_path=str(head_path.relative_to(root)),
        manifest_path=str(manifest_path.relative_to(root)),
        manifest_hash_authority_audit=role_hashes.get("authority_audit", ("", None))[0],
        manifest_hash_consumed_capability=role_hashes.get("consumed_capability", ("", None))[0],
        manifest_hash_consumption_receipt=role_hashes.get("consumption_receipt", ("", None))[0],
        manifest_hash_source_nonmutation_audit=role_hashes.get("source_nonmutation_audit", ("", None))[0],
        manifest_hash_head=role_hashes.get("canonical_head", ("", None))[0],
        manifest_hash_generation=role_hashes.get("canonical_generation", ("", None))[0],
        _payload=dict(gen),
        canonical_digest=canonical_digest,
    )
