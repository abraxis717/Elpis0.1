"""Canonical serialization and digest utilities for Darwinian life records."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_bytes(
    payload: dict[str, Any],
) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def payload_digest(
    payload: dict[str, Any],
) -> str:
    return hashlib.sha256(
        canonical_json_bytes(payload)
    ).hexdigest()


def require_sha256(
    value: str,
    *,
    field_name: str,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise ValueError(
            field_name
            + " must be a lowercase SHA-256 digest."
        )

    return value
