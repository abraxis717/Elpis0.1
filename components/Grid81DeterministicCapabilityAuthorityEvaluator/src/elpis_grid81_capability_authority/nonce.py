"""G5.2B Deterministic Nonce.

Nonce digest = SHA256(
    UTF8("g5.structural-influence-capability-nonce.v1") ||
    0x00 ||
    source_request_digest_bytes ||
    authority_policy_digest_bytes ||
    authority_context_digest_bytes
)

No randomness, UUID, wall clock, process state, or filesystem state.
"""
import hashlib

from .canonical import sha256_bytes


def compute_nonce_digest(source_request_digest: str,
                         authority_policy_digest: str,
                         authority_context_digest: str) -> str:
    """Compute deterministic nonce digest for a capability.

    Returns 64 lowercase hexadecimal characters.
    """
    nonce_prefix = b"g5.structural-influence-capability-nonce.v1"

    h = hashlib.sha256()
    h.update(nonce_prefix)
    h.update(b"\x00")
    h.update(source_request_digest.encode("utf-8"))
    h.update(authority_policy_digest.encode("utf-8"))
    h.update(authority_context_digest.encode("utf-8"))
    return h.hexdigest()


def validate_nonce_digest(nonce: str) -> bool:
    """Validate nonce digest format."""
    if not isinstance(nonce, str):
        return False
    if len(nonce) != 64:
        return False
    return all(c in "0123456789abcdef" for c in nonce)
