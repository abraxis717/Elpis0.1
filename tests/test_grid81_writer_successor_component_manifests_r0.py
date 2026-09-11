from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

SPECS = {
    "Grid81_Canonical_Promotion_Authority": Path(
        "components/Grid81DeterministicCanonicalPromotionAuthority"
    ),
    "Grid81_Canonical_Candidate_Constructor": Path(
        "components/Grid81DeterministicCanonicalCandidateConstructor"
    ),
    "Grid81_Atomic_Canonical_Publisher": Path(
        "components/Grid81DeterministicCanonicalPublisher"
    ),
}

REGISTRY = ROOT / "manifests/GRID81_WRITER_CHAIN_SUCCESSOR_REGISTRY_R0.json"
PUBLIC = ROOT / "manifests/PUBLIC_COMPONENT_REGISTRY.json"
CANONICAL = ROOT / "ELPIS_CANONICAL_MANIFEST.json"


def _canonical_bytes(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tracked_inventory(component: Path):
    names = subprocess.check_output(
        ["git", "ls-files", component.as_posix()],
        cwd=ROOT,
        text=True,
    ).splitlines()
    names = sorted(
        name for name in names
        if Path(name).name != "COMPONENT_MANIFEST.json"
    )
    return [
        {
            "path": Path(name).relative_to(component).as_posix(),
            "sha256": _sha_file(ROOT / name),
            "size": (ROOT / name).stat().st_size,
        }
        for name in names
    ]


def _without(mapping: dict, field: str):
    return {
        key: value
        for key, value in mapping.items()
        if key != field
    }


def test_successor_component_manifests_are_reproducible_and_fail_closed():
    seen = set()
    for component_id, component in SPECS.items():
        path = ROOT / component / "COMPONENT_MANIFEST.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))

        assert manifest["schema"] == (
            "elpis.component-manifest.successor-engineering.v1"
        )
        assert manifest["component_id"] == component_id
        assert component_id not in seen
        seen.add(component_id)

        assert manifest["qualification_disposition"] == (
            "QUALIFIED_LOCAL_SUCCESSOR"
        )
        assert manifest["runtime_admission"] is False
        assert manifest["public_registry_admission"] is False

        inventory = _tracked_inventory(component)
        assert manifest["source_inventory"] == inventory
        expected_inventory_digest = _sha_bytes(
            b"elpis.writer-component.inventory.v1\0"
            + _canonical_bytes(inventory)
        )
        assert manifest["source_inventory_digest"] == (
            expected_inventory_digest
        )

        expected_self_hash = _sha_bytes(
            _canonical_bytes(
                _without(manifest, "manifest_self_hash")
            )
        )
        assert manifest["manifest_self_hash"] == expected_self_hash

        assert manifest["claims_not_made"] == [
            "does not imply runtime admission",
            (
                "does not imply inclusion in "
                "manifests/PUBLIC_COMPONENT_REGISTRY.json"
            ),
            "does not reconstruct legacy promotion-receipt provenance",
            "does not alter the Elpis2.1.16 public release boundary",
        ]


def test_successor_registry_binds_exact_component_manifests():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert registry["schema"] == (
        "elpis.grid81.writer-chain.successor-registry.v1"
    )
    assert registry["registry_id"] == (
        "GRID81_WRITER_CHAIN_SUCCESSOR_REGISTRY_R0"
    )
    assert registry["component_count"] == 3
    assert registry["runtime_admission"] is False
    assert registry["public_registry_admission"] is False
    assert registry["legacy_assembly_metadata_unchanged"] is True

    by_id = {
        item["component_id"]: item
        for item in registry["components"]
    }
    assert set(by_id) == set(SPECS)

    for component_id, component in SPECS.items():
        manifest = json.loads(
            (
                ROOT / component / "COMPONENT_MANIFEST.json"
            ).read_text(encoding="utf-8")
        )
        entry = by_id[component_id]
        assert entry["manifest_self_hash"] == (
            manifest["manifest_self_hash"]
        )
        assert entry["source_inventory_digest"] == (
            manifest["source_inventory_digest"]
        )
        assert entry["runtime_admission"] is False
        assert entry["public_registry_admission"] is False

    expected_self_hash = _sha_bytes(
        _canonical_bytes(
            _without(registry, "registry_self_hash")
        )
    )
    assert registry["registry_self_hash"] == expected_self_hash


def test_legacy_public_and_canonical_assembly_metadata_remain_frozen():
    public = json.loads(PUBLIC.read_text(encoding="utf-8"))
    canonical = json.loads(CANONICAL.read_text(encoding="utf-8"))

    assert public["component_count"] == 16
    assert canonical["component_count"] == 17

    public_ids = {
        item["component_id"]
        for item in public["components"]
    }
    canonical_ids = {
        item["component_id"]
        for item in canonical["components"]
    }

    for component_id in SPECS:
        assert component_id not in public_ids
        assert component_id not in canonical_ids


def test_qualification_commits_are_ancestors_of_current_engineering_head():
    for component in SPECS.values():
        manifest = json.loads(
            (
                ROOT / component / "COMPONENT_MANIFEST.json"
            ).read_text(encoding="utf-8")
        )
        for commit in manifest["qualification_commits"]:
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
                cwd=ROOT,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
