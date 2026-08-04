"""Canonical JSON encoding and digest computation."""

import hashlib
import json
import os


def canonical_json(obj) -> str:
    """Produce canonical JSON: sorted keys, no extra whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: str) -> str:
    """SHA-256 hex digest of a string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def canonical_digest(obj) -> str:
    """SHA-256 of canonical JSON representation of obj."""
    return sha256_hex(canonical_json(obj))


def file_sha256(path: str) -> str:
    """SHA-256 of file contents (raw bytes)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_digest(directory: str, exclude_patterns=None) -> str:
    """Deterministic tree digest over all files in directory.

    Walks sorted, hashes each file path + content in order.
    """
    if exclude_patterns is None:
        exclude_patterns = {"__pycache__", ".pytest_cache", ".git"}

    hasher = hashlib.sha256()
    all_files = []
    for root, dirs, files in os.walk(directory):
        # Filter excluded dirs in-place
        dirs[:] = sorted([d for d in dirs if d not in exclude_patterns])
        for fname in sorted(files):
            # Skip binary/cache files
            if fname.endswith((".pyc", ".pyo", "~")):
                continue
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, directory)
            all_files.append(rel)

    all_files.sort()
    for rel in all_files:
        fpath = os.path.join(directory, rel)
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\x00")
        with open(fpath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        hasher.update(b"\n")

    return hasher.hexdigest()


def digest_from_canonical_json_obj(obj) -> str:
    """Compute digest: canonical JSON of obj -> SHA-256."""
    return sha256_hex(canonical_json(obj))
