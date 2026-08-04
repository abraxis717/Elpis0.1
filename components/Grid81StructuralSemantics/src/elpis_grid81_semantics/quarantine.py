"""QuarantineIdentityV1 — three-part identity (G4.0B Phase 10).

Separate fields:
  canonical_payload_digest: SHA-256 of canonicalized payload bytes (semantic identity)
  raw_byte_sha256: SHA-256 of original raw bytes (exact representation)
  provenance_root_digest: SHA-256 of provenance root (origin/lineage)

Do NOT collapse into one digest.
"""

from __future__ import annotations
import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QuarantineIdentityV1:
    canonical_payload_digest: str
    raw_byte_sha256: str
    provenance_root_digest: str


def compute_quarantine_identity(
    payload_dict: dict[str, Any],
    raw_bytes: bytes,
    provenance_data: str,
) -> QuarantineIdentityV1:
    """Compute three-part quarantine identity."""
    import json
    canonical_b = json.dumps(payload_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    canonical_digest = hashlib.sha256(canonical_b).hexdigest()
    raw_digest = hashlib.sha256(raw_bytes).hexdigest()
    provenance_digest = hashlib.sha256(provenance_data.encode("utf-8")).hexdigest()
    return QuarantineIdentityV1(
        canonical_payload_digest=canonical_digest,
        raw_byte_sha256=raw_digest,
        provenance_root_digest=provenance_digest,
    )


def compute_quarantine_from_pair(
    pair_dict: dict[str, Any],
    provenance_digest: str | None = None,
) -> QuarantineIdentityV1:
    """Compute quarantine identity from a pair dict and optional provenance."""
    import json
    canonical_b = json.dumps(pair_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    canonical_digest = hashlib.sha256(canonical_b).hexdigest()
    # raw bytes = canonical bytes when pair is already canonical
    raw_digest = canonical_digest
    if provenance_digest is None:
        provenance_digest = hashlib.sha256(b"").hexdigest()
    return QuarantineIdentityV1(
        canonical_payload_digest=canonical_digest,
        raw_byte_sha256=raw_digest,
        provenance_root_digest=provenance_digest,
    )
