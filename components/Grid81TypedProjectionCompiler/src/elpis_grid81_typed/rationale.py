"""Rationale view compiler - T00RationaleViewV1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from elpis_grid81_typed.canonical import canonicalize, domain_digest
from elpis_grid81_typed.errors import RationaleCompilerError


@dataclass(frozen=True)
class T00RationaleViewV1:
    """Diagnostic rationale metadata bound to transition supervision.

    Fields:
        source_case_id: T00 case identifier.
        source_row_digest: SHA-256 of canonical source row bytes.
        input_grid: 81-cell input state.
        canonical_target_grid: 81-cell canonical target state.
        transition_delta: List of changed cells and delta size.
        rationale_codes: Sorted list of diagnostic rationale code strings.
        rationale_view_digest: Domain-separated SHA-256 digest.
    """
    source_case_id: str
    source_row_digest: str
    input_grid: List[int]
    canonical_target_grid: List[int]
    transition_delta: Dict[str, Any]
    rationale_codes: List[str]
    rationale_view_digest: str

    @classmethod
    def compile(
        cls,
        source_case_id: str,
        source_row_digest: str,
        input_grid: List[int],
        canonical_target_grid: List[int],
        rationale_codes: List[str],
    ) -> "T00RationaleViewV1":
        """Compile rationale view from source row fields.

        Rationale is diagnostic only. It does NOT determine:
            - target_cell, target_value, writable scope, quiescence, expansion membership

        Rationale codes are canonicalized as a duplicate-free sorted collection
        (G4.0A.3 does not declare ordering as semantic).
        """
        if len(input_grid) != 81:
            raise RationaleCompilerError(f"input_grid length must be 81, got {len(input_grid)}")
        if len(canonical_target_grid) != 81:
            raise RationaleCompilerError(f"canonical_target_grid length must be 81, got {len(canonical_target_grid)}")

        # Compute transition delta
        delta_cells = sorted([
            i for i in range(81) if input_grid[i] != canonical_target_grid[i]
        ])
        transition_delta = {
            "delta_cells": delta_cells,
            "delta_size": len(delta_cells),
        }

        # Canonicalize rationale codes: deduplicate and sort
        unique_codes = sorted(set(rationale_codes))

        # Compute rationale view digest
        rationale_payload = canonicalize({
            "input_grid": input_grid,
            "canonical_target_grid": canonical_target_grid,
            "rationale_codes": unique_codes,
        })
        rationale_view_digest = domain_digest("rationale_view", rationale_payload)

        return cls(
            source_case_id=source_case_id,
            source_row_digest=source_row_digest,
            input_grid=list(input_grid),
            canonical_target_grid=list(canonical_target_grid),
            transition_delta=transition_delta,
            rationale_codes=unique_codes,
            rationale_view_digest=rationale_view_digest,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_case_id": self.source_case_id,
            "source_row_digest": self.source_row_digest,
            "input_grid": self.input_grid,
            "canonical_target_grid": self.canonical_target_grid,
            "transition_delta": self.transition_delta,
            "rationale_codes": self.rationale_codes,
            "rationale_view_digest": self.rationale_view_digest,
        }
