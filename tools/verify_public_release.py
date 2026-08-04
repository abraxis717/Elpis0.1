#!/usr/bin/env python3
"""Public release verifier for Elpis-Canonical.

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


def check_manifest() -> tuple[bool, list[str]]:
    """Verify PUBLIC_RELEASE_MANIFEST.json exists and all files match digests."""
    errors = []
    manifest_path = REPO / "manifests/PUBLIC_RELEASE_MANIFEST.json"
    if not manifest_path.exists():
        return False, ["PUBLIC_RELEASE_MANIFEST.json not found"]

    manifest = json.loads(manifest_path.read_text())
    if manifest.get("version") != "v1.1.1":
        errors.append(f"Expected version v1.1.1, got {manifest.get('version')}")

    undeclared = []
    mismatch = []
    for entry in manifest.get("files", []):
        # Skip self-reference: the manifest cannot contain its own digest
        if entry["path"] == "manifests/PUBLIC_RELEASE_MANIFEST.json":
            continue
        fp = REPO / entry["path"]
        if not fp.exists():
            mismatch.append(f"MISSING: {entry['path']}")
            continue
        actual = sha256(fp)
        if actual != entry["sha256"]:
            mismatch.append(f"DIGEST MISMATCH: {entry['path']}")

    # Check for undeclared top-level roots
    declared_paths = {e["path"].split("/")[0] for e in manifest.get("files", [])}
    for item in sorted(REPO.iterdir()):
        if item.is_dir() and item.name.startswith("."):
            continue  # .git is expected to be absent or empty
        if item.name not in declared_paths and item.name not in (".git", "build"):
            undeclared.append(f"UNDECLARED: {item.name}")

    if mismatch:
        errors.extend(mismatch)
    if undeclared:
        errors.extend(undeclared)

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
    secret_patterns = [
        (r'BEGIN PRIVATE KEY', "BEGIN PRIVATE KEY"),
        (r'ghp_[A-Za-z0-9_]{10,}', "GitHub personal access token"),
        (r'github_pat_[A-Za-z0-9_]{10,}', "GitHub PAT"),
        (r'sk-[A-Za-z0-9]{20,}', "OpenAI-style API key"),
        (r'AKIA[A-Z0-9]{16}', "AWS access key"),
        (r'AIza[A-Za-z0-9_-]{35}', "Google API key"),
        (r'Authorization:\s*Bearer\s+\S+', "Bearer token"),
        (r'password\s*=\s*["\'][^\x00-\x7F]', "Non-ASCII password literal"),
        (r'secret\s*=\s*["\'][^\x00-\x7F]', "Non-ASCII secret literal"),
    ]
    scan_extensions = {".py", ".c", ".cpp", ".h", ".json", ".toml", ".md"}
    for f in REPO.rglob("*"):
        if f.suffix not in scan_extensions:
            continue
        # Skip the verifier itself — it contains pattern strings for scanning
        if f.name == "verify_public_release.py":
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

    # Check for private paths
    for f in REPO.rglob("*.json"):
        if ".egg-info" in str(f):
            continue
        try:
            content = f.read_text()
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
    """Check for undeclared top-level directory roots."""
    allowed_roots = {
        "components", "native", "runtime", "docs", "manifests", "tests", "tools",
        ".github", "LICENSE", "LICENSES", "README.md", "VERSION", "pyproject.toml",
        "CMakeLists.txt", "RELEASE_NOTES.md", "CHANGELOG.md", "CITATION.cff",
        "SECURITY.md", "CONTRIBUTING.md", "THIRD_PARTY_NOTICES.md",
        "COMPONENT_REGISTRY.json", "ELPIS_CANONICAL_MANIFEST.json", ".gitignore",
    }
    # .git may exist if in a git repo, skip it
    errors = []
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
