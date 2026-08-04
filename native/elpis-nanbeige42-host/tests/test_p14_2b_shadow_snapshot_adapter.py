from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO = Path("/mnt/primesauce/Elpis_Canon")
SOURCE = REPO / "hosts/nanbeige42/experiments/host_v0_1/p14_2b_open_canary_live_execution_v2.py"


def load_module():
    spec = importlib.util.spec_from_file_location("p14_2b_live_v2", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_tree(tmp_path: Path):
    module = load_module()
    repo = tmp_path / "repo"
    task_id = "canary"
    source = repo / module.TASK_REL / "workspaces" / task_id
    acceptance = repo / module.TASK_REL / "acceptance" / task_id
    source.mkdir(parents=True)
    acceptance.mkdir(parents=True)
    (source / "TASK.md").write_text("task\n", encoding="utf-8")
    (source / "solution.py").write_text("def f():\n    return 0\n", encoding="utf-8")
    (acceptance / "test_acceptance.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    entry = SimpleNamespace(
        task_id=task_id,
        workspace_root=str(source),
        workspace_snapshot_digest="sha256:registry-with-pyc",
        entry_digest="sha256:entry",
        packet_binding_digest="sha256:packet",
    )
    access = {
        "task_id": task_id,
        "workspace_snapshot_digest": entry.workspace_snapshot_digest,
        "entry_digest": entry.entry_digest,
        "packet_binding_digest": entry.packet_binding_digest,
        "task_md_sha256": sha(source / "TASK.md"),
        "solution_sha256": sha(source / "solution.py"),
        "acceptance_test_sha256": sha(acceptance / "test_acceptance.py"),
    }
    return module, repo, entry, access


def test_shadow_accepts_source_hashes_while_preserving_registry_snapshot(tmp_path):
    module, repo, entry, access = fixture_tree(tmp_path)
    shadow, workspace, validation = module.prepare_shadow(
        repo, tmp_path / "runtime", "run", entry, access
    )
    assert validation["registry_workspace_snapshot_digest"] == "sha256:registry-with-pyc"
    assert validation["interpreter_cache_copied"] is False
    assert sorted(p.name for p in workspace.iterdir()) == ["TASK.md", "solution.py"]
    assert (shadow / "acceptance" / entry.task_id / "test_acceptance.py").is_file()


def test_shadow_rejects_task_hash_drift(tmp_path):
    module, repo, entry, access = fixture_tree(tmp_path)
    Path(entry.workspace_root, "TASK.md").write_text("changed\n", encoding="utf-8")
    with pytest.raises(module.LiveError, match="canonical source hash drift: TASK.md"):
        module.prepare_shadow(repo, tmp_path / "runtime", "run", entry, access)


def test_shadow_rejects_solution_hash_drift(tmp_path):
    module, repo, entry, access = fixture_tree(tmp_path)
    Path(entry.workspace_root, "solution.py").write_text("changed\n", encoding="utf-8")
    with pytest.raises(module.LiveError, match="canonical source hash drift: solution.py"):
        module.prepare_shadow(repo, tmp_path / "runtime", "run", entry, access)


def test_shadow_rejects_acceptance_hash_drift(tmp_path):
    module, repo, entry, access = fixture_tree(tmp_path)
    test_file = repo / module.TASK_REL / "acceptance" / entry.task_id / "test_acceptance.py"
    test_file.write_text("changed\n", encoding="utf-8")
    with pytest.raises(module.LiveError, match="canonical acceptance hash drift"):
        module.prepare_shadow(repo, tmp_path / "runtime", "run", entry, access)


def test_shadow_rejects_registry_access_binding_drift(tmp_path):
    module, repo, entry, access = fixture_tree(tmp_path)
    access["workspace_snapshot_digest"] = "sha256:other"
    with pytest.raises(module.LiveError, match="registry snapshot/access binding drift"):
        module.prepare_shadow(repo, tmp_path / "runtime", "run", entry, access)


def test_shadow_does_not_copy_canonical_pycache(tmp_path):
    module, repo, entry, access = fixture_tree(tmp_path)
    cache = Path(entry.workspace_root) / "__pycache__"
    cache.mkdir()
    (cache / "solution.cpython-311.pyc").write_bytes(b"interpreter-cache")
    shadow, workspace, validation = module.prepare_shadow(
        repo, tmp_path / "runtime", "run", entry, access
    )
    assert not (workspace / "__pycache__").exists()
    assert not any("__pycache__" in path.parts for path in shadow.rglob("*"))
    assert validation["workspace_files"] == ["TASK.md", "solution.py"]
