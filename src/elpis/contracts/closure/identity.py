from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any


_HEX_RE = re.compile(r"^[0-9a-f]+$")


class ClosureIdentityError(ValueError):
    pass


def require_hex(
    value: str,
    *,
    field_name: str,
    exact_length: int | None = None,
    minimum_length: int = 16,
) -> str:
    if not isinstance(value, str):
        raise ClosureIdentityError(f"{field_name} must be a string")
    if exact_length is not None and len(value) != exact_length:
        raise ClosureIdentityError(
            f"{field_name} must contain exactly {exact_length} hex characters"
        )
    if exact_length is None and len(value) < minimum_length:
        raise ClosureIdentityError(
            f"{field_name} must contain at least {minimum_length} hex characters"
        )
    if not _HEX_RE.fullmatch(value):
        raise ClosureIdentityError(f"{field_name} must be lowercase hexadecimal")
    return value


def _canonical(value: Any) -> Any:
    if is_dataclass(value):
        return _canonical(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _canonical(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ClosureIdentityError(
        f"unsupported canonical identity value: {type(value).__name__}"
    )


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def content_checksum(domain: str, value: Any) -> str:
    if not domain:
        raise ClosureIdentityError("identity domain is required")
    digest = hashlib.sha256()
    digest.update(domain.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(canonical_json_bytes(value))
    return digest.hexdigest()
