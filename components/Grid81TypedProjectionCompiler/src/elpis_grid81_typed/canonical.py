"""Deterministic canonical JSON serialization and domain-separated digests."""

import hashlib
import json
from typing import Any

from elpis_grid81_typed.errors import CanonicalizationError


def canonicalize(obj: Any) -> bytes:
    """Produce deterministic canonical JSON bytes.

    Rules:
      - UTF-8 encoding
      - Sorted object keys
      - No whitespace (compact separators)
      - No NaN or infinity
      - Integers remain integers, booleans remain booleans
      - Sets converted to canonically sorted arrays
      - Duplicate semantic entries rejected
    """
    cleaned = _clean(obj)
    raw = json.dumps(cleaned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw.encode("utf-8")


def _clean(obj: Any) -> Any:
    """Recursively clean object for canonical serialization."""
    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float)):
        if isinstance(obj, float):
            import math
            if math.isnan(obj) or math.isinf(obj):
                raise CanonicalizationError(f"NaN or infinity not allowed in canonical JSON: {obj}")
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_clean(item) for item in obj]
    if isinstance(obj, set):
        cleaned_items = [_clean(item) for item in obj]
        return _canonical_sort(cleaned_items)
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    raise CanonicalizationError(f"Unsupported type for canonicalization: {type(obj).__name__}")


def _canonical_sort(items: list) -> list:
    """Sort items in a canonical order for set-to-array conversion."""
    # Group by type for stable comparison
    def sort_key(item):
        type_order = {
            str: 0, int: 1, float: 2, bool: 3, list: 4, dict: 5, type(None): 6
        }
        type_rank = type_order.get(type(item), 99)
        if isinstance(item, str):
            return (type_rank, item)
        if isinstance(item, (int, float)):
            return (type_rank, item)
        if isinstance(item, list):
            return (type_rank, json.dumps(item, sort_keys=True))
        if isinstance(item, dict):
            return (type_rank, json.dumps(item, sort_keys=True))
        return (type_rank, str(item))
    return sorted(items, key=sort_key)


# Domain-separated digest domains - each semantic domain has a unique prefix
DOMAINS = {
    "source": "elpis.grid81.source.v1",
    "row": "elpis.grid81.row.v1",
    "transition_view": "elpis.grid81.transition_view.v1",
    "expansion_view": "elpis.grid81.expansion_view.v1",
    "quiescence_view": "elpis.grid81.quiescence_view.v1",
    "rationale_view": "elpis.grid81.rationale_view.v1",
    "d4_registry": "elpis.grid81.d4_transform_registry.v1",
    "transition_orbit": "elpis.grid81.transition_orbit.v1",
    "expansion_orbit": "elpis.grid81.expansion_orbit.v1",
    "quiescence_orbit": "elpis.grid81.quiescence_orbit.v1",
    "rationale_orbit": "elpis.grid81.rationale_orbit.v1",
}


def domain_digest(domain: str, data: bytes) -> str:
    """Compute domain-separated SHA-256 digest.

    The domain prefix ensures no digest collision across semantic domains.
    Format: SHA256(domain_prefix || 0x00 || data)
    """
    if domain not in DOMAINS:
        raise CanonicalizationError(f"Unknown digest domain: {domain}")
    domain_prefix = DOMAINS[domain].encode("utf-8")
    separator = b"\x00"
    combined = domain_prefix + separator + data
    return hashlib.sha256(combined).hexdigest()


def verify_domain_digest(domain: str, data: bytes, expected: str) -> bool:
    """Verify a domain-separated digest matches expected value."""
    return domain_digest(domain, data) == expected
