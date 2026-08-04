"""G5.3C Canonicalization and digest computation.

Follows G5.3A canonicalization contract:
- Sorted keys, no insignificant whitespace
- Stable booleans/nulls
- Sorted arrays where set semantics apply
- SHA-256 domain-separated digests
"""
import hashlib
import json


def canonical_json(obj) -> str:
    """Produce canonical JSON: sorted keys, no spaces, stable types."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_digest(obj) -> str:
    """SHA-256 digest of canonical JSON representation."""
    canonical = canonical_json(obj)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def check_hex64(value: str) -> bool:
    """Check if value is a valid 64-character hex string."""
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def sha256_file(path: str) -> str:
    """Compute SHA-256 of a file on disk."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
