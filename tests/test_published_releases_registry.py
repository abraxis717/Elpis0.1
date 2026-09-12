from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "PUBLISHED_RELEASES.json"
FAILED_RELEASES = ROOT / "FAILED_RELEASES.json"
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


def _failed_payload() -> dict:
    return json.loads(FAILED_RELEASES.read_text(encoding="utf-8"))


def _failed_tags() -> set[str]:
    payload = _failed_payload()
    assert payload["schema"] == "elpis.failed-releases.v1"
    tags = [item["release_tag"] for item in payload["failed_releases"]]
    assert len(tags) == len(set(tags))
    assert all(TAG_RE.fullmatch(tag) for tag in tags)
    return set(tags)


def _publishable_tags() -> list[str]:
    failed = _failed_tags()
    return [tag for tag in _semantic_tags() if tag not in failed]


def _pending_event_tag() -> str | None:
    if os.environ.get("GITHUB_REF_TYPE") != "tag":
        return None
    tag = os.environ.get("GITHUB_REF_NAME", "")
    return tag if TAG_RE.fullmatch(tag) else None


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

    publishable = _publishable_tags()
    pending = _pending_event_tag()
    if pending is None:
        assert tags == publishable
    else:
        assert pending in _semantic_tags()
        assert pending not in _failed_tags()
        assert pending not in tags
        assert tags == [tag for tag in publishable if tag != pending]

        manifest = ROOT / "manifests" / f"{pending}.RELEASE_MANIFEST.json"
        assert manifest.is_file()
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        assert payload["release_tag"] == pending
        assert payload["version"] == pending.removeprefix("Elpis")

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
    for tag in ("Elpis2.1.13", "Elpis2.1.14", "Elpis2.1.24"):
        assert (
            ROOT / "manifests" / f"{tag}.RELEASE_MANIFEST.json"
        ).is_file()
        assert tag not in tags


def test_failed_release_2_1_24_is_bound_to_immutable_authority():
    payload = _failed_payload()
    entries = {
        item["release_tag"]: item
        for item in payload["failed_releases"]
    }
    item = entries["Elpis2.1.24"]
    assert item["version"] == "2.1.24"
    assert item["disposition"] == "SEALED_TAGGED_CI_FAILED_NOT_PUBLISHED"
    assert item["tag_object"] == (
        "3c422b52f28048f19ce998b2deab25720dcf6f8a"
    )
    assert item["peeled_commit"] == (
        "111ea53d0dded111b53aa5b62c55ea6c9d57ab34"
    )
    assert _git("rev-parse", "Elpis2.1.24^{tag}") == item["tag_object"]
    assert _git("rev-parse", "Elpis2.1.24^{}") == item["peeled_commit"]
    manifest = ROOT / item["manifest_path"]
    assert manifest.is_file()
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == (
        item["manifest_sha256"]
    )


def test_current_release_is_published():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    tags = {
        entry["release_tag"]
        for entry in data["published_releases"]
    }
    assert "Elpis2.1.16" in tags
