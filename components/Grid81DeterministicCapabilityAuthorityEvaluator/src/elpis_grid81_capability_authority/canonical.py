"""Canonicalization utilities for G5.2B.

Implements the G5.2A canonicalization contract:
- sorted keys
- no insignificant whitespace
- stable booleans
- stable null
- arrays sorted where set semantics apply
- SHA-256 digests
- UTF-8 encoding
"""
import hashlib
import json


def sha256_bytes(data: bytes) -> str:
    """SHA-256 digest as 64 lowercase hex chars."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    """SHA-256 digest of a file's raw bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj) -> str:
    """Canonical JSON: sorted keys, no insignificant whitespace, stable booleans/null."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_json_bytes(obj) -> bytes:
    """Canonical JSON as UTF-8 bytes."""
    return canonical_json(obj).encode("utf-8")


def canonical_digest(obj) -> str:
    """SHA-256 of canonical JSON representation."""
    return sha256_bytes(canonical_json_bytes(obj))


def domain_digest(domain_separator: str, obj) -> str:
    """Domain-separator digest: SHA256(UTF8(domain_separator) || 0x00 || canonical_semantic_payload)."""
    h = hashlib.sha256()
    h.update(domain_separator.encode("utf-8"))
    h.update(b"\x00")
    h.update(canonical_json_bytes(obj))
    return h.hexdigest()


def sorted_hex_list(items: list) -> list:
    """Return sorted list of hex strings, ensuring uniqueness."""
    return sorted(set(items))


def check_hex64(value: str, field: str = "") -> bool:
    """Check that a value is exactly 64 lowercase hex characters."""
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
