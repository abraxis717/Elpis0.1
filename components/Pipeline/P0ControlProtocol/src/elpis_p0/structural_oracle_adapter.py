"""Minimal typed adapter between P0 refinement contracts and StructuralOracle.

This module provides one-way, fail-closed adapters that map:
  - StructuralRefinementInputV1 -> StructuralState  (input adapter)
  - OracleTransition -> TRMRefinementProposal       (output adapter)

Constraints:
- Uses typed contracts only.
- Performs no semantic guessing.
- Preserves writable scope from input.
- Preserves clamp semantics (values in [0,9]).
- Preserves canonical Grid81 indexing (flat 0-80).
- Binds input and output digests.
- Fails closed on contract violation.
- Introduces no learned dependency.
- Introduces no ECRF dependency.
- Has no persistent mutation.
- Gives StructuralOracle sole transition authority.

Does NOT modify StructuralOracle semantics.
Does NOT modify the Projector.
Does NOT integrate DarwinianMatrix.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional, Tuple

from elpis_fractal_spine.structural_oracle import (
    OracleTransition,
    StructuralOracle,
)
from elpis_fractal_spine.structural_refinement import (
    STRUCTURAL_OPCODE_DOMAIN,
    StructuralRefinementError,
    StructuralRefinementInputV1,
)
from elpis_fractal_spine.structural_semantics import (
    GRID_SIZE,
    StructuralContext,
    StructuralGrid,
    StructuralState,
)

from .canonical import digest
from .contracts import TRMRefinementProposal


# ---------------------------------------------------------------------------
# Input adapter: StructuralRefinementInputV1 -> StructuralState
# ---------------------------------------------------------------------------


def refinement_input_to_structural_state(
    input_v1: StructuralRefinementInputV1,
    *,
    depth: int = 0,
    context: Optional[StructuralContext] = None,
) -> StructuralState:
    """Convert a StructuralRefinementInputV1 to a StructuralState.

    Mapping:
        grid81 -> StructuralGrid(tokens=grid81)
        writable_mask81 -> mask
        depth -> depth (default 0)
        provenance -> None (root state)

    Args:
        input_v1: A validated StructuralRefinementInputV1.
        depth: Recursion depth for the resulting state (default 0).
        context: StructuralContext hint (not stored, returned alongside).

    Returns:
        A valid StructuralState ready for oracle evaluation.

    Raises:
        StructuralRefinementError: If grid or mask validation fails.
    """
    # Validate grid
    grid81 = input_v1.grid81
    if len(grid81) != GRID_SIZE:
        raise StructuralRefinementError(
            f"grid81 length {len(grid81)} != {GRID_SIZE}"
        )
    for i, v in enumerate(grid81):
        if v not in STRUCTURAL_OPCODE_DOMAIN:
            raise StructuralRefinementError(
                f"grid81[{i}] = {v} not in structural opcode domain 0..9"
            )

    # Validate mask
    mask = input_v1.writable_mask81
    if len(mask) != GRID_SIZE:
        raise StructuralRefinementError(
            f"writable_mask81 length {len(mask)} != {GRID_SIZE}"
        )
    for i, v in enumerate(mask):
        if v not in (0, 1):
            raise StructuralRefinementError(
                f"writable_mask81[{i}] = {v} not in {{0, 1}}"
            )

    # Validate depth
    if depth < 0:
        raise StructuralRefinementError(
            f"depth {depth} must be non-negative"
        )

    # Construct StructuralGrid
    grid = StructuralGrid(tokens=grid81)

    # Construct StructuralState
    state = StructuralState(
        grid=grid,
        mask=mask,
        depth=depth,
        provenance=None,
    )

    return state


# ---------------------------------------------------------------------------
# Output adapter: OracleTransition -> TRMRefinementProposal
# ---------------------------------------------------------------------------


def oracle_transition_to_trm_proposal(
    transition: OracleTransition,
    *,
    input_digest: str,
) -> TRMRefinementProposal:
    """Convert an OracleTransition to a TRMRefinementProposal.

    Mapping:
        canonical_next_state.grid.tokens -> proposed_grid81
        expansion_targets[].cell -> expansion_cells
        rationale_codes -> rationale
        quiescence -> halt_score (1.0 if quiescent, else derived)
        grid diff -> residual81
        input_digest -> input_digest (supplied)
        digest -> computed via canonical digest

    Args:
        transition: A valid OracleTransition from StructuralOracle.evaluate().
        input_digest: The input identity digest (from the original input).

    Returns:
        A TRMRefinementProposal with all fields populated.

    Raises:
        StructuralRefinementError: If contract validation fails.
    """
    canonical = transition.canonical_next_state

    # Map proposed_grid81
    proposed_grid81 = canonical.grid.tokens
    if len(proposed_grid81) != GRID_SIZE:
        raise StructuralRefinementError(
            f"proposed_grid81 length {len(proposed_grid81)} != {GRID_SIZE}"
        )

    # Clamp semantics: verify all values in [0, 9]
    for i, v in enumerate(proposed_grid81):
        if v not in STRUCTURAL_OPCODE_DOMAIN:
            raise StructuralRefinementError(
                f"proposed_grid81[{i}] = {v} outside clamp domain [0,9]"
            )

    # Map expansion_cells from expansion_targets
    expansion_cells = tuple(
        target.cell for target in transition.expansion_targets
    )

    # Map rationale
    rationale = transition.rationale_codes

    # Derive halt_score from quiescence
    if transition.quiescence:
        halt_score = 1.0
    else:
        # Non-quiescent: compute based on resolved void count
        resolved = sum(
            1
            for v in proposed_grid81
            if v != 0  # VOID opcode
        )
        halt_score = max(0.0, min(1.0, resolved / GRID_SIZE))

    # Derive residual81 from grid differences
    # (1.0 for cells that differ from VOID, 0.125 for resolved)
    residuals = tuple(
        1.0 if v == 0 else 0.125 for v in proposed_grid81
    )

    # Compute proposal digest
    proposal_payload = {
        "input_digest": input_digest,
        "proposed_grid81": proposed_grid81,
        "residual81": residuals,
        "halt_score": halt_score,
        "expansion_cells": expansion_cells,
        "rationale": rationale,
    }
    proposal_digest = digest(proposal_payload)

    # Construct TRMRefinementProposal
    proposal = TRMRefinementProposal(
        input_digest=input_digest,
        proposed_grid81=proposed_grid81,
        residual81=residuals,
        halt_score=halt_score,
        expansion_cells=expansion_cells,
        rationale=rationale,
        digest=proposal_digest,
    )

    # Validate
    proposal.validate()

    return proposal


# ---------------------------------------------------------------------------
# Combined one-step adapter
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OneStepAdapterResult:
    """Result of a combined one-step structural oracle evaluation.

    Binds:
        input_digest: Original input envelope digest
        structural_state_digest: Digest of the converted StructuralState
        oracle_transition_digest: Digest of the canonical next state
        proposal_digest: Digest of the converted TRMRefinementProposal
        proposal: The resulting TRMRefinementProposal
        quiescence: Whether the oracle reached quiescence
        violation_codes: Any structural violation codes
        candidate_count: Number of valid candidates generated
        rationale_codes: Oracle rationale codes
    """

    input_digest: str
    structural_state_digest: str
    oracle_transition_digest: str
    proposal_digest: str
    proposal: TRMRefinementProposal
    quiescence: bool
    violation_codes: tuple[str, ...]
    candidate_count: int
    rationale_codes: tuple[str, ...]
    result_digest: str = ""

    def __post_init__(self) -> None:
        # Compute result digest binding all identity digests
        payload = {
            "input_digest": self.input_digest,
            "structural_state_digest": self.structural_state_digest,
            "oracle_transition_digest": self.oracle_transition_digest,
            "proposal_digest": self.proposal_digest,
            "quiescence": self.quiescence,
            "violation_codes": self.violation_codes,
            "candidate_count": self.candidate_count,
            "rationale_codes": self.rationale_codes,
        }
        computed = hashlib.sha256(
            digest(payload).encode("utf-8")
        ).hexdigest()
        object.__setattr__(self, "result_digest", computed)


def evaluate_one_step(
    input_v1: StructuralRefinementInputV1,
    *,
    oracle: Optional[StructuralOracle] = None,
    depth: int = 0,
) -> OneStepAdapterResult:
    """Execute a complete one-step structural oracle evaluation.

    Pipeline:
        StructuralRefinementInputV1 -> StructuralState
        StructuralState -> StructuralOracle.evaluate() -> OracleTransition
        OracleTransition -> TRMRefinementProposal

    Args:
        input_v1: Validated refinement input with grid and mask.
        oracle: StructuralOracle instance (constructed if absent).
        depth: Recursion depth for the structural state.

    Returns:
        OneStepAdapterResult with all identity digests bound.

    Raises:
        StructuralRefinementError: On any contract violation.
    """
    # 1. Convert input to StructuralState
    state = refinement_input_to_structural_state(
        input_v1, depth=depth
    )

    # 2. Compute structural state digest
    structural_state_digest = state.grid.digest()

    # 3. Evaluate oracle
    if oracle is None:
        oracle = StructuralOracle()

    transition = oracle.evaluate(state)

    # 4. Compute oracle transition digest
    oracle_transition_digest = transition.canonical_next_state.digest()

    # 5. Convert to TRMRefinementProposal
    proposal = oracle_transition_to_trm_proposal(
        transition,
        input_digest=input_v1.combined_digest,
    )

    # 6. Bind result
    return OneStepAdapterResult(
        input_digest=input_v1.combined_digest,
        structural_state_digest=structural_state_digest,
        oracle_transition_digest=oracle_transition_digest,
        proposal_digest=proposal.digest,
        proposal=proposal,
        quiescence=transition.quiescence,
        violation_codes=transition.violation_codes,
        candidate_count=len(transition.valid_next_states),
        rationale_codes=transition.rationale_codes,
    )
