from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_PACKAGES = {
    "elpis_p0", "elpis_fractal_spine", "elpis_grid81_semantics",
    "elpis_grid81_typed", "elpis_grid81_groups", "elpis_grid81_adjudication",
    "elpis_grid81_capability_authority", "elpis_grid81_consumption_compiler",
    "elpis_grid81_application_executor", "elpis_grid81_promotion_planner",
    "c_numpy_cortex", "elpis_header", "elpis_runtime_r0", "elpis_runtime_r1",
}

def test_public_registry_truthfully_excludes_nonshipped_nanbeige_host():
    canonical = json.loads((ROOT / "ELPIS_CANONICAL_MANIFEST.json").read_text())
    public = json.loads((ROOT / "manifests/PUBLIC_COMPONENT_REGISTRY.json").read_text())
    canonical_ids = {c["component_id"] for c in canonical["components"]}
    public_ids = {c["component_id"] for c in public["components"]}
    assert canonical_ids - public_ids == {"elpis_nanbeige42_host"}
    assert public["component_count"] == 16
    assert not (ROOT / "native/elpis-nanbeige42-host").exists()
    assert not (ROOT / "components/elpis_nanbeige42_host").exists()

def test_canonical_assembly_verifier_is_green():
    cp = subprocess.run([sys.executable, str(ROOT / "tools/verify_canonical_assembly.py")],
                        cwd=ROOT, text=True, capture_output=True)
    assert cp.returncode == 0, cp.stdout + cp.stderr

def test_package_discovery_declares_all_nested_source_roots():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    find = config["tool"]["setuptools"]["packages"]["find"]
    includes = set(find["include"])
    assert {name + "*" for name in EXPECTED_PACKAGES} <= includes
    assert "runtime/R0/src" in find["where"]
    assert "runtime/R1/src" in find["where"]
    assert "components/Pipeline/P0ControlProtocol/src" in find["where"]
    assert "native/elpis-header/src" in find["where"]

def test_ci_has_complete_top_level_suite_and_read_only_assembly_gate():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "python -m pytest -q -p no:cacheprovider tests/" in workflow
    assert "python tools/verify_canonical_assembly.py" in workflow
    assert "python tools/print_component_map.py" in workflow
    assert "python tools/qualify_allocator_budget.py" in workflow
