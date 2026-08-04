"""
G5.3I-G.1 Adversarial Runtime Consumer Matrix

28 adversarial scenarios testing the production canonical reader
and runtime consumer integration boundary. Each scenario proves both:
  1. Reader rejected malformed canonical state
  2. Runtime consumer received no object
"""

import copy
import hashlib
import json
import os
import pathlib
import shutil
import tempfile

import pytest

# Import production reader
import sys as _sys
_root = str(pathlib.Path(__file__).resolve().parent.parent)
if _root not in _sys.path:
    _sys.path.insert(0, _root)

from Grid81.canonical_reader import CanonicalReadError, load_current_grid81
from elpis_header.observer.grid81_reducer import load_grid81_runtime_state


PROJECT_ROOT = pathlib.Path("/mnt/primesauce/Elpis_Canon")
CANONICAL_DIR = PROJECT_ROOT / "Canonical" / "Grid81"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_copy_canonical(tmp_root: pathlib.Path) -> None:
    """Copy Grid81 canonical files into a temporary root."""
    dst = tmp_root / "Canonical" / "Grid81"
    dst.mkdir(parents=True)
    for f in CANONICAL_DIR.iterdir():
        src_path = CANONICAL_DIR / f.name
        dst_path = dst / f.name
        if src_path.is_dir():
            shutil.copytree(src_path, dst_path)
        else:
            shutil.copy2(str(src_path), str(dst_path))


def _modify_file(tmp_root: pathlib.Path, rel_path: str, mutator) -> None:
    p = tmp_root / rel_path
    data = json.loads(p.read_text())
    data = mutator(data)
    p.write_text(json.dumps(data, indent=2))


def _test_scenario(tmp_root: pathlib.Path):
    """Run one adversarial scenario: reader rejects, runtime gets nothing."""
    reader_rejected = False
    runtime_object = None

    try:
        state = load_current_grid81(tmp_root)
    except CanonicalReadError:
        reader_rejected = True

    assert reader_rejected, "Reader did not reject malformed canonical state"

    try:
        runtime = load_grid81_runtime_state(tmp_root)
        runtime_object = runtime
    except CanonicalReadError:
        pass

    assert runtime_object is None, "Runtime consumer received object despite rejection"


# ---------------------------------------------------------------------------
# 28 scenarios
# ---------------------------------------------------------------------------

class TestAdversarialRuntimeConsumer:

    # --- HEAD tampering (4) ---

    def test_001_head_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            (root / "Canonical" / "Grid81" / "HEAD.json").unlink()
            _test_scenario(root)

    def test_002_head_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            (root / "Canonical" / "Grid81" / "HEAD.json").write_text("{invalid json")
            _test_scenario(root)

    def test_003_head_wrong_generation_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            _modify_file(root, "Canonical/Grid81/HEAD.json",
                lambda d: {**d, "generation_file_sha256": "0" * 64})
            _test_scenario(root)

    def test_004_head_wrong_semantic_digest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            _modify_file(root, "Canonical/Grid81/HEAD.json",
                lambda d: {**d, "generation_semantic_digest": "0" * 64})
            _test_scenario(root)

    # --- Generation tampering (4) ---

    def test_005_generation_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            (root / "Canonical" / "Grid81" / "generations" / "000001.json").unlink()
            _test_scenario(root)

    def test_006_generation_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            (root / "Canonical" / "Grid81" / "generations" / "000001.json").write_text("NOT_JSON")
            _test_scenario(root)

    def test_007_generation_wrong_transaction_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            _modify_file(root, "Canonical/Grid81/generations/000001.json",
                lambda d: {**d, "transaction_id": "0" * 64})
            _test_scenario(root)

    def test_008_generation_wrong_capability_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            _modify_file(root, "Canonical/Grid81/generations/000001.json",
                lambda d: {**d, "authority_record": {**d.get("authority_record", {}), "capability_id": "0" * 64}})
            _test_scenario(root)

    # --- Symlink/path traversal (3) ---

    def test_009_head_symlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            head = root / "Canonical" / "Grid81" / "HEAD.json"
            real = head.with_suffix(".json.real")
            shutil.move(str(head), str(real))
            head.symlink_to(real)
            _test_scenario(root)

    def test_010_generation_symlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            gen = root / "Canonical" / "Grid81" / "generations" / "000001.json"
            real = gen.with_suffix(".json.real")
            shutil.move(str(gen), str(real))
            gen.symlink_to(real)
            _test_scenario(root)

    def test_011_manifest_symlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            mf = root / "Canonical" / "Grid81" / ".transaction_manifest.json"
            real = mf.with_suffix(".json.real")
            shutil.move(str(mf), str(real))
            mf.symlink_to(real)
            _test_scenario(root)

    # --- Manifest tampering (4) ---

    def test_012_manifest_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            (root / "Canonical" / "Grid81" / ".transaction_manifest.json").unlink()
            _test_scenario(root)

    def test_013_manifest_wrong_transaction_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            _modify_file(root, "Canonical/Grid81/.transaction_manifest.json",
                lambda d: {**d, "transaction_id": "0" * 64})
            _test_scenario(root)

    def test_014_manifest_wrong_capability_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            _modify_file(root, "Canonical/Grid81/.transaction_manifest.json",
                lambda d: {**d, "capability_id": "0" * 64})
            _test_scenario(root)

    def test_015_manifest_wrong_hash_authority_audit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            _modify_file(root, "Canonical/Grid81/.transaction_manifest.json",
                lambda d: {**d, "artifact_inventory": [
                    {**a, "sha256": "0" * 64} if a.get("artifact_role") == "authority_audit" else a
                    for a in d.get("artifact_inventory", [])
                ]})
            _test_scenario(root)

    # --- Lifecycle tampering (4) ---

    def test_016_consumed_capability_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            (root / "Canonical" / "Grid81" / ".consumed_capability.json").unlink()
            _test_scenario(root)

    def test_017_capability_not_consumed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            _modify_file(root, "Canonical/Grid81/.consumed_capability.json",
                lambda d: {**d, "lifecycle": {**d.get("lifecycle", {}), "consumed": False}})
            _test_scenario(root)

    def test_018_consumption_receipt_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            (root / "Canonical" / "Grid81" / ".consumption_receipt.json").unlink()
            _test_scenario(root)

    def test_019_receipt_not_committed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            _modify_file(root, "Canonical/Grid81/.consumption_receipt.json",
                lambda d: {**d, "commit_status": "UNCOMMITTED"})
            _test_scenario(root)

    # --- Missing files (4) ---

    def test_020_authority_audit_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            (root / "Canonical" / "Grid81" / ".authority_audit.json").unlink()
            _test_scenario(root)

    def test_021_source_nonmutation_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            (root / "Canonical" / "Grid81" / ".source_nonmutation_audit.json").unlink()
            _test_scenario(root)

    def test_022_canonical_dir_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            shutil.rmtree(str(root / "Canonical" / "Grid81"))
            _test_scenario(root)

    def test_023_unexpected_file_in_canonical(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            (root / "Canonical" / "Grid81" / ".sneaky_backdoor.json").write_text("{}")
            _test_scenario(root)

    # --- Cross-field consistency (3) ---

    def test_024_head_generation_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            _modify_file(root, "Canonical/Grid81/HEAD.json",
                lambda d: {**d, "generation": 999})
            _test_scenario(root)

    def test_025_head_txn_vs_generation_txn_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            _modify_file(root, "Canonical/Grid81/HEAD.json",
                lambda d: {**d, "transaction_id": "0" * 64})
            _test_scenario(root)

    def test_026_head_capability_vs_generation_capability_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            _modify_file(root, "Canonical/Grid81/HEAD.json",
                lambda d: {**d, "capability_id": "0" * 64})
            _test_scenario(root)

    # --- Edge cases (2) ---

    def test_027_generation_content_modified(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _deep_copy_canonical(root)
            gen_path = root / "Canonical" / "Grid81" / "generations" / "000001.json"
            data = json.loads(gen_path.read_text())
            data["generation_number"] = 999
            gen_path.write_text(json.dumps(data, indent=2))
            _test_scenario(root)

    def test_028_empty_project_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            _test_scenario(root)
