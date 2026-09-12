"""Elpis ECS M1A — canonical serialization and domain-separated digests.

This module provides the ONLY canonical byte form and digest used by the
kernel. Every digest in the system is a domain-separated SHA-256 over a
canonical JSON byte form, to distinguish domains before hashing (subject to SHA-256 collision
resistance).

IMPORTANT (per adjudication): these digests provide CONTENT IDENTITY and
INTEGRITY only. They are NOT authentication and NOT proof of issuer. A digest
over public/re-derivable inputs can be recomputed by any party; it binds
content, not origin. See ECS/design/13-nonclaims.md.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .errors import CanonicalError

# ---------------------------------------------------------------------------
# Domain separation tags. Each distinct record type digests under its own
# domain so that, e.g., an entity founding record and a message envelope have
# different hash inputs even if their canonical JSON payloads match.
# ---------------------------------------------------------------------------

DOMAIN_ENTITY_FOUNDED = "ecs.entity.founded.v1"
DOMAIN_ENTITY_STATE = "ecs.entity.state.v1"
DOMAIN_MESSAGE = "ecs.message.v1"
DOMAIN_EVENT = "ecs.event.v1"
DOMAIN_STATE_ROOT = "ecs.state_root.v1"
DOMAIN_CHECKPOINT = "ecs.checkpoint.v1"
DOMAIN_GENESIS = "ecs.genesis.v1"

# Schema / protocol version constants (bumped only on canonical-form change).
SCHEMA_VERSION = 1
MESSAGE_SCHEMA = "ecs.message.v1"
EVENT_SCHEMA = "ecs.event.v1"


def canonical_bytes(obj: Any) -> bytes:
    """Minimal canonical JSON: sorted keys, compact separators, no NaN.

    This is the single canonical byte form for all JSON-serializable kernel
    records. It matches the repository P0/R0 convention so that digests are
    comparable across the codebase.
    """
    try:
        return json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise CanonicalError(f"CANONICAL_SERIALIZATION_FAILED: {exc}") from exc


def sha256_hex(data: bytes) -> str:
    """Lowercase SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def digest(obj: Any) -> str:
    """Canonical digest of any JSON-serializable object (no domain tag)."""
    return sha256_hex(canonical_bytes(obj))


def domain_digest(domain: str, obj: Any) -> str:
    """Domain-separated canonical digest.

    The domain tag is bound into the hashed byte form so that the same payload
    under two different domains yields two different digests. This is content
    identity/integrity only — NOT authentication.
    """
    if not isinstance(domain, str) or not domain:
        raise CanonicalError("DOMAIN_INVALID: empty/non-string domain")
    return sha256_hex(canonical_bytes({"domain": domain, "payload": obj}))


def digest_bytes(raw: bytes) -> str:
    """Domain-separated digest of raw (already-canonical) bytes."""
    return sha256_hex(canonical_bytes({"bytes": raw.hex()}))
