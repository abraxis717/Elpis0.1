"""Elpis Canonical Object Digest v1.

Digest law:
  sha256(canonical_bytes(all object fields except that object's digest field))

Floats are canonicalized as exact IEEE-754 hexadecimal strings. This avoids
self-reference and decimal rendering drift. Nested digest values remain part of
the parent object's payload; only the explicitly named top-level field is
excluded.
"""

from __future__ import annotations

import base64
from dataclasses import asdict, is_dataclass
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .errors import DigestRuleViolation

ALGORITHM = "sha256"
SCHEMA = "elpis.canonical-object-digest.v1"
_FLOAT_TAG = "$elpis_f64_hex"
_BYTES_TAG = "$elpis_bytes_b64"


def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Enum):
        return _normalize(value.value)
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DigestRuleViolation("non-finite float cannot be canonicalized")
        return {_FLOAT_TAG: value.hex()}
    if isinstance(value, bytes):
        return {_BYTES_TAG: base64.b64encode(value).decode("ascii")}
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise DigestRuleViolation("canonical mappings require string keys")
            result[key] = _normalize(child)
        return result
    if isinstance(value, (list, tuple)):
        return [_normalize(child) for child in value]
    raise DigestRuleViolation(f"unsupported canonical value type: {type(value)!r}")


def canonical_bytes(value: Any, *, digest_field: str | None = None) -> bytes:
    normalized = _normalize(value)
    if digest_field is not None:
        if not isinstance(normalized, dict):
            raise DigestRuleViolation("digest_field exclusion requires a mapping object")
        normalized = dict(normalized)
        normalized.pop(digest_field, None)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_digest(value: Any, *, digest_field: str | None = None) -> str:
    return f"{ALGORITHM}:" + hashlib.sha256(
        canonical_bytes(value, digest_field=digest_field)
    ).hexdigest()


def validate_digest(value: Any, *, digest_field: str) -> bool:
    if is_dataclass(value):
        actual = getattr(value, digest_field)
    elif isinstance(value, Mapping):
        actual = value.get(digest_field)
    else:
        raise DigestRuleViolation("digest validation requires dataclass or mapping")
    expected = canonical_digest(value, digest_field=digest_field)
    return actual == expected
