from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
SEALER = Path("tools/seal_release.py")
VERIFIER = Path("tools/verify_public_release.py")

BASE_IGNORE = shutil.ignore_patterns(
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "build",
    "dist",
    "*.egg-info",
)


def copy_ignore(src, names):
    """Exclude only the top-level qualification model directory."""
    ignored = set(BASE_IGNORE(src, names))

    if Path(src).resolve() == REPO.resolve() and "models" in names:
        ignored.add("models")

    return ignored


def copy_repo(tmp_path: Path) -> Path:
    """Materialize the sealed control from exact staged-index bytes.

    During precommit successor qualification, the Git index is the candidate
    authority: it contains the exact staged source/metadata and the newly
    sealed write-once manifest while excluding arbitrary unstaged worktree
    bytes. On a committed clean tree the index and HEAD are identical.
    """
    root = tmp_path / "repo"
    root.mkdir()

    subprocess.run(
        [
            "git", "-C", str(REPO), "checkout-index", "--all",
            f"--prefix={root}{os.sep}",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return root


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=root,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def output(proc: subprocess.CompletedProcess[str]) -> str:
    return proc.stdout + proc.stderr


def test_existing_manifest_is_write_once(tmp_path: Path) -> None:
    root = copy_repo(tmp_path)
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    manifest = root / f"manifests/Elpis{version}.RELEASE_MANIFEST.json"
    if not manifest.exists():
        manifest.write_text("{}\n", encoding="utf-8")

    proc = run(root, str(SEALER), "--version", version)

    assert proc.returncode == 2
    assert "already exists; release manifests are write-once" in output(proc)


def test_published_belt_is_independent_of_manifest_existence(tmp_path: Path) -> None:
    root = copy_repo(tmp_path)
    (root / "VERSION").write_text("2.1.15\n", encoding="utf-8")
    manifest = root / "manifests/Elpis2.1.15.RELEASE_MANIFEST.json"
    manifest.unlink(missing_ok=True)

    proc = run(root, str(SEALER), "--version", "2.1.15")

    assert proc.returncode == 2
    assert "Elpis2.1.15 is published; its manifest is immutable" in output(proc)

def test_sealer_refuses_ephemeral_artifact(tmp_path: Path) -> None:
    root = copy_repo(tmp_path)
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    manifest = root / f"manifests/Elpis{version}.RELEASE_MANIFEST.json"
    manifest.unlink(missing_ok=True)
    (root / ".pytest_cache").mkdir()

    proc = run(root, str(SEALER), "--version", version)

    assert proc.returncode == 3
    assert "EPHEMERAL ARTIFACT PRESENT" in output(proc)


def test_real_sealed_tree_verifies_without_reseal(tmp_path: Path) -> None:
    version = (REPO / "VERSION").read_text(encoding="utf-8").strip()
    manifest = REPO / f"manifests/Elpis{version}.RELEASE_MANIFEST.json"

    if not manifest.exists():
        if os.environ.get("ELPIS_REQUIRE_SEALED_CONTROL") == "1":
            pytest.fail(f"required sealed manifest absent: {manifest.name}")
        pytest.skip("pre-seal qualification: real-manifest control runs after sealing")

    root = copy_repo(tmp_path)
    proc = run(root, str(VERIFIER))

    assert proc.returncode == 0, output(proc)
