#!/usr/bin/env python3
"""Deterministic secret and sensitive-data scanner for CI qualification.

Replaces the previous shell-grep approach which had false-positive issues:
  - Loose 'sk-' pattern matched 'task-1' and other benign strings
  - Scanner scanned its own detector definitions

Uses context-aware regex patterns with realistic token lengths and alphabets.
Never prints actual secret material — only reports the file and pattern name.

Exit codes:
  0 — clean (no secrets found)
  1 — secrets or private paths detected
  2 — scanner error
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Detectors — each is (compiled_regex, human_label)
# Realistic token lengths prevent false positives on ordinary variable names.
# ---------------------------------------------------------------------------

SECRET_DETECTORS: list[tuple[re.Pattern[str], str]] = [
    # Private keys
    (re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"), "PRIVATE_KEY_HEADER"),
    # GitHub personal access tokens: ghp_ + 36 alphanumeric chars
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "GITHUB_PAT"),
    # GitHub fine-grained PAT: github_pat_ + prefix + alphanumeric
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "GITHUB_FINE_PAT"),
    # OpenAI-style keys: sk- + 48 chars from base58-like alphabet
    (re.compile(r"sk-[A-Za-z0-9]{48,}"), "OPENAI_KEY"),
    # AWS access key IDs: AKIA + 16 uppercase alphanumeric
    (re.compile(r"AKIA[A-Z0-9]{16}"), "AWS_ACCESS_KEY"),
    # Google API keys: AIza + 35 chars
    (re.compile(r"AIza[A-Za-z0-9_-]{35}"), "GOOGLE_API_KEY"),
    # Bearer tokens with realistic length (not just "Bearer...")
    (re.compile(r'"?Authorization"?\s*:\s*"Bearer\s+[A-Za-z0-9._\-]{20,}'), "BEARER_TOKEN"),
    # Password assignments with non-trivial values
    (re.compile(r'(?:password|passwd)\s*=\s*["\'][^"\']{8,}["\']', re.IGNORECASE), "PASSWORD_ASSIGN"),
    # Secret assignments with non-trivial values
    (re.compile(r'(?:secret|api_key|apikey|secret_key)\s*=\s*["\'][^"\']{8,}["\']', re.IGNORECASE), "SECRET_ASSIGN"),
]

# Private-path detectors
PRIVATE_PATHS: list[str] = [
    "/mnt/primesauce",
    "/home/joe",
]

# Binary/artifact extensions
BINARY_EXTENSIONS: set[str] = {
    ".so", ".a", ".o", ".pyc", ".egg", ".gguf", ".safetensors", ".pt",
}

# Directories to skip entirely
SKIP_DIRS: set[str] = {
    ".git", "__pycache__", ".pytest_cache", "node_modules", ".egg-info",
    "build", "CMakeFiles", "CMakeCache.txt",
}

# Extensions to scan for secrets/paths
TEXT_EXTENSIONS: set[str] = {
    ".py", ".c", ".cpp", ".h", ".hpp", ".json", ".toml", ".yaml", ".yml",
    ".md", ".txt", ".cff", ".txt", ".cmake", ".sh",
}

# The scanner's own filename — skip it to avoid self-triggering
SELF_NAME = Path(__file__).name

# Test files that contain synthetic fixtures — skip for self-trigger prevention
TEST_FIXTURE_NAMES: set[str] = {
    "test_ci_secret_scan.py",
}

# Files that contain FORBIDDEN_PREFIXES security guard patterns with intentional
# workstation paths — skip to avoid false positives on security guards
GUARD_NAMES: set[str] = {
    "transaction.py",
    "test_r0_transaction.py",
    "verify_public_release.py",
}


def scan_secrets(repo_root: Path) -> list[str]:
    """Scan for secrets and return list of finding descriptions."""
    findings: list[str] = []
    for f in repo_root.rglob("*"):
        if f.is_dir():
            continue
        if any(part in SKIP_DIRS for part in f.parts):
            continue
        if f.name == SELF_NAME:
            continue
        if f.name in TEST_FIXTURE_NAMES:
            continue
        if f.suffix not in TEXT_EXTENSIONS:
            continue
        try:
            content = f.read_text(errors="replace")
        except Exception:
            continue
        for pat, label in SECRET_DETECTORS:
            if pat.search(content):
                rel = f.relative_to(repo_root)
                findings.append(f"SECRET '{label}' in {rel}")
    return findings


def scan_private_paths(repo_root: Path) -> list[str]:
    """Scan for private workstation paths in JSON and text files."""
    findings: list[str] = []
    for f in repo_root.rglob("*"):
        if f.is_dir():
            continue
        if any(part in SKIP_DIRS for part in f.parts):
            continue
        if f.name == SELF_NAME:
            continue
        if f.name in TEST_FIXTURE_NAMES or f.name in GUARD_NAMES:
            continue
        if f.suffix not in TEXT_EXTENSIONS and f.suffix != ".json":
            continue
        if f.name == SELF_NAME:
            continue
        try:
            content = f.read_text(errors="replace")
        except Exception:
            continue
        for path in PRIVATE_PATHS:
            if path in content:
                rel = f.relative_to(repo_root)
                findings.append(f"PRIVATE PATH '{path}' in {rel}")
    return findings


def scan_binaries(repo_root: Path) -> list[str]:
    """Check for tracked binary artifacts."""
    findings: list[str] = []
    for f in repo_root.rglob("*"):
        if f.is_dir():
            continue
        if any(part in SKIP_DIRS for part in f.parts):
            continue
        if f.suffix in BINARY_EXTENSIONS:
            rel = f.relative_to(repo_root)
            findings.append(f"BINARY ARTIFACT: {rel}")
    return findings


def run_scan(repo_root: str) -> dict:
    """Run all scans and return structured results."""
    root = Path(repo_root).resolve()
    secret_findings = scan_secrets(root)
    path_findings = scan_private_paths(root)
    binary_findings = scan_binaries(root)

    result = {
        "secrets": secret_findings,
        "private_paths": path_findings,
        "binary_artifacts": binary_findings,
        "total_findings": len(secret_findings) + len(path_findings) + len(binary_findings),
        "clean": (
            len(secret_findings) == 0
            and len(path_findings) == 0
            and len(binary_findings) == 0
        ),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Elpis CI secret scanner")
    parser.add_argument(
        "repo_root", nargs="?", default=".",
        help="Path to repository root (default: current directory)",
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    result = run_scan(args.repo_root)

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        if result["secrets"]:
            print("SECRETS FOUND:")
            for f in result["secrets"]:
                print(f"  -> {f}")
        else:
            print("Secret scan: PASS")
        if result["private_paths"]:
            print("PRIVATE PATHS FOUND:")
            for f in result["private_paths"]:
                print(f"  -> {f}")
        else:
            print("Private path scan: PASS")
        if result["binary_artifacts"]:
            print("BINARY ARTIFACTS FOUND:")
            for f in result["binary_artifacts"]:
                print(f"  -> {f}")
        else:
            print("Binary scan: PASS")

    if not result["clean"]:
        print(f"\nFAIL: {result['total_findings']} finding(s)")
        return 1
    else:
        print("\nPASS: Clean")
        return 0


if __name__ == "__main__":
    sys.exit(main())
