"""Internal Header validation helpers.

Canonical serialization and identity remain owned by Artifacts.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def require_digest(name: str, value: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a 64-character lowercase SHA-256 hex digest")
    return value


def require_optional_digest(name: str, value: str | None) -> str | None:
    if value is not None:
        require_digest(name, value)
    return value


def require_nonnegative_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def require_positive_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def require_probability(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be finite and within [0, 1]")
    return value


def require_finite_vector(
    name: str,
    values: Iterable[float],
    *,
    length: int,
) -> tuple[float, ...]:
    vector = tuple(float(v) for v in values)
    if len(vector) != length:
        raise ValueError(f"{name} must contain exactly {length} values")
    if not all(math.isfinite(v) for v in vector):
        raise ValueError(f"{name} must contain only finite values")
    return vector
