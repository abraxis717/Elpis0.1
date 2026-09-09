#!/usr/bin/env python3
"""Seal a release manifest. Published manifests are never rewritten.

WHY THIS IS A SEPARATE TOOL
  Resealing was previously done by ad-hoc scripts during review, which is how
  a published manifest (Elpis2.1.2) came to be edited in a repair branch. A
  published release is immutable: a repair tranche becomes a SUCCESSOR
  version with its own manifest file, and the predecessor's bytes are left
  alone.

GUARDS
  - Refuses to rewrite any existing release manifest. Manifest existence is
    the primary write-once fact.
  - PUBLISHED remains a secondary historical belt and independently refuses
    known published versions when their manifest is absent in a test copy.
  - The only rewrite override is --provisional plus --i-am-rewriting-history
    inside the verified throwaway mutation-copy shape.
  - Refuses to seal when the working tree contains ephemeral artifacts, since
    those must never enter a release manifest.
  - Refuses to seal a version whose identity constants are still UNSEALED in
    the verifier's RELEASE_IDENTITIES table.

USAGE
  python tools/seal_release.py --version 2.1.3 \\
      --primitive-closure-commit <sha> --base-release-commit <sha>

  python tools/seal_release.py --provisional
      Reseal the CURRENT version's manifest in place. Intended only for
      throwaway working copies (the mutation suite uses this); it refuses to
      run on a published version without the override flag.

CLAIMS NOT MADE
  Sealing asserts that the manifest matches the tree at this instant. It
  asserts nothing about whether the tree is correct.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import runpy
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Versions that have been released. Their manifest bytes are frozen.
PUBLISHED = frozenset({"2.0.0", "2.1.0", "2.1.1", "2.1.2", "2.1.3", "2.1.4", "2.1.5", "2.1.6", "2.1.7", "2.1.8", "2.1.9"})

IGNORE_PARTS = {".git"}

EPHEMERAL_PARTS = {
    "build", "dist", "__pycache__", ".venv",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
}


def ephemeral(rel: Path) -> bool:
    if set(rel.parts) & EPHEMERAL_PARTS:
        return True
    return any(part.endswith(".egg-info") for part in rel.parts)


def tree_files(manifest_rel: Path) -> list[str]:
    out = []
    for path in REPO.rglob("*"):
        rel = path.relative_to(REPO)
        if set(rel.parts) & IGNORE_PARTS or rel == manifest_rel:
            continue
        if path.is_file() or path.is_symlink():
            out.append(rel.as_posix())
    return sorted(out)


def digest(rel: str) -> str:
    path = REPO / rel
    if path.is_symlink():
        return hashlib.sha256(str(path.readlink()).encode()).hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version")
    ap.add_argument("--primitive-closure-commit")
    ap.add_argument("--base-release-commit")
    ap.add_argument("--provisional", action="store_true")
    ap.add_argument("--i-am-rewriting-history", action="store_true")
    args = ap.parse_args(argv)

    version = args.version or (REPO / "VERSION").read_text().strip()
    manifest_rel = Path(f"manifests/Elpis{version}.RELEASE_MANIFEST.json")
    manifest = REPO / manifest_rel

    override = args.i_am_rewriting_history
    if override and not (
        args.provisional and REPO.name == "repo"
        and REPO.parent.name.startswith("elpis_mut_")
        and REPO.parent.parent.resolve() == Path(tempfile.gettempdir()).resolve()
        and not (REPO / ".git").exists()
    ):
        print("REFUSED: override requires an explicit throwaway mutation copy", file=sys.stderr)
        return 2
    if manifest.exists() and not override:
        print(
            f"REFUSED: {manifest_rel.as_posix()} already exists; "
            "release manifests are write-once",
            file=sys.stderr,
        )
        return 2
    if version in PUBLISHED and not override:
        print(f"REFUSED: Elpis{version} is published; its manifest is immutable", file=sys.stderr)
        return 2
    if version != (REPO / "VERSION").read_text().strip():
        print("REFUSED: VERSION mismatch", file=sys.stderr)
        return 2
    verifier = runpy.run_path(str(REPO / "tools/verify_public_release.py"))
    try:
        identity = verifier["release_identity"]()
    except ValueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    for key in ("primitive_closure_commit", "base_release_commit"):
        value = getattr(args, key)
        if value is not None and value != identity[key]:
            print(f"REFUSED: {key} disagrees with ratified identity", file=sys.stderr)
            return 2
    paths = verifier["release_paths"]()
    if any(ephemeral(path.relative_to(REPO)) for path in paths):
        print("REFUSED: EPHEMERAL ARTIFACT PRESENT", file=sys.stderr)
        return 3
    for path in paths:
        if path.is_symlink() and not path.resolve().is_relative_to(REPO):
            print("REFUSED: SYMLINK ESCAPE", file=sys.stderr)
            return 3

    files = tree_files(manifest_rel)

    stray = [f for f in files if ephemeral(Path(f))]
    if stray:
        print("REFUSED: ephemeral artifacts present:", file=sys.stderr)
        for s in stray[:20]:
            print(f"  {s}", file=sys.stderr)
        return 3

    if manifest.exists():
        data = json.loads(manifest.read_text())
    else:
        data = {
            "schema": "elpis.release-manifest.v2",
            "package_name": "elpis",
            "runtime_status": "VALIDATED_SOURCE",
            "full_elpis_runtime_admission": True,
            "request_guidance_gate_default": False,
            "output_authority_granted": 0,
            "validation_authority_propagated": False,
            "generated_source_executed": False,
            "execution_authorized": False,
            "experiments_shipped": False,
            "nanbeige_host_shipped": False,
        }

    data["release_name"] = f"Elpis{version}"
    data["release_tag"] = f"Elpis{version}"
    data["version"] = version
    data.update(identity)
    data["files"] = [{"path": f, "sha256": digest(f)} for f in files]
    data["file_count"] = len(files)

    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(data, indent=2) + "\n")
    print(f"sealed {manifest_rel.as_posix()}: {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
