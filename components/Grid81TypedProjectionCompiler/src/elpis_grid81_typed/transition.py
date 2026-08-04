"""Transition view compiler - T00TransitionViewV1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from elpis_grid81_typed.canonical import canonicalize, domain_digest
from elpis_grid81_typed.errors import TransitionCompilerError


@dataclass(frozen=True)
class T00TransitionViewV1:
    """Transition supervision derived strictly from input -> target delta.

    Fields:
        source_case_id: T00 case identifier.
        source_row_digest: SHA-256 of canonical source row bytes.
        input_grid: 81-cell input state.
        input_mask: 81-cell writable scope mask.
        canonical_target_grid: 81-cell canonical target state.
        delta_kind: NOOP | EDIT derived from |D|.
        target_cell: Cell index (0-80) for EDIT; None for NOOP.
        target_value: Target token (0-9) for EDIT; None for NOOP.
        transition_digest: Domain-separated SHA-256 digest.
    """
    source_case_id: str
    source_row_digest: str
    input_grid: List[int]
    input_mask: List[int]
    canonical_target_grid: List[int]
    delta_kind: str
    target_cell: Optional[int]
    target_value: Optional[int]
    transition_digest: str

    @classmethod
    def compile(
        cls,
        source_case_id: str,
        source_row_digest: str,
        input_grid: List[int],
        input_mask: List[int],
        canonical_target_grid: List[int],
    ) -> "T00TransitionViewV1":
        """Compile a transition view from source row fields.

        Derivation:
            D = {i | input_grid[i] != canonical_target_grid[i]}
            |D| == 0: NOOP, target_cell=None, target_value=None
            |D| == 1: EDIT, target_cell=D[0], target_value=canonical_target_grid[D[0]]
            |D| > 1: REJECT

        Does NOT read expansion_targets, rationale_codes, or quiescence_target.
        """
        # Validate grid lengths
        if len(input_grid) != 81:
            raise TransitionCompilerError(f"input_grid length must be 81, got {len(input_grid)}")
        if len(canonical_target_grid) != 81:
            raise TransitionCompilerError(f"canonical_target_grid length must be 81, got {len(canonical_target_grid)}")
        if len(input_mask) != 81:
            raise TransitionCompilerError(f"input_mask length must be 81, got {len(input_mask)}")

        # Validate token values
        for i, v in enumerate(input_grid):
            if not (0 <= v <= 9):
                raise TransitionCompilerError(f"input_grid[{i}] = {v} not in 0..9")

        for i, v in enumerate(input_mask):
            if v not in (0, 1):
                raise TransitionCompilerError(f"input_mask[{i}] = {v} not in {{0,1}}")

        # Compute delta set
        delta_cells: List[int] = [
            i for i in range(81) if input_grid[i] != canonical_target_grid[i]
        ]
        delta_size = len(delta_cells)

        if delta_size == 0:
            delta_kind = "NOOP"
            target_cell: Optional[int] = None
            target_value: Optional[int] = None
        elif delta_size == 1:
            target_cell = delta_cells[0]
            target_value = canonical_target_grid[target_cell]

            # Validate EDIT constraints
            if input_mask[target_cell] != 1:
                raise TransitionCompilerError(
                    f"EDIT target_cell={target_cell} is not writable (mask=0)"
                )
            if target_value == input_grid[target_cell]:
                raise TransitionCompilerError(
                    f"EDIT target_value={target_value} equals input value at cell {target_cell}"
                )
            if not (0 <= target_value <= 9):
                raise TransitionCompilerError(
                    f"EDIT target_value={target_value} not in 0..9"
                )

            delta_kind = "EDIT"
        else:
            raise TransitionCompilerError(
                f"Transition rejected: |D| = {delta_size} > 1 for case {source_case_id}. "
                f"Delta cells: {delta_cells[:10]}..."
            )

        # Compute transition digest
        transition_payload = canonicalize({
            "delta_kind": delta_kind,
            "input_grid": input_grid,
            "target_cell": target_cell,
            "target_value": target_value,
        })
        transition_digest = domain_digest("transition_view", transition_payload)

        return cls(
            source_case_id=source_case_id,
            source_row_digest=source_row_digest,
            input_grid=list(input_grid),
            input_mask=list(input_mask),
            canonical_target_grid=list(canonical_target_grid),
            delta_kind=delta_kind,
            target_cell=target_cell,
            target_value=target_value,
            transition_digest=transition_digest,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_case_id": self.source_case_id,
            "source_row_digest": self.source_row_digest,
            "input_grid": self.input_grid,
            "input_mask": self.input_mask,
            "canonical_target_grid": self.canonical_target_grid,
            "delta_kind": self.delta_kind,
            "target_cell": self.target_cell,
            "target_value": self.target_value,
            "transition_digest": self.transition_digest,
        }
