"""
GATE 6/7/8 — Structural oracle with deterministic transitions.

Deterministic oracle: O(S_t, C_t) -> Y_t
where S_t is StructuralState, C_t is StructuralContext, Y_t is OracleTransition.

Pure NumPy-compatible. No PyTorch, no model loading, no authority, no Cortex,
no wall clocks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional, Set, Tuple

import numpy as np

from .structural_semantics import (
    ABI_VERSION,
    ALL_OPCODES,
    EXPANSION_OPCODE,
    GRID_SIZE,
    LEGAL_TRANSITIONS,
    SEMANTIC_SPACE,
    TERMINAL_OPCODES,
    StructuralConstraint,
    StructuralContext,
    StructuralGrid,
    StructuralOpcode,
    StructuralState,
    VOID_OPCODE,
)


# ---------------------------------------------------------------------------
# Oracle output types (GATE 6/7)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExpansionTarget:
    """A cell that may undergo structural expansion."""

    cell: int
    rationale_code: str


@dataclass(frozen=True)
class ChildSpecification:
    """Specification for a child refinement (P0.2 seed rule)."""

    parent_cell: int
    seed_grid_digest: str
    seed_rule_id: str = "child_seed.copy_void_cell.v1"


@dataclass(frozen=True)
class FoldExpectation:
    """Expected fold outcome for a child resolution."""

    parent_cell: int
    expected_token: int
    unresolved_expansion: bool
    fold_rule_id: str = "fold.replace_cell.v1"


@dataclass(frozen=True)
class OracleNextState:
    """A single valid next state from the oracle."""

    grid: StructuralGrid
    expansion_targets: Tuple[ExpansionTarget, ...] = ()
    child_specifications: Tuple[ChildSpecification, ...] = ()
    fold_expectations: Tuple[FoldExpectation, ...] = ()
    quiescence: bool = False
    violation_codes: Tuple[str, ...] = ()
    rationale_codes: Tuple[str, ...] = ()

    def digest(self) -> str:
        import hashlib
        raw = self.grid.digest()
        for et in self.expansion_targets:
            raw += f"|ET:{et.cell}:{et.rationale_code}"
        for cs in self.child_specifications:
            raw += f"|CS:{cs.parent_cell}:{cs.seed_grid_digest}"
        raw += f"|Q:{self.quiescence}|V:{','.join(self.violation_codes)}"
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class OracleTransition:
    """
    Y_t = O(S_t, C_t)

    Complete oracle output including all valid next states and the canonical one.
    """

    valid_next_states: Tuple[OracleNextState, ...]
    canonical_next_state: OracleNextState
    quiescence: bool
    violation_codes: Tuple[str, ...]
    rationale_codes: Tuple[str, ...]
    expansion_targets: Tuple[ExpansionTarget, ...]
    child_specifications: Tuple[ChildSpecification, ...]
    fold_expectations: Tuple[FoldExpectation, ...]


# ---------------------------------------------------------------------------
# Oracle core logic (GATE 8 — invariants)
# ---------------------------------------------------------------------------
#
# Invariants:
# 1. Determinism: identical input -> byte-identical output
# 2. Semantic validity: every emitted token in StructuralOpcode
# 3. Write locality: G_{t+1}[i] != G_t[i] implies M_t[i] = 1
# 4. Idempotence at terminal: terminal(S) -> canonical_next = S
# 5. Expansion provenance: every expansion has rationale code
# 6. Fold locality: child fold changes only admitted parent cell
# 7. Constraint preservation: transitions do not increase violations
# 8. Equivariance: O(pi(S)) = pi(O(S)) for admitted symmetries
# ---------------------------------------------------------------------------


class StructuralOracle:
    """
    Deterministic structural oracle for grid81.structural.v1.

    O(S_t, C_t) -> Y_t

    No learned parameters. No model. Pure structural logic.
    """

    def __init__(self, context: Optional[StructuralContext] = None):
        self._context = context or StructuralContext.canonical()

    @property
    def context(self) -> StructuralContext:
        return self._context

    def evaluate(
        self, state: StructuralState
    ) -> OracleTransition:
        """
        Main oracle entry point.

        Returns OracleTransition with valid next states, canonical next state,
        and structural metadata.
        """
        # Check terminal state (invariant 4) - only quiescent if no void AND no expansion
        if state.is_terminal() and not state.grid.void_cells:
            quiescent = OracleNextState(
                grid=state.grid,
                quiescence=True,
                rationale_codes=("REFINEMENT_QUIESCENCE",),
            )
            return OracleTransition(
                valid_next_states=(quiescent,),
                canonical_next_state=quiescent,
                quiescence=True,
                violation_codes=(),
                rationale_codes=("REFINEMENT_QUIESCENCE",),
                expansion_targets=(),
                child_specifications=(),
                fold_expectations=(),
            )

        # Generate candidate next states
        candidates = self._generate_candidates(state)

        if not candidates:
            # No valid transitions — contradiction or invalid state
            fallback = OracleNextState(
                grid=state.grid,
                violation_codes=("NO_VALID_TRANSITION",),
                rationale_codes=("CONTRACTION",),
            )
            return OracleTransition(
                valid_next_states=(fallback,),
                canonical_next_state=fallback,
                quiescence=False,
                violation_codes=("NO_VALID_TRANSITION",),
                rationale_codes=("CONTRACTION",),
                expansion_targets=(),
                child_specifications=(),
                fold_expectations=(),
            )

        # Sort candidates deterministically by digest for canonical selection
        sorted_candidates = sorted(
            candidates, key=lambda c: c.digest()
        )

        canonical = sorted_candidates[0]

        # Collect expansion targets
        expansion_targets = self._find_expansion_targets(state)

        # Build child specifications for expansion cells
        child_specs = self._build_child_specs(state, expansion_targets)

        # Build fold expectations
        fold_expectations = self._build_fold_expectations(state, child_specs)

        # Check constraint violations
        violations = self._check_violations(state, canonical)

        rationale = self._compute_rationale(state, canonical)

        return OracleTransition(
            valid_next_states=tuple(sorted_candidates),
            canonical_next_state=canonical,
            quiescence=canonical.quiescence,
            violation_codes=violations,
            rationale_codes=rationale,
            expansion_targets=tuple(expansion_targets),
            child_specifications=tuple(child_specs),
            fold_expectations=tuple(fold_expectations),
        )

    def _generate_candidates(self, state: StructuralState) -> List[OracleNextState]:
        """Generate all structurally valid next states."""
        candidates = []
        grid = state.grid.tokens
        mask = state.mask

        # Find cells that can change
        changeable = []
        for i in range(GRID_SIZE):
            if mask[i] == 0:
                continue
            current = grid[i]
            legal = LEGAL_TRANSITIONS.get(current, frozenset())
            new_values = [v for v in sorted(legal) if v != current]
            for v in new_values:
                changeable.append((i, current, v))

        if not changeable:
            # Grid is stable — return itself as only candidate
            return [OracleNextState(
                grid=state.grid,
                quiescence=True,
                rationale_codes=("NO_CHANGE_POSSIBLE",),
            )]

        # Generate single-cell refinement candidates (write locality)
        for i, old_val, new_val in changeable:
            new_tokens = list(grid)
            new_tokens[i] = new_val
            new_grid = StructuralGrid(tokens=tuple(new_tokens))

            rationale = self._cell_refinement_rationale(i, old_val, new_val)
            expansion_targets = []
            if new_val == EXPANSION_OPCODE:
                expansion_targets.append(
                    ExpansionTarget(cell=i, rationale_code="DECOMPOSITION")
                )

            candidates.append(OracleNextState(
                grid=new_grid,
                expansion_targets=tuple(expansion_targets),
                rationale_codes=(rationale,),
            ))

        return candidates

    def _cell_refinement_rationale(
        self, cell: int, old_val: int, new_val: int
    ) -> str:
        """Determine the rationale code for a cell refinement."""
        if old_val == VOID_OPCODE:
            if new_val == EXPANSION_OPCODE:
                return "VOID_EXPANSION"
            return "VOID_RESOLUTION"
        elif old_val == EXPANSION_OPCODE:
            if new_val == VOID_OPCODE:
                return "EXPANSION_VOID_FOLD"
            return "EXPANSION_TERMINAL_RESOLUTION"
        elif old_val in TERMINAL_OPCODES and new_val == EXPANSION_OPCODE:
            return "TERMINAL_DECOMPOSITION"
        return f"CELL_{cell}_REFINEMENT"

    def _find_expansion_targets(
        self, state: StructuralState
    ) -> List[ExpansionTarget]:
        """Find cells that are expansion-bearing."""
        targets = []
        for i, t in enumerate(state.grid.tokens):
            if t == EXPANSION_OPCODE:
                targets.append(
                    ExpansionTarget(
                        cell=i,
                        rationale_code="ACTIVE_EXPANSION"
                    )
                )
        return targets

    def _build_child_specs(
        self,
        state: StructuralState,
        expansion_targets: List[ExpansionTarget],
    ) -> List[ChildSpecification]:
        """Build child specifications for each expansion cell."""
        specs = []
        for target in expansion_targets:
            # P0.2 seed rule: copy parent grid, set chosen cell to VOID
            import hashlib
            seed_grid = list(state.grid.tokens)
            seed_grid[target.cell] = VOID_OPCODE
            seed_digest = hashlib.sha256(
                ",".join(str(t) for t in seed_grid).encode()
            ).hexdigest()
            specs.append(ChildSpecification(
                parent_cell=target.cell,
                seed_grid_digest=seed_digest,
            ))
        return specs

    def _build_fold_expectations(
        self,
        state: StructuralState,
        child_specs: List[ChildSpecification],
    ) -> List[FoldExpectation]:
        """Build fold expectations for each child specification."""
        expectations = []
        for spec in child_specs:
            # Default fold expectation: terminal token resolves,
            # expansion token remains unresolved (VOID)
            expectations.append(FoldExpectation(
                parent_cell=spec.parent_cell,
                expected_token=VOID_OPCODE,  # conservative default
                unresolved_expansion=True,
            ))
        return expectations

    def _check_violations(
        self, state: StructuralState, candidate: OracleNextState
    ) -> Tuple[str, ...]:
        """Check structural constraint violations."""
        violations = []

        # Check write locality
        for i in range(GRID_SIZE):
            if state.grid.tokens[i] != candidate.grid.tokens[i]:
                if not state.is_cell_writable(i):
                    violations.append(f"ILLEGAL_WRITE:{i}")

        # Check token validity
        for i, t in enumerate(candidate.grid.tokens):
            if t not in ALL_OPCODES:
                violations.append(f"INVALID_TOKEN:{i}:{t}")

        # Check constraint scope violations
        for constraint in self._context.constraints:
            for cell in constraint.scope:
                if cell < len(candidate.grid.tokens):
                    # Simplified: check if the cell transition is legal
                    old_t = state.grid.tokens[cell]
                    new_t = candidate.grid.tokens[cell]
                    if old_t != new_t and new_t not in LEGAL_TRANSITIONS.get(
                        old_t, frozenset()
                    ):
                        violations.append(
                            f"CONSTRAINT_VIOLATION:{constraint.constraint_id}"
                        )

        return tuple(sorted(set(violations)))

    def _compute_rationale(
        self, state: StructuralState, candidate: OracleNextState
    ) -> Tuple[str, ...]:
        """Compute rationale codes for the transition."""
        rationale = set()

        if candidate.quiescence:
            rationale.add("REFINEMENT_QUIESCENCE")

        for i in range(GRID_SIZE):
            old_t = state.grid.tokens[i]
            new_t = candidate.grid.tokens[i]
            if old_t != new_t:
                rationale.add(
                    self._cell_refinement_rationale(i, old_t, new_t)
                )

        if not rationale:
            rationale.add("NO_CHANGE")

        return tuple(sorted(rationale))


# ---------------------------------------------------------------------------
# Symmetry operations (GATE 8 equivariance)
# ---------------------------------------------------------------------------
#
# Structural symmetries derived from the grid81 layout:
# - 9x9 grid rotations and reflections (Sudoku box symmetries NOT imported
#   unless structural contract defines them)
# - Permutation of terminal opcodes within semantic equivalence classes
# ---------------------------------------------------------------------------


def _grid_9x9_indices() -> List[Tuple[int, int]]:
    """Map flat index to 9x9 coordinates."""
    return [(i // 9, i % 9) for i in range(GRID_SIZE)]


def _rotate_90(grid: StructuralGrid) -> StructuralGrid:
    """Rotate 9x9 grid 90 degrees clockwise."""
    tokens = list(grid.tokens)
    new_tokens = [0] * GRID_SIZE
    for r in range(9):
        for c in range(9):
            old_idx = r * 9 + c
            new_r = c
            new_c = 8 - r
            new_idx = new_r * 9 + new_c
            new_tokens[new_idx] = tokens[old_idx]
    return StructuralGrid(tokens=tuple(new_tokens))


def _reflect_horizontal(grid: StructuralGrid) -> StructuralGrid:
    """Reflect 9x9 grid horizontally."""
    tokens = list(grid.tokens)
    new_tokens = [0] * GRID_SIZE
    for r in range(9):
        for c in range(9):
            old_idx = r * 9 + c
            new_idx = r * 9 + (8 - c)
            new_tokens[new_idx] = tokens[old_idx]
    return StructuralGrid(tokens=tuple(new_tokens))


def _canonical_symmetry_digest(grid: StructuralGrid) -> str:
    """
    Compute canonical isomorphism digest:
    D_iso(S) = min over admitted symmetries pi of H(pi(S))
    """
    import hashlib

    symmetries = [grid]
    g = grid
    for _ in range(3):
        g = _rotate_90(g)
        symmetries.append(g)

    # Add reflections
    g_ref = _reflect_horizontal(grid)
    symmetries.append(g_ref)
    for _ in range(3):
        g_ref = _rotate_90(g_ref)
        symmetries.append(g_ref)

    # Compute digests and find minimum
    digests = []
    for s in symmetries:
        d = hashlib.sha256(
            ",".join(str(t) for t in s.tokens).encode()
        ).hexdigest()
        digests.append(d)

    return min(digests)


# ---------------------------------------------------------------------------
# Oracle validator (invariant checker)
# ---------------------------------------------------------------------------


class OracleValidator:
    """Validates oracle invariants (GATE 8)."""

    def validate_determinism(
        self, oracle: StructuralOracle, state: StructuralState, iterations: int = 3
    ) -> bool:
        """Check that oracle produces byte-identical output for same input."""
        results = []
        for _ in range(iterations):
            trans = oracle.evaluate(state)
            results.append(trans.canonical_next_state.digest())
        return len(set(results)) == 1

    def validate_write_locality(
        self, state: StructuralState, transition: OracleTransition
    ) -> bool:
        """Check that G_{t+1}[i] != G_t[i] implies M_t[i] = 1."""
        canonical = transition.canonical_next_state
        for i in range(GRID_SIZE):
            if state.grid.tokens[i] != canonical.grid.tokens[i]:
                if not state.is_cell_writable(i):
                    return False
        return True

    def validate_terminal_idempotence(
        self, oracle: StructuralOracle, state: StructuralState
    ) -> bool:
        """Check that terminal(S) -> canonical_next = S."""
        if not state.is_terminal():
            return True  # only applies to terminal states
        trans = oracle.evaluate(state)
        return trans.canonical_next_state.grid.digest() == state.grid.digest()

    def validate_semantic_validity(
        self, transition: OracleTransition
    ) -> bool:
        """Check every emitted token belongs to StructuralOpcode."""
        for ns in transition.valid_next_states:
            for t in ns.grid.tokens:
                if t not in ALL_OPCODES:
                    return False
        return True

    def validate_equivariance(
        self, oracle: StructuralOracle, state: StructuralState
    ) -> bool:
        """Check O(pi(S)) = pi(O(S)) for rotation symmetry."""
        trans = oracle.evaluate(state)
        rotated_state_grid = _rotate_90(state.grid)
        rotated_state = StructuralState(
            grid=rotated_state_grid,
            mask=state.mask,
            depth=state.depth,
            provenance=state.provenance,
        )
        trans_rotated = oracle.evaluate(rotated_state)

        # The canonical next state of the rotated should be the rotation
        # of the canonical next state
        expected_rotated = _rotate_90(trans.canonical_next_state.grid)
        actual_rotated = trans_rotated.canonical_next_state.grid

        return expected_rotated.digest() == actual_rotated.digest()
