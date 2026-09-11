from __future__ import annotations

from pathlib import Path
import runpy
import subprocess


REPO = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")

    (repo / "tracked.txt").write_text("tracked\\n", encoding="utf-8")
    (repo / "PUBLISHED_RELEASES.json").write_text("{}\\n", encoding="utf-8")
    local = repo / ".astra_tmp" / "codex-bwrap-synthetic-mount-targets-1000"
    local.mkdir(parents=True)
    (local / "lock").write_text("clone-local\\n", encoding="utf-8")

    _git(repo, "add", "tracked.txt", "PUBLISHED_RELEASES.json")
    return repo


def test_sealer_manifest_membership_uses_git_tracked_tree(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    ns = runpy.run_path(str(REPO / "tools" / "seal_release.py"))
    tree_files = ns["tree_files"]
    tree_files.__globals__["REPO"] = repo

    files = tree_files(Path("manifests/Elpis9.9.9.RELEASE_MANIFEST.json"))

    assert files == ["tracked.txt"]


def test_verifier_manifest_membership_uses_git_tracked_tree(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    ns = runpy.run_path(str(REPO / "tools" / "verify_public_release.py"))
    actual_files = ns["actual_files"]
    actual_files.__globals__["REPO"] = repo
    actual_files.__globals__["MANIFEST_REL"] = Path(
        "manifests/Elpis9.9.9.RELEASE_MANIFEST.json"
    )

    files = actual_files()

    assert files == {"tracked.txt"}
