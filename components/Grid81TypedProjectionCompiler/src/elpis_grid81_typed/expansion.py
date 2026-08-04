"""Expansion-locus view compiler - T00ExpansionLocusViewV1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from elpis_grid81_typed.canonical import canonicalize, domain_digest
from elpis_grid81_typed.errors import ExpansionCompilerError


@dataclass(frozen=True)
class T00ExpansionLocusViewV1:
    """Expansion locus derived exclusively from input_grid token-6 membership.

    Fields:
        source_case_id: T00 case identifier.
        source_row_digest: SHA-256 of canonical source row bytes.
        input_grid: 81-cell input state.
        expansion_locus_mask81: Binary mask, 1 iff input_grid[i] == 6.
        expansion_cells: Sorted list of cell indices where mask == 1.
        expansion_view_digest: Domain-separated SHA-256 digest.
    """
    source_case_id: str
    source_row_digest: str
    input_grid: List[int]
    expansion_locus_mask81: List[int]
    expansion_cells: List[int]
    expansion_view_digest: str

    @classmethod
    def compile(
        cls,
        source_case_id: str,
        source_row_digest: str,
        input_grid: List[int],
        stored_expansion_targets: Any = None,
    ) -> "T00ExpansionLocusViewV1":
        """Compile expansion locus view from input_grid.

        Derivation:
            expansion_locus_mask81[i] = 1 iff input_grid[i] == 6
            expansion_cells = sorted indices where mask == 1

        Stored expansion_targets is verification evidence only.
        """
        if len(input_grid) != 81:
            raise ExpansionCompilerError(f"input_grid length must be 81, got {len(input_grid)}")

        # Derive expansion mask and cells from token-6 membership
        expansion_locus_mask81: List[int] = [1 if cell == 6 else 0 for cell in input_grid]
        expansion_cells: List[int] = sorted(
            [i for i, v in enumerate(expansion_locus_mask81) if v == 1]
        )

        # Verify against stored targets if provided
        if stored_expansion_targets is not None:
            stored_cells = sorted(
                [t["cell"] for t in stored_expansion_targets if isinstance(t, dict) and "cell" in t]
            )
            if stored_cells != expansion_cells:
                raise ExpansionCompilerError(
                    f"Expansion mismatch for {source_case_id}: "
                    f"derived={expansion_cells[:5]}..., stored={stored_cells[:5]}..."
                )

        # Compute expansion view digest
        expansion_payload = canonicalize({
            "expansion_cells": expansion_cells,
            "input_grid": input_grid,
        })
        expansion_view_digest = domain_digest("expansion_view", expansion_payload)

        return cls(
            source_case_id=source_case_id,
            source_row_digest=source_row_digest,
            input_grid=list(input_grid),
            expansion_locus_mask81=expansion_locus_mask81,
            expansion_cells=expansion_cells,
            expansion_view_digest=expansion_view_digest,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_case_id": self.source_case_id,
            "source_row_digest": self.source_row_digest,
            "input_grid": self.input_grid,
            "expansion_locus_mask81": self.expansion_locus_mask81,
            "expansion_cells": self.expansion_cells,
            "expansion_view_digest": self.expansion_view_digest,
        }
