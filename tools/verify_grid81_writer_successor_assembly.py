#!/usr/bin/env python3
"""Verify the post-2.1.16 Grid81 writer successor assembly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REGISTRY_REL = Path(
    "manifests/GRID81_WRITER_CHAIN_SUCCESSOR_REGISTRY_R0.json"
)
GRAPH_REL = Path(
    "manifests/GRID81_WRITER_CHAIN_SUCCESSOR_DEPENDENCY_GRAPH_R0.json"
)

EXPECTED_SUCCESSOR_IDS = {
    "Grid81_Canonical_Promotion_Authority",
    "Grid81_Canonical_Candidate_Constructor",
    "Grid81_Atomic_Canonical_Publisher",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path, errors: list[str]) -> dict | None:
    if not path.is_file():
        errors.append(f"MISSING:{path}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"INVALID_JSON:{path}:{exc}")
        return None
    if type(value) is not dict:
        errors.append(f"ROOT_NOT_OBJECT:{path}")
        return None
    return value


def _self_hash(value: dict, field: str) -> str:
    return _sha_bytes(
        _canonical_bytes(
            {
                key: item
                for key, item in value.items()
                if key != field
            }
        )
    )


def _tracked_inventory(root: Path, component_rel: Path) -> list[dict]:
    names = subprocess.check_output(
        ["git", "ls-files", component_rel.as_posix()],
        cwd=root,
        text=True,
    ).splitlines()
    names = sorted(
        name for name in names
        if Path(name).name != "COMPONENT_MANIFEST.json"
    )
    return [
        {
            "path": Path(name).relative_to(component_rel).as_posix(),
            "sha256": _sha_file(root / name),
            "size": (root / name).stat().st_size,
        }
        for name in names
    ]


def _has_successor_cycle(nodes: set[str], edges: list[dict]) -> bool:
    successors: dict[str, set[str]] = {node: set() for node in nodes}
    for edge in edges:
        source = edge["from"]
        target = edge["to"]
        if source in nodes and target in nodes:
            successors[source].add(target)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for target in successors[node]:
            if visit(target):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in sorted(nodes))


def verify(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []

    registry = _load(root / REGISTRY_REL, errors)
    graph = _load(root / GRAPH_REL, errors)
    legacy_canonical = _load(root / "ELPIS_CANONICAL_MANIFEST.json", errors)
    legacy_public = _load(
        root / "manifests/PUBLIC_COMPONENT_REGISTRY.json", errors
    )
    legacy_graph = _load(
        root / "manifests/PUBLIC_DEPENDENCY_GRAPH.json", errors
    )
    if any(
        value is None
        for value in (
            registry,
            graph,
            legacy_canonical,
            legacy_public,
            legacy_graph,
        )
    ):
        return errors

    assert registry is not None
    assert graph is not None
    assert legacy_canonical is not None
    assert legacy_public is not None
    assert legacy_graph is not None

    if registry.get("schema") != (
        "elpis.grid81.writer-chain.successor-registry.v1"
    ):
        errors.append("REGISTRY_SCHEMA")
    if registry.get("registry_self_hash") != _self_hash(
        registry, "registry_self_hash"
    ):
        errors.append("REGISTRY_SELF_HASH")

    if graph.get("schema") != (
        "elpis.grid81.writer-chain.successor-dependency-graph.v1"
    ):
        errors.append("GRAPH_SCHEMA")
    if graph.get("graph_self_hash") != _self_hash(
        graph, "graph_self_hash"
    ):
        errors.append("GRAPH_SELF_HASH")
    if graph.get("registry_self_hash") != registry.get(
        "registry_self_hash"
    ):
        errors.append("GRAPH_REGISTRY_BINDING")

    entries = registry.get("components")
    if type(entries) is not list:
        errors.append("REGISTRY_COMPONENTS")
        return errors

    registry_ids = {
        item.get("component_id")
        for item in entries
        if type(item) is dict
    }
    if registry_ids != EXPECTED_SUCCESSOR_IDS:
        errors.append("SUCCESSOR_ID_SET")
    if registry.get("component_count") != len(EXPECTED_SUCCESSOR_IDS):
        errors.append("SUCCESSOR_COMPONENT_COUNT")
    if registry.get("runtime_admission") is not False:
        errors.append("REGISTRY_RUNTIME_ADMISSION")
    if registry.get("public_registry_admission") is not False:
        errors.append("REGISTRY_PUBLIC_ADMISSION")
    if registry.get("legacy_assembly_metadata_unchanged") is not True:
        errors.append("LEGACY_UNCHANGED_DECLARATION")

    by_id = {
        item["component_id"]: item
        for item in entries
        if type(item) is dict and item.get("component_id")
    }

    manifest_dependencies: dict[str, list[str]] = {}
    for component_id in sorted(EXPECTED_SUCCESSOR_IDS):
        entry = by_id.get(component_id)
        if entry is None:
            continue

        manifest_rel = Path(entry.get("manifest_path", ""))
        if manifest_rel.is_absolute() or ".." in manifest_rel.parts:
            errors.append(f"UNSAFE_MANIFEST_PATH:{component_id}")
            continue

        manifest = _load(root / manifest_rel, errors)
        if manifest is None:
            continue

        if manifest.get("component_id") != component_id:
            errors.append(f"MANIFEST_COMPONENT_ID:{component_id}")
        if manifest.get("manifest_self_hash") != _self_hash(
            manifest, "manifest_self_hash"
        ):
            errors.append(f"MANIFEST_SELF_HASH:{component_id}")
        if entry.get("manifest_self_hash") != manifest.get(
            "manifest_self_hash"
        ):
            errors.append(f"REGISTRY_MANIFEST_BINDING:{component_id}")
        if entry.get("source_inventory_digest") != manifest.get(
            "source_inventory_digest"
        ):
            errors.append(f"REGISTRY_INVENTORY_BINDING:{component_id}")
        if manifest.get("runtime_admission") is not False:
            errors.append(f"MANIFEST_RUNTIME_ADMISSION:{component_id}")
        if manifest.get("public_registry_admission") is not False:
            errors.append(f"MANIFEST_PUBLIC_ADMISSION:{component_id}")

        component_rel = Path(manifest.get("component_path", ""))
        if component_rel.is_absolute() or ".." in component_rel.parts:
            errors.append(f"UNSAFE_COMPONENT_PATH:{component_id}")
            continue

        try:
            inventory = _tracked_inventory(root, component_rel)
        except Exception as exc:
            errors.append(
                f"INVENTORY_READ:{component_id}:{type(exc).__name__}"
            )
            continue

        if manifest.get("source_inventory") != inventory:
            errors.append(f"SOURCE_INVENTORY:{component_id}")

        expected_inventory_digest = _sha_bytes(
            b"elpis.writer-component.inventory.v1\0"
            + _canonical_bytes(inventory)
        )
        if manifest.get("source_inventory_digest") != (
            expected_inventory_digest
        ):
            errors.append(f"SOURCE_INVENTORY_DIGEST:{component_id}")

        deps = manifest.get("dependencies")
        if (
            type(deps) is not list
            or not all(type(dep) is str and dep for dep in deps)
            or len(deps) != len(set(deps))
        ):
            errors.append(f"MANIFEST_DEPENDENCIES:{component_id}")
            continue
        manifest_dependencies[component_id] = deps

    successor_nodes = set(graph.get("successor_nodes", []))
    if successor_nodes != EXPECTED_SUCCESSOR_IDS:
        errors.append("GRAPH_SUCCESSOR_NODES")

    public_ids = {
        item.get("component_id")
        for item in legacy_public.get("components", [])
        if type(item) is dict
    }
    canonical_ids = {
        item.get("component_id")
        for item in legacy_canonical.get("components", [])
        if type(item) is dict
    }

    if legacy_public.get("component_count") != 16:
        errors.append("LEGACY_PUBLIC_COUNT")
    if legacy_canonical.get("component_count") != 17:
        errors.append("LEGACY_CANONICAL_COUNT")
    if EXPECTED_SUCCESSOR_IDS & public_ids:
        errors.append("SUCCESSOR_LEAKED_INTO_LEGACY_PUBLIC")
    if EXPECTED_SUCCESSOR_IDS & canonical_ids:
        errors.append("SUCCESSOR_LEAKED_INTO_LEGACY_CANONICAL")

    expected_edges = sorted(
        (
            {"from": component_id, "to": dependency}
            for component_id, dependencies in manifest_dependencies.items()
            for dependency in dependencies
        ),
        key=lambda item: (item["from"], item["to"]),
    )
    graph_edges = graph.get("dependency_edges")
    if graph_edges != expected_edges:
        errors.append("GRAPH_DEPENDENCY_EDGES")

    expected_external = sorted({
        edge["to"]
        for edge in expected_edges
        if edge["to"] not in EXPECTED_SUCCESSOR_IDS
    })
    if graph.get("legacy_external_nodes") != expected_external:
        errors.append("GRAPH_EXTERNAL_NODES")
    if any(dep not in public_ids for dep in expected_external):
        errors.append("EXTERNAL_DEPENDENCY_NOT_FROZEN_PUBLIC")

    if _has_successor_cycle(EXPECTED_SUCCESSOR_IDS, expected_edges):
        errors.append("SUCCESSOR_DEPENDENCY_CYCLE")

    flow_nodes = registry.get("writer_chain_order")
    if graph.get("writer_flow_nodes") != flow_nodes:
        errors.append("FLOW_NODE_BINDING")
    if type(flow_nodes) is not list or len(flow_nodes) < 2:
        errors.append("FLOW_NODES")
    else:
        expected_flow_edges = [
            {"from": flow_nodes[i], "to": flow_nodes[i + 1]}
            for i in range(len(flow_nodes) - 1)
        ]
        if graph.get("writer_flow_edges") != expected_flow_edges:
            errors.append("FLOW_EDGES")
        if flow_nodes != [
            "G53e_Canonical_Promotion_Planner",
            "Grid81_Canonical_Promotion_Authority",
            "Grid81_Canonical_Candidate_Constructor",
            "Grid81_Atomic_Canonical_Publisher",
            "Grid81_Canonical_Substrate",
        ]:
            errors.append("FLOW_ORDER")

    bindings = graph.get("legacy_assembly_bindings")
    if type(bindings) is not list:
        errors.append("LEGACY_BINDINGS")
    else:
        expected_paths = {
            "ELPIS_CANONICAL_MANIFEST.json",
            "manifests/PUBLIC_COMPONENT_REGISTRY.json",
            "manifests/PUBLIC_DEPENDENCY_GRAPH.json",
        }
        bound_paths = {
            item.get("path")
            for item in bindings
            if type(item) is dict
        }
        if bound_paths != expected_paths:
            errors.append("LEGACY_BINDING_PATH_SET")
        for item in bindings:
            if type(item) is not dict:
                errors.append("LEGACY_BINDING_RECORD")
                continue
            path = root / item.get("path", "")
            if not path.is_file():
                errors.append(f"LEGACY_BINDING_MISSING:{item.get('path')}")
                continue
            if item.get("sha256") != _sha_file(path):
                errors.append(f"LEGACY_BINDING_HASH:{item.get('path')}")
            if item.get("size") != path.stat().st_size:
                errors.append(f"LEGACY_BINDING_SIZE:{item.get('path')}")

    legacy_nodes = set(legacy_graph.get("nodes", []))
    if legacy_nodes != public_ids:
        errors.append("LEGACY_GRAPH_NODE_SET")

    if graph.get("runtime_admission") is not False:
        errors.append("GRAPH_RUNTIME_ADMISSION")
    if graph.get("public_registry_admission") is not False:
        errors.append("GRAPH_PUBLIC_ADMISSION")

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = verify(root)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"FAIL: {len(errors)} successor assembly error(s)")
        return 1

    print(
        "PASS: Grid81 successor writer assembly verified; "
        "legacy 17/16 assembly remains byte-bound and unchanged"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
