"""Canonical serialization and digest for pair payloads (G4.0B).

Canonical bytes: JSON with sort_keys=True, separators=(',', ':').
Canonical digest: SHA-256 of canonical bytes."""

from __future__ import annotations
import hashlib
import json
from typing import Any

SCHEMA_ID: str = "elpis.d4_pair_payload.v1"
SCHEMA_VERSION: str = "1.0"


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    """Produce canonical byte representation of a pair payload.

    Deterministic JSON: sorted keys, no whitespace, consistent ordering.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_digest(payload: dict[str, Any]) -> str:
    """SHA-256 hex digest of canonical bytes."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def pair_orbit_digest(canonical_representative_bytes: bytes, schema_id: str, schema_version: str, registry_digest: str) -> str:
    """Compute pair_orbit_digest per G4.0A spec.

    Digest = SHA256(schema_version || registry_digest || canonical_representative)
    """
    combined = f"{schema_id}:{schema_version}:{registry_digest}:".encode("utf-8") + canonical_representative_bytes
    return hashlib.sha256(combined).hexdigest()
