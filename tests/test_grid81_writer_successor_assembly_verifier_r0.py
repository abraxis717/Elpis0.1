from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
VERIFY_PATH = ROOT / "tools/verify_grid81_writer_successor_assembly.py"

spec = importlib.util.spec_from_file_location(
    "verify_grid81_writer_successor_assembly",
    VERIFY_PATH,
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def _copy_authority_tree(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()

    files = [
        Path("ELPIS_CANONICAL_MANIFEST.json"),
        Path("manifests/PUBLIC_COMPONENT_REGISTRY.json"),
        Path("manifests/PUBLIC_DEPENDENCY_GRAPH.json"),
        Path("manifests/GRID81_WRITER_CHAIN_SUCCESSOR_REGISTRY_R0.json"),
        Path(
            "manifests/"
            "GRID81_WRITER_CHAIN_SUCCESSOR_DEPENDENCY_GRAPH_R0.json"
        ),
    ]

    registry = json.loads(
        (
            ROOT
            / "manifests/GRID81_WRITER_CHAIN_SUCCESSOR_REGISTRY_R0.json"
        ).read_text(encoding="utf-8")
    )
    for entry in registry["components"]:
        manifest_path = Path(entry["manifest_path"])
        files.append(manifest_path)
        manifest = json.loads(
            (ROOT / manifest_path).read_text(encoding="utf-8")
        )
        component = Path(manifest["component_path"])
        for item in manifest["source_inventory"]:
            files.append(component / item["path"])

    for rel in sorted(set(files)):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)

    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    return root


def _rewrite_json(path: Path, mutate) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def test_successor_assembly_verifier_accepts_current_authority():
    assert module.verify(ROOT) == []


def test_graph_tamper_fails_self_hash(tmp_path):
    root = _copy_authority_tree(tmp_path)
    path = (
        root
        / "manifests/"
        "GRID81_WRITER_CHAIN_SUCCESSOR_DEPENDENCY_GRAPH_R0.json"
    )
    _rewrite_json(
        path,
        lambda value: value["writer_flow_edges"].reverse(),
    )

    errors = module.verify(root)
    assert "GRAPH_SELF_HASH" in errors
    assert "FLOW_EDGES" in errors


def test_manifest_source_tamper_fails_inventory(tmp_path):
    root = _copy_authority_tree(tmp_path)
    source = (
        root
        / "components/"
        "Grid81DeterministicCanonicalPublisher/"
        "src/elpis_grid81_canonical_publisher/publisher.py"
    )
    source.write_text(
        source.read_text(encoding="utf-8") + "\n# tamper\n",
        encoding="utf-8",
    )

    errors = module.verify(root)
    assert (
        "SOURCE_INVENTORY:Grid81_Atomic_Canonical_Publisher"
        in errors
    )
    assert (
        "SOURCE_INVENTORY_DIGEST:Grid81_Atomic_Canonical_Publisher"
        in errors
    )


def test_legacy_public_metadata_tamper_fails_byte_binding(tmp_path):
    root = _copy_authority_tree(tmp_path)
    path = root / "manifests/PUBLIC_COMPONENT_REGISTRY.json"
    _rewrite_json(
        path,
        lambda value: value.__setitem__("runtime_admission", True),
    )

    errors = module.verify(root)
    assert (
        "LEGACY_BINDING_HASH:manifests/PUBLIC_COMPONENT_REGISTRY.json"
        in errors
    )


def test_successor_component_cannot_leak_into_legacy_public(tmp_path):
    root = _copy_authority_tree(tmp_path)
    path = root / "manifests/PUBLIC_COMPONENT_REGISTRY.json"

    def mutate(value):
        value["components"].append({
            "component_id": "Grid81_Atomic_Canonical_Publisher",
            "version": "R0",
            "public_path": "components/Grid81DeterministicCanonicalPublisher",
            "runtime_admission": False,
            "active_status": "ACTIVE",
            "dependencies": [],
        })
        value["component_count"] = 17

    _rewrite_json(path, mutate)

    errors = module.verify(root)
    assert "LEGACY_PUBLIC_COUNT" in errors
    assert "SUCCESSOR_LEAKED_INTO_LEGACY_PUBLIC" in errors
