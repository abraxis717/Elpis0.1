#!/usr/bin/env python3
"""Public release verifier for Elpis0.1.

Verifies the integrity, composition, and safety of the public distribution.
Exits 0 on PASS, 1 on FAIL with detailed diagnostics.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_post_release_overlay() -> tuple[dict, list[str]]:
    """Load and structurally validate the post-release overlay."""
    errors = []
    overlay_path = REPO / "manifests/PUBLIC_POST_RELEASE_OVERLAY.json"
    if not overlay_path.exists():
        return {}, ["PUBLIC_POST_RELEASE_OVERLAY.json not found"]

    try:
        overlay = json.loads(overlay_path.read_text())
    except Exception as exc:
        return {}, [f"Invalid PUBLIC_POST_RELEASE_OVERLAY.json: {exc}"]

    if overlay.get("schema") != "elpis.public-post-release-overlay.v1":
        errors.append(f"Unexpected overlay schema: {overlay.get('schema')}")
    if overlay.get("repository") != "abraxis717/Elpis0.1":
        errors.append(f"Unexpected overlay repository: {overlay.get('repository')}")
    if overlay.get("base_release") != "v1.1.2":
        errors.append(f"Unexpected overlay base release: {overlay.get('base_release')}")

    return overlay, errors


def check_manifest() -> tuple[bool, list[str]]:
    """Verify the immutable v1.1.2 seal plus explicitly declared post-release changes."""
    errors = []
    manifest_path = REPO / "manifests/PUBLIC_RELEASE_MANIFEST.json"
    if not manifest_path.exists():
        return False, ["PUBLIC_RELEASE_MANIFEST.json not found"]

    manifest = json.loads(manifest_path.read_text())
    if manifest.get("version") != "v1.1.2":
        errors.append(f"Expected historical release v1.1.2, got {manifest.get('version')}")

    overlay, overlay_errors = load_post_release_overlay()
    errors.extend(overlay_errors)

    historical = {
        entry["path"]: entry
        for entry in manifest.get("files", [])
        if entry["path"] != "manifests/PUBLIC_RELEASE_MANIFEST.json"
    }

    overlay_entries = {}
    for entry in overlay.get("paths", []):
        rel = entry.get("path")
        classification = entry.get("classification")
        digest = entry.get("sha256")

        if not isinstance(rel, str) or not rel:
            errors.append("Overlay entry has invalid path")
            continue
        if rel in overlay_entries:
            errors.append(f"Duplicate overlay path: {rel}")
            continue
        if classification not in {"ADDED", "POST_RELEASE_MODIFIED"}:
            errors.append(f"Invalid overlay classification for {rel}: {classification}")
            continue
        if not isinstance(digest, str) or len(digest) != 64:
            errors.append(f"Invalid overlay digest for {rel}")
            continue

        if classification == "ADDED" and rel in historical:
            errors.append(f"Overlay marks historical path as ADDED: {rel}")
        if classification == "POST_RELEASE_MODIFIED" and rel not in historical:
            errors.append(f"Overlay modifies path absent from historical seal: {rel}")

        overlay_entries[rel] = entry

    for rel, entry in historical.items():
        fp = REPO / rel
        if not fp.exists():
            errors.append(f"MISSING: {rel}")
            continue

        expected = entry["sha256"]
        if rel in overlay_entries:
            expected = overlay_entries[rel]["sha256"]

        actual = sha256(fp)
        if actual != expected:
            errors.append(f"DIGEST MISMATCH: {rel}")

    for rel, entry in overlay_entries.items():
        fp = REPO / rel
        if not fp.exists():
            errors.append(f"OVERLAY MISSING: {rel}")
            continue
        actual = sha256(fp)
        if actual != entry["sha256"]:
            errors.append(f"OVERLAY DIGEST MISMATCH: {rel}")

    declared_roots = {
        entry["path"].split("/")[0]
        for entry in manifest.get("files", [])
    }
    declared_roots.update(overlay.get("allowed_new_roots", []))

    for item in sorted(REPO.iterdir()):
        if item.is_dir() and item.name.startswith("."):
            continue
        if item.name not in declared_roots and item.name not in (".git", "build"):
            errors.append(f"UNDECLARED: {item.name}")

    return len(errors) == 0, errors


def check_components() -> tuple[bool, list[str]]:
    """Verify all 17 components are represented."""
    errors = []
    registry = REPO / "manifests/PUBLIC_COMPONENT_REGISTRY.json"
    if not registry.exists():
        return False, ["PUBLIC_COMPONENT_REGISTRY.json not found"]

    data = json.loads(registry.read_text())
    if data.get("component_count") != 17:
        errors.append(f"Expected 17 components, got {data.get('component_count')}")

    for comp in data.get("components", []):
        pub_path = REPO / comp["public_path"]
        if not pub_path.exists():
            errors.append(f"Component path missing: {comp['public_path']}")

    return len(errors) == 0, errors


def check_no_secrets() -> tuple[bool, list[str]]:
    """Scan for secrets and private data.

    Uses context-aware matching to avoid false positives on legitimate uses
    of words like 'token' (e.g., 'token_count', 'token_record', 'tokenization')
    and 'sk-' in structural context (e.g., 'sklearn', structural keys).
    """
    errors = []
    # Patterns that indicate actual secrets (not legitimate variable/function names)
    import re
    # Realistic token-length patterns — avoid false positives on 'task-1', 'sklearn', etc.
    secret_patterns = [
        (r'BEGIN PRIVATE KEY', "BEGIN PRIVATE KEY"),
        (r'ghp_[A-Za-z0-9]{36}', "GitHub personal access token"),
        (r'github_pat_[A-Za-z0-9_]{20,}', "GitHub PAT"),
        (r'sk-[A-Za-z0-9]{48,}', "OpenAI-style API key"),
        (r'AKIA[A-Z0-9]{16}', "AWS access key"),
        (r'AIza[A-Za-z0-9_-]{35}', "Google API key"),
        (r'"?Authorization"?\s*:\s*"Bearer\s+[A-Za-z0-9._\-]{20,}', "Bearer token"),
    ]
    # Files that contain synthetic secret fixtures for scanner testing — skip
    _fixture_names = {"ci_secret_scan.py", "test_ci_secret_scan.py"}
    # Files that contain FORBIDDEN_PREFIXES security guard patterns (intentional workstation paths)
    _guard_names = {"transaction.py", "test_r0_transaction.py"}
    _skip_names = _fixture_names | _guard_names
    scan_extensions = {".py", ".c", ".cpp", ".h", ".json", ".toml", ".md"}
    for f in REPO.rglob("*"):
        if f.suffix not in scan_extensions:
            continue
        # Skip the verifier itself and test fixtures that contain synthetic secrets
        if f.name == "verify_public_release.py" or f.name in _skip_names:
            continue
        if ".egg-info" in str(f) or "__pycache__" in str(f):
            continue
        try:
            content = f.read_text(errors="replace")
        except Exception:
            continue
        for pat, desc in secret_patterns:
            if re.search(pat, content):
                errors.append(f"SECRET PATTERN '{desc}' in {f.relative_to(REPO)}")

    # Check for private paths across all text files
    all_text_extensions = {".py", ".c", ".cpp", ".h", ".json", ".toml", ".yaml", ".yml", ".md", ".txt", ".cff", ".cmake", ".sh"}
    for f in REPO.rglob("*"):
        if f.suffix not in all_text_extensions:
            continue
        if f.name == "verify_public_release.py" or f.name in _skip_names:
            continue
        if ".egg-info" in str(f) or "__pycache__" in str(f):
            continue
        try:
            content = f.read_text(errors="replace")
        except Exception:
            continue
        for bad in ["/mnt/primesauce", "/home/joe"]:
            if bad in content:
                errors.append(f"PRIVATE PATH '{bad}' in {f.relative_to(REPO)}")

    return len(errors) == 0, errors


def check_no_binaries() -> tuple[bool, list[str]]:
    """Check for compiled binaries, model weights, or build artifacts."""
    errors = []
    bad_extensions = {".so", ".a", ".o", ".pyc", ".egg", ".gguf", ".safetensors", ".pt"}
    for f in REPO.rglob("*"):
        if f.is_file() and f.suffix in bad_extensions:
            errors.append(f"BINARY/ARTIFACT: {f.relative_to(REPO)}")

    # Check for symlinks escaping the repository
    for f in REPO.rglob("*"):
        if f.is_symlink():
            target = f.resolve()
            if not target.is_relative_to(REPO):
                errors.append(f"SYMLINK ESCAPE: {f.relative_to(REPO)} -> {target}")

    return len(errors) == 0, errors


def check_runtime_admission() -> tuple[bool, list[str]]:
    """Verify runtime admission is FALSE."""
    errors = []
    registry = REPO / "manifests/PUBLIC_COMPONENT_REGISTRY.json"
    if not registry.exists():
        return False, ["PUBLIC_COMPONENT_REGISTRY.json not found"]
    data = json.loads(registry.read_text())
    if data.get("runtime_admission") is not False:
        errors.append(f"Runtime admission must be FALSE, got {data.get('runtime_admission')}")
    for comp in data.get("components", []):
        if comp.get("runtime_admission") is not False:
            errors.append(f"Component {comp['component_id']} runtime_admission must be FALSE")
    return len(errors) == 0, errors


def check_no_generated() -> tuple[bool, list[str]]:
    """Check for generated artifacts in source tree."""
    errors = []
    bad_dirs = {"__pycache__", ".pytest_cache", "CMakeFiles", "build"}
    for f in REPO.rglob("*"):
        if f.is_dir():
            if f.name in bad_dirs:
                errors.append(f"GENERATED DIR: {f.relative_to(REPO)}")
    return len(errors) == 0, errors


def check_undeclared_roots() -> tuple[bool, list[str]]:
    """Check top-level roots against the release plus post-release overlay."""
    allowed_roots = {
        "components", "native", "runtime", "docs", "manifests", "tests", "tools", "src",
        ".github", "LICENSE", "LICENSES", "README.md", "VERSION", "pyproject.toml",
        "CMakeLists.txt", "RELEASE_NOTES.md", "CHANGELOG.md", "CITATION.cff",
        "SECURITY.md", "CONTRIBUTING.md", "THIRD_PARTY_NOTICES.md",
        "COMPONENT_REGISTRY.json", "ELPIS_CANONICAL_MANIFEST.json", ".gitignore",
    }

    overlay, overlay_errors = load_post_release_overlay()
    errors = list(overlay_errors)
    allowed_roots.update(overlay.get("allowed_new_roots", []))

    for item in sorted(REPO.iterdir()):
        if item.name.startswith(".") and item.name != ".github":
            continue
        if item.name not in allowed_roots:
            errors.append(f"UNDECLARED ROOT: {item.name}")

    return len(errors) == 0, errors


def main() -> int:
    checks = [
        ("Manifest integrity", check_manifest),
        ("Component representation", check_components),
        ("Secret scan", check_no_secrets),
        ("Binary/artifact scan", check_no_binaries),
        ("Runtime admission", check_runtime_admission),
        ("Generated artifacts", check_no_generated),
        ("Undeclared roots", check_undeclared_roots),
    ]

    all_pass = True
    for name, fn in checks:
        ok, errors = fn()
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"[{status}] {name}")
        for e in errors:
            print(f"  -> {e}")

    if all_pass:
        print("\\nPASS: Public release verified")
        return 0
    else:
        print("\\nFAIL: Public release verification failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
