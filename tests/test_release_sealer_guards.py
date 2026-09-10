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


def _copy_ignore(src, names):
    """Ignore generated content while preserving nested vendored `models/`.

    `shutil.ignore_patterns("models")` is recursively applied and therefore
    incorrectly removes src/elpis_reference/vendor/fprm/models/. Only the
    repository-root qualification checkpoint directory is excluded.
    """
    ignored = set(
        shutil.ignore_patterns(
            ".git",
            "build",
            "dist",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "*.egg-info",
        )(src, names)
    )

    if Path(src).resolve() == REPO.resolve() and "models" in names:
        ignored.add("models")

    return ignored


@pytest.fixture
def copy_root():
    with tempfile.TemporaryDirectory(prefix="elpis_mut_") as td:
        root = Path(td) / "repo"
        shutil.copytree(
            REPO,
            root,
            symlinks=True,
            ignore=_copy_ignore,
        )
        yield root


def seal(root, *args):
    return subprocess.run([sys.executable, str(root / "tools/seal_release.py"), *args],
                          cwd=root, capture_output=True, text=True)


@pytest.mark.parametrize(
    "version",
    ["2.0.0", "2.1.0", "2.1.1", "2.1.2", "2.1.3", "2.1.4", "2.1.5", "2.1.6", "2.1.7", "2.1.8", "2.1.9", "2.1.10", "2.1.11", "2.1.12", "2.1.13", "2.1.14", "2.1.15"],
)
def test_existing_published_manifest_is_write_once(copy_root, version):
    path = copy_root / f"manifests/Elpis{version}.RELEASE_MANIFEST.json"
    before = path.read_bytes()

    proc = seal(copy_root, "--version", version)

    marker = (
        f"manifests/Elpis{version}.RELEASE_MANIFEST.json "
        "already exists; release manifests are write-once"
    )
    assert proc.returncode == 2
    assert marker in proc.stderr
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

    # During successor pre-seal qualification the current manifest does not
    # exist yet. Materialize only a minimal throwaway fixture so the verifier
    # reaches the deliberately corrupted identity branch instead of stopping
    # first at "missing manifest". This is not a seal or a production write.
    if not manifest.exists():
        manifest.write_text("{}\n", encoding="utf-8")

    checked = subprocess.run(
        [sys.executable, str(copy_root / "tools/verify_public_release.py")],
        cwd=copy_root,
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 1
    assert marker in checked.stdout


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
