"""Canonical constants, digest utilities, and deterministic serialization for FS0.1."""

import hashlib
import json
import struct
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Determinism constants
# ---------------------------------------------------------------------------

SHA256_DOMAIN_SEPARATOR = b"elpis.fs01.sha256."

CANONICAL_JSON_SORT_KEYS = True
CANONICAL_JSON_SEPARATORS = (",", ":")

# Epsilon constants — overridable via config, these are the defaults.
DEFAULT_BASIS_EPSILON: float = 1e-12
DEFAULT_SIGN_EPSILON: float = 1e-15
DEFAULT_NORM_EPSILON: float = 1e-12
DEFAULT_DEPENDENCE_EPSILON: float = 1e-10
DEFAULT_DEPENDENCE_EPSILON_REL: float = 1e-8
DEFAULT_RATIONALE_THRESHOLD: float = 0.01
DEFAULT_RE_ORTHOGONALIZATION_PASSES: int = 2

# Recursive embedding defaults
DEFAULT_PARENT_DECAY: float = 0.5
DEFAULT_LOCAL_WEIGHT: float = 1.0
DEFAULT_MAX_DEPTH: int = 1

# ---------------------------------------------------------------------------
# Canonical JSON serialization
# ---------------------------------------------------------------------------

def canonical_json(obj: Any) -> bytes:
    """Produce canonical JSON bytes: sorted keys, minimal separators, UTF-8."""
    return json.dumps(
        obj,
        sort_keys=CANONICAL_JSON_SORT_KEYS,
        separators=CANONICAL_JSON_SEPARATORS,
        ensure_ascii=False,
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# SHA-256 with domain separator
# ---------------------------------------------------------------------------

def sha256_digest(data: bytes) -> str:
    """Compute SHA-256 hex digest with domain separator."""
    return hashlib.sha256(SHA256_DOMAIN_SEPARATOR + data).hexdigest()


def json_sha256(obj: Any) -> str:
    """SHA-256 of canonical JSON representation."""
    return sha256_digest(canonical_json(obj))


# ---------------------------------------------------------------------------
# Float vector canonicalization and byte encoding
# ---------------------------------------------------------------------------

def canonicalize_float_vector(vec: np.ndarray) -> np.ndarray:
    """
    Canonicalize a float64 vector:
    - Ensure C-contiguous, dtype float64
    - Replace -0.0 with +0.0
    - Reject NaN and Inf
    """
    arr = np.asarray(vec, dtype=np.float64).copy()
    arr = np.ascontiguousarray(arr)

    if not np.all(np.isfinite(arr)):
        raise ValueError(
            "Vector contains non-finite values (NaN or Inf). Cannot canonicalize."
        )

    # Canonicalize negative zero to positive zero.
    arr = np.where(arr == 0.0, 0.0, arr)

    return arr


def vector_to_bytes(vec: np.ndarray) -> bytes:
    """Convert canonicalized float64 vector to little-endian byte string."""
    arr = canonicalize_float_vector(vec)
    return arr.tobytes("C")


def vector_sha256(vec: np.ndarray) -> str:
    """SHA-256 of a canonicalized float64 vector byte representation."""
    return sha256_digest(vector_to_bytes(vec))


# ---------------------------------------------------------------------------
# Tuple helpers for frozen dataclasses
# ---------------------------------------------------------------------------

def floats_as_tuple(vec: np.ndarray) -> tuple:
    """Convert canonicalized float vector to a tuple of Python floats."""
    arr = canonicalize_float_vector(vec)
    return tuple(float(x) for x in arr)


def metadata_as_tuples(
    metadata: dict,
) -> tuple:
    """Convert dict to sorted tuple of (key, value) pairs for immutability."""
    return tuple(sorted(metadata.items()))
