"""G5.3B Canonicalization and digest computation.

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


def canonical_semantic(obj) -> str:
    """Canonical JSON for semantic digest computation."""
    return canonical_json(obj)


def canonical_digest(obj) -> str:
    """SHA-256 digest of canonical JSON representation."""
    canonical = canonical_json(obj)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def domain_digest(domain_separator: str, obj) -> str:
    """SHA256(UTF8(domain_separator) || 0x00 || canonical_semantic_payload)."""
    canonical = canonical_json(obj)
    payload = domain_separator.encode("utf-8") + b"\x00" + canonical.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def check_hex64(value: str) -> bool:
    """Check if value is a valid 64-character hex string."""
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False
