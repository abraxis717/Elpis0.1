"""G5.2B Verifier module.

Re-exports verification functions for use by the independent verifier script.
"""
from .upstream import verify_manifest, verify_cross_seals, EXPECTED_DIGESTS
from .source_join import load_jsonl, perform_source_join
from .canonical import sha256_file, sha256_bytes, canonical_digest, canonical_json

__all__ = [
    "verify_manifest",
    "verify_cross_seals",
    "EXPECTED_DIGESTS",
    "load_jsonl",
    "perform_source_join",
    "sha256_file",
    "sha256_bytes",
    "canonical_digest",
    "canonical_json",
]
