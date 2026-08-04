"""Source chain contract — expected values derived from census."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceContract:
    """Frozen contract derived from the census phase."""
    g53b1_manifest_files: int
    g53b1_disposition: str
    g53c_manifest_files: int
    g53c_disposition: str
    g53c_receipt_count: int
    g53c_artifact_digests: tuple
    g53c_capability_digests: tuple
    g53c_lifecycle_state: str
    g53c_shadow_receipt_digest: str
    g53c_resulting_state_digest: str
    g53c_resulting_ledger_head: str
    g53c_determinism_receipt_digest: str
    g53d_manifest_files: int
    g53d_disposition: str
    g53d_bundle_digest: str
    g53d_binding_count: int
