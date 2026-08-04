"""Quiescence view compiler - T00QuiescenceViewV1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from elpis_grid81_typed.canonical import canonicalize, domain_digest
from elpis_grid81_typed.errors import QuiescenceCompilerError


@dataclass(frozen=True)
class T00QuiescenceViewV1:
    """Quiescence classification derived from input state token composition.

    Fields:
        source_case_id: T00 case identifier.
        source_row_digest: SHA-256 of canonical source row bytes.
        input_grid: 81-cell input state.
        derived_quiescence: True if no token 0 and no token 6 in input_grid.
        stored_quiescence: Original stored quiescence_target value.
        lineage_status: 'AGREED' or 'STALE_STORED_LABEL'.
        quiescence_view_digest: Domain-separated SHA-256 digest.
    """
    source_case_id: str
    source_row_digest: str
    input_grid: List[int]
    derived_quiescence: bool
    stored_quiescence: bool
    lineage_status: str
    quiescence_view_digest: str

    @classmethod
    def compile(
        cls,
        source_case_id: str,
        source_row_digest: str,
        input_grid: List[int],
        stored_quiescence: bool,
    ) -> "T00QuiescenceViewV1":
        """Compile quiescence view from input_grid.

        Derivation:
            derived_quiescence = (no token 0 in input_grid) and (no token 6 in input_grid)

        Lineage law:
            derived_quiescence is authoritative
            stored_quiescence is retained as provenance evidence
            mismatches get lineage_status = STALE_STORED_LABEL
        """
        if len(input_grid) != 81:
            raise QuiescenceCompilerError(f"input_grid length must be 81, got {len(input_grid)}")

        # Derive quiescence from token composition
        has_void = any(cell == 0 for cell in input_grid)
        has_expansion = any(cell == 6 for cell in input_grid)
        derived_quiescence = not has_void and not has_expansion

        # Determine lineage status
        if derived_quiescence == stored_quiescence:
            lineage_status = "AGREED"
        else:
            lineage_status = "STALE_STORED_LABEL"

        # The authoritative label is the derived value
        quiescence_label = derived_quiescence

        # Compute quiescence view digest
        quiescence_payload = canonicalize({
            "input_grid": input_grid,
            "quiescence_label": quiescence_label,
        })
        quiescence_view_digest = domain_digest("quiescence_view", quiescence_payload)

        return cls(
            source_case_id=source_case_id,
            source_row_digest=source_row_digest,
            input_grid=list(input_grid),
            derived_quiescence=derived_quiescence,
            stored_quiescence=stored_quiescence,
            lineage_status=lineage_status,
            quiescence_view_digest=quiescence_view_digest,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_case_id": self.source_case_id,
            "source_row_digest": self.source_row_digest,
            "input_grid": self.input_grid,
            "derived_quiescence": self.derived_quiescence,
            "stored_quiescence": self.stored_quiescence,
            "lineage_status": self.lineage_status,
            "quiescence_view_digest": self.quiescence_view_digest,
        }
