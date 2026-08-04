"""Source row identity for provenance binding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from elpis_grid81_typed.canonical import canonicalize, domain_digest
from elpis_grid81_typed.errors import SourceIdentityError


# Fields that are explicitly non-semantic transport fields per G4.0A.3
# These are excluded from the source_row_digest computation.
# The authoritative source is the full row; all fields contribute to identity.
# No transport-only fields exist in the T00 corpus ABI.
NONSEMANTIC_TRANSPORT_FIELDS: frozenset = frozenset()


@dataclass(frozen=True)
class SourceRowIdentityV1:
    """Canonical source row identity with provenance binding.

    Fields:
        source_case_id: Unique case identifier within T00 corpus.
        source_split: Dataset split (train/validation/test).
        source_schema_version: ABI version string of this row.
        source_canonical_bytes: Canonical JSON encoding of the entire row.
        source_row_digest: SHA-256 domain digest of source_canonical_bytes.
        source_provenance_root: Provenance digest from T00 row.
    """
    source_case_id: str
    source_split: str
    source_schema_version: str
    source_canonical_bytes: bytes
    source_row_digest: str
    source_provenance_root: str

    @classmethod
    def from_row(
        cls,
        row: Dict[str, Any],
        source_split: str,
    ) -> "SourceRowIdentityV1":
        """Derive SourceRowIdentityV1 from a raw T00 corpus row.

        All six fields are required. The source digest binds the complete
        canonical source row.
        """
        source_case_id = row.get("case_id")
        if source_case_id is None:
            raise SourceIdentityError("Missing required field: case_id")

        source_schema_version = row.get("abi_version")
        if source_schema_version is None:
            raise SourceIdentityError("Missing required field: abi_version")

        if source_split not in ("train", "validation", "test"):
            raise SourceIdentityError(f"Invalid source_split: {source_split}")

        source_provenance_root = row.get("provenance_digest")
        if source_provenance_root is None:
            raise SourceIdentityError("Missing required field: provenance_digest")

        source_canonical_bytes = canonicalize(row)
        source_row_digest = domain_digest("source", source_canonical_bytes)

        return cls(
            source_case_id=source_case_id,
            source_split=source_split,
            source_schema_version=source_schema_version,
            source_canonical_bytes=source_canonical_bytes,
            source_row_digest=source_row_digest,
            source_provenance_root=source_provenance_root,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (bytes fields converted to hex)."""
        return {
            "source_case_id": self.source_case_id,
            "source_split": self.source_split,
            "source_schema_version": self.source_schema_version,
            "source_canonical_bytes": self.source_canonical_bytes.hex(),
            "source_row_digest": self.source_row_digest,
            "source_provenance_root": self.source_provenance_root,
        }
