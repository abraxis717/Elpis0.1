"""Executable sealer guards: refusal must precede all manifest writes."""
import ast
import json
import runpy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def copy_root():
    with tempfile.TemporaryDirectory(prefix="elpis_mut_") as td:
        root = Path(td) / "repo"
        shutil.copytree(REPO, root, symlinks=True, ignore=shutil.ignore_patterns(
            ".git", "build", "dist", "__pycache__", ".pytest_cache", "*.egg-info"))
        yield root


def seal(root, *args):
    return subprocess.run([sys.executable, str(root / "tools/seal_release.py"), *args],
                          cwd=root, capture_output=True, text=True)


@pytest.mark.parametrize("version", ["2.0.0", "2.1.0", "2.1.1", "2.1.2"])
def test_published_manifest_is_immutable(copy_root, version):
    path = copy_root / f"manifests/Elpis{version}.RELEASE_MANIFEST.json"
    before = path.read_bytes()
    proc = seal(copy_root, "--version", version)
    assert proc.returncode == 2 and "immutable" in proc.stderr
    assert path.read_bytes() == before


def test_override_requires_provisional(copy_root):
    proc = seal(copy_root, "--i-am-rewriting-history")
    assert proc.returncode == 2 and "throwaway" in proc.stderr


def set_identity(root, value):
    path = root / "tools/verify_public_release.py"
    tree = ast.parse(path.read_text())
    version = (root / "VERSION").read_text().strip()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "RELEASE_IDENTITIES" for t in node.targets):
            identities = ast.literal_eval(node.value)
            if value is None:
                identities.pop(version, None)
            else:
                identities[version] = dict.fromkeys(("primitive_closure_commit", "base_release_commit"), value)
            node.value = ast.parse(repr(identities), mode="eval").body
    path.write_text(ast.unparse(tree))


@pytest.mark.parametrize("value,marker", [(None, "UNKNOWN_RELEASE_IDENTITY"), ("UNSEALED", "UNSEALED_RELEASE_IDENTITY")])
def test_identity_must_be_ratified(copy_root, value, marker):
    set_identity(copy_root, value)
    version = (copy_root / "VERSION").read_text().strip()
    manifest = copy_root / f"manifests/Elpis{version}.RELEASE_MANIFEST.json"
    before = manifest.read_bytes() if manifest.exists() else None
    proc = seal(copy_root, "--provisional", "--i-am-rewriting-history")
    assert proc.returncode == 2 and marker in proc.stderr
    assert (manifest.read_bytes() if manifest.exists() else None) == before
    checked = subprocess.run([sys.executable, str(copy_root / "tools/verify_public_release.py")],
                             cwd=copy_root, capture_output=True, text=True)
    assert checked.returncode == 1 and marker in checked.stdout


def test_sealer_rejects_empty_ephemeral_directory(copy_root):
    (copy_root / "build").mkdir()
    proc = seal(copy_root, "--provisional", "--i-am-rewriting-history")
    assert proc.returncode == 3 and "EPHEMERAL ARTIFACT PRESENT" in proc.stderr


def test_sealer_rejects_symlink_escape(copy_root):
    (copy_root / "escaped").symlink_to(copy_root.parent / "outside")
    proc = seal(copy_root, "--provisional", "--i-am-rewriting-history")
    assert proc.returncode == 3 and "SYMLINK ESCAPE" in proc.stderr


def test_allowlist_emission_is_fixed_point(copy_root):
    verifier = runpy.run_path(str(copy_root / "tools/verify_public_release.py"))
    emitted = verifier["emitted_allowlist"]()
    path = copy_root / "tools/public_scan_allowlist.json"
    assert emitted == json.loads(path.read_text())
    path.write_text(json.dumps(emitted, indent=2) + "\n")
    assert emitted == verifier["emitted_allowlist"]()
