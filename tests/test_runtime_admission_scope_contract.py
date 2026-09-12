from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _literal_assignment(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path}")


def test_whole_runtime_admission_is_distinct_from_component_registry_admission():
    full_runtime = _literal_assignment(
        ROOT / "src/elpis_reference/structural_guidance/authority.py",
        "FULL_ELPIS_RUNTIME_ADMISSION",
    )
    registry = json.loads(
        (ROOT / "manifests/PUBLIC_COMPONENT_REGISTRY.json").read_text(
            encoding="utf-8"
        )
    )

    assert full_runtime is True
    assert registry["runtime_admission"] is False
    assert registry["components"]
    assert all(
        component["runtime_admission"] is False
        for component in registry["components"]
    )
