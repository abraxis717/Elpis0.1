"""Canonical JSON encoding and digest computation for G5.0B artifacts.

Follows G5.0A canonicalization contract:
  - UTF-8 encoding
  - sorted_keys
  - no insignificant whitespace
  - boolean: true/false lowercase
  - null: null lowercase
  - integer: no decimal point
  - lists: stable specified order

Digest formula:
  SHA256( UTF8(domain_separator) || 0x00 || canonical_semantic_payload )
"""

import hashlib
import json


def canonical_json(obj) -> str:
    """Produce canonical JSON string for an object.

    Rules: sorted keys, no whitespace, ensure_ascii=False for UTF-8.
    """
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def canonical_json_bytes(obj) -> bytes:
    """Produce canonical JSON as UTF-8 bytes."""
    return canonical_json(obj).encode('utf-8')


def compute_digest(domain_separator: str, payload: dict) -> str:
    """Compute a G5 digest: SHA256(domain_separator || 0x00 || canonical_payload)."""
    separator_bytes = domain_separator.encode('utf-8')
    separator_bytes += b'\x00'
    payload_bytes = canonical_json_bytes(payload)
    return hashlib.sha256(separator_bytes + payload_bytes).hexdigest()


def sha256_of_bytes(data: bytes) -> str:
    """Compute SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_of_file(filepath: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


# Domain separators
EVIDENCE_DOMAIN = 'g5.structural-group-evidence.v1'
PROPOSAL_DOMAIN = 'g5.structural-group-proposal.v1'
ORDERING_DOMAIN = 'g5.proposal-ordering.v1'
CONFLICT_DOMAIN = 'g5.structural-conflict-evidence.v1'
