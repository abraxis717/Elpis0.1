#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "PUBLISHED_RELEASES.json"
FAILED_RELEASES = ROOT / "FAILED_RELEASES.json"
TAG_RE = re.compile(r"^Elpis(\d+)\.(\d+)\.(\d+)$")


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args],
        text=True,
    ).strip()


def semantic_tags() -> list[str]:
    return sorted(
        (
            tag
            for tag in git("tag", "--list", "Elpis*").splitlines()
            if TAG_RE.fullmatch(tag)
        ),
        key=lambda tag: tuple(
            int(x) for x in TAG_RE.fullmatch(tag).groups()
        ),
    )


def failed_tags() -> set[str]:
    payload = json.loads(FAILED_RELEASES.read_text(encoding="utf-8"))
    if payload.get("schema") != "elpis.failed-releases.v1":
        raise SystemExit("invalid FAILED_RELEASES.json schema")
    tags = set()
    for item in payload.get("failed_releases", []):
        tag = item.get("release_tag")
        if not isinstance(tag, str) or not TAG_RE.fullmatch(tag):
            raise SystemExit("invalid failed release tag")
        if tag in tags:
            raise SystemExit(f"duplicate failed release tag: {tag}")
        tags.add(tag)
    return tags


def publishable_tags() -> list[str]:
    failed = failed_tags()
    return [tag for tag in semantic_tags() if tag not in failed]


def materialize() -> dict:
    entries = []
    for tag in publishable_tags():
        version = tag.removeprefix("Elpis")
        manifest_rel = Path("manifests") / f"{tag}.RELEASE_MANIFEST.json"
        manifest = ROOT / manifest_rel
        if not manifest.is_file():
            raise SystemExit(f"missing manifest for publishable tag: {tag}")
        entries.append({
            "manifest_path": manifest_rel.as_posix(),
            "manifest_sha256": hashlib.sha256(
                manifest.read_bytes()
            ).hexdigest(),
            "peeled_commit": git("rev-parse", f"{tag}^{{}}"),
            "release_tag": tag,
            "version": version,
        })
    return {
        "published_releases": entries,
        "schema": "elpis.published-releases.v1",
        "source_of_truth": "refs/tags/Elpis<semver>",
    }


def encoded() -> str:
    return json.dumps(materialize(), indent=2) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    expected = encoded()
    if args.check:
        if REGISTRY.read_text(encoding="utf-8") != expected:
            raise SystemExit(
                "PUBLISHED_RELEASES.json is not the exact "
                "publishable-tag-derived projection"
            )
        print("PASS published-release registry matches publishable tag authority")
        return 0
    REGISTRY.write_text(expected, encoding="utf-8")
    print(
        "updated PUBLISHED_RELEASES.json from "
        f"{len(publishable_tags())} publishable semantic tags"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
