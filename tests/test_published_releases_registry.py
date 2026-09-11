from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "PUBLISHED_RELEASES.json"
TAG_RE = re.compile(r"^Elpis(\d+)\.(\d+)\.(\d+)$")


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
    ).strip()


def _semantic_tags() -> list[str]:
    return sorted(
        (
            tag
            for tag in _git("tag", "--list", "Elpis*").splitlines()
            if TAG_RE.fullmatch(tag)
        ),
        key=lambda tag: tuple(
            int(x) for x in TAG_RE.fullmatch(tag).groups()
        ),
    )


def test_published_release_registry_matches_tag_authority():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert data["schema"] == "elpis.published-releases.v1"
    assert data["source_of_truth"] == "refs/tags/Elpis<semver>"

    entries = data["published_releases"]
    assert isinstance(entries, list)

    versions = [entry["version"] for entry in entries]
    tags = [entry["release_tag"] for entry in entries]

    assert len(versions) == len(set(versions))
    assert len(tags) == len(set(tags))
    assert tags == _semantic_tags()

    for entry in entries:
        tag = entry["release_tag"]
        match = TAG_RE.fullmatch(tag)
        assert match is not None

        version = ".".join(match.groups())
        assert entry["version"] == version

        assert entry["peeled_commit"] == _git(
            "rev-parse", f"{tag}^{{}}"
        )

        expected_manifest = (
            Path("manifests") / f"{tag}.RELEASE_MANIFEST.json"
        )
        assert entry["manifest_path"] == expected_manifest.as_posix()

        manifest = ROOT / expected_manifest
        assert manifest.is_file()

        assert entry["manifest_sha256"] == hashlib.sha256(
            manifest.read_bytes()
        ).hexdigest()


def test_failed_sealed_candidates_are_not_published():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    tags = {
        entry["release_tag"]
        for entry in data["published_releases"]
    }

    for tag in ("Elpis2.1.13", "Elpis2.1.14"):
        assert (ROOT / "manifests" / f"{tag}.RELEASE_MANIFEST.json").is_file()
        assert tag not in tags


def test_current_release_is_published():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    tags = {
        entry["release_tag"]
        for entry in data["published_releases"]
    }

    assert "Elpis2.1.16" in tags
