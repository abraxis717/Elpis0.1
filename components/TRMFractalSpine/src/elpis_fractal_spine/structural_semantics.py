"""
GATE 5/6 — Structural semantic census and formal structural state.

Deterministic, frozen definitions for the grid81.structural.v1 vocabulary.
No PyTorch. No model loading. No authority. No Cortex. No wall clocks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import FrozenSet, List, Optional, Set, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# StructuralOpcode — exact integer enum from census (GATE 5)
# ---------------------------------------------------------------------------
#
# Census authority: P0.2 expansion.py defines EXPANSION_TOKEN=6, VOID_TOKEN=0.
# P0.2 expansion_schema.json defines fold/seed rules referencing these tokens.
# semantic_spaces.py validates grid81 tokens in 0..9.
# spine_math.py defines WrapperParadigm.STRUCTURAL_OPCODE as the paradigm
#   for native_task=grid81.structural.v1.
#
# Token 6 = EXPANSION only because the controller-owned P0.2 structural
# contract defines it that way. Sudoku digit semantics are excluded.
# ---------------------------------------------------------------------------


class StructuralOpcode(IntEnum):
    """Canonical structural vocabulary for grid81.structural.v1."""

    VOID = 0
    TERMINAL_A = 1
    TERMINAL_B = 2
    TERMINAL_C = 3
    TERMINAL_D = 4
    TERMINAL_E = 5
    EXPANSION = 6
    TERMINAL_F = 7
    TERMINAL_G = 8
    TERMINAL_H = 9

    @property
    def is_terminal(self) -> bool:
        return self not in (StructuralOpcode.VOID, StructuralOpcode.EXPANSION)

    @property
    def is_expansion_bearing(self) -> bool:
        return self == StructuralOpcode.EXPANSION

    @property
    def is_void(self) -> bool:
        return self == StructuralOpcode.VOID

    @property
    def is_refinement_quiescent(self) -> bool:
        """Cell cannot be further refined (terminal or void in quiescent grid)."""
        return self != StructuralOpcode.EXPANSION


# Derived constants
ALL_OPCODES = frozenset(StructuralOpcode)
TERMINAL_OPCODES = frozenset(o for o in StructuralOpcode if o.is_terminal)
VOID_OPCODE = StructuralOpcode.VOID
EXPANSION_OPCODE = StructuralOpcode.EXPANSION

SEMANTIC_SPACE = "grid81.structural.v1"
ABI_VERSION = "t00.structural.v1"
GRID_SIZE = 81
VOCABULARY_SIZE = 10

# ---------------------------------------------------------------------------
# Token transition rules (GATE 5 census resolution)
# ---------------------------------------------------------------------------

# Legal producers: who may produce this token in a structural context
LEGAL_PRODUCERS: dict[int, FrozenSet[str]] = {
    0: frozenset({"oracle", "controller_fold", "child_seed"}),
    1: frozenset({"oracle", "model_structural_head"}),
    2: frozenset({"oracle", "model_structural_head"}),
    3: frozenset({"oracle", "model_structural_head"}),
    4: frozenset({"oracle", "model_structural_head"}),
    5: frozenset({"oracle", "model_structural_head"}),
    6: frozenset({"oracle", "model_structural_head"}),
    7: frozenset({"oracle", "model_structural_head"}),
    8: frozenset({"oracle", "model_structural_head"}),
    9: frozenset({"oracle", "model_structural_head"}),
}

# Legal consumers: who may consume this token
LEGAL_CONSUMERS: dict[int, FrozenSet[str]] = {
    0: frozenset({"oracle", "controller", "child_trm"}),
    1: frozenset({"oracle", "controller", "model_structural_head"}),
    2: frozenset({"oracle", "controller", "model_structural_head"}),
    3: frozenset({"oracle", "controller", "model_structural_head"}),
    4: frozenset({"oracle", "controller", "model_structural_head"}),
    5: frozenset({"oracle", "controller", "model_structural_head"}),
    6: frozenset({"oracle", "controller", "expansion_admission"}),
    7: frozenset({"oracle", "controller", "model_structural_head"}),
    8: frozenset({"oracle", "controller", "model_structural_head"}),
    9: frozenset({"oracle", "controller", "model_structural_head"}),
}

# Legal transitions: from_token -> set of to_tokens
# VOID can become anything (unresolved placeholder)
# TERMINAL can stay terminal or become EXPANSION (decomposition)
# EXPANSION can resolve to terminal or VOID (fold)
LEGAL_TRANSITIONS: dict[int, FrozenSet[int]] = {
    0: frozenset(range(10)),  # VOID -> anything
    1: frozenset({1, 6}),     # TERMINAL_A -> itself or EXPANSION
    2: frozenset({2, 6}),
    3: frozenset({3, 6}),
    4: frozenset({4, 6}),
    5: frozenset({5, 6}),
    6: frozenset({0, 1, 2, 3, 4, 5, 7, 8, 9}),  # EXPANSION -> terminal or VOID
    7: frozenset({7, 6}),
    8: frozenset({8, 6}),
    9: frozenset({9, 6}),
}

# ---------------------------------------------------------------------------
# Frozen structural state (GATE 6)
# ---------------------------------------------------------------------------
# S_t = (G_t, M_t, D_t, P_t)
# G_t: Grid81 in {0,...,9}^81
# M_t: writable-cell mask in {0,1}^81
# D_t: recursion depth (non-negative integer)
# P_t: immutable parent/fold provenance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParentProvenance:
    """Immutable parent/fold provenance for a structural state."""

    parent_grid_digest: str
    parent_expansion_cell: Optional[int]
    fold_rule_id: str
    depth: int

    def __post_init__(self):
        if self.depth < 0:
            raise ValueError(f"depth {self.depth} must be non-negative")
        if self.parent_expansion_cell is not None and (
            self.parent_expansion_cell < 0 or self.parent_expansion_cell >= GRID_SIZE
        ):
            raise ValueError(
                f"parent_expansion_cell {self.parent_expansion_cell} out of range"
            )


@dataclass(frozen=True)
class StructuralGrid:
    """Frozen 81-cell structural grid with validation."""

    tokens: Tuple[int, ...]

    def __post_init__(self):
        if len(self.tokens) != GRID_SIZE:
            raise ValueError(
                f"Grid tokens length {len(self.tokens)} != {GRID_SIZE}"
            )
        for i, t in enumerate(self.tokens):
            if not isinstance(t, int) or t not in ALL_OPCODES:
                raise ValueError(f"Cell {i}: token {t} not in StructuralOpcode")

    @property
    def as_array(self) -> np.ndarray:
        return np.array(self.tokens, dtype=np.int64)

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "StructuralGrid":
        if arr.shape != (GRID_SIZE,):
            raise ValueError(f"Array shape {arr.shape} != ({GRID_SIZE},)")
        tokens = tuple(int(x) for x in arr.ravel())
        return cls(tokens=tokens)

    @property
    def expansion_cells(self) -> Tuple[int, ...]:
        return tuple(
            i for i, t in enumerate(self.tokens)
            if t == EXPANSION_OPCODE
        )

    @property
    def void_cells(self) -> Tuple[int, ...]:
        return tuple(
            i for i, t in enumerate(self.tokens)
            if t == VOID_OPCODE
        )

    @property
    def terminal_cells(self) -> Tuple[int, ...]:
        return tuple(
            i for i, t in enumerate(self.tokens)
            if t in TERMINAL_OPCODES
        )

    def is_refinement_quiescent(self) -> bool:
        """No expansion cells remain — grid is stable."""
        return len(self.expansion_cells) == 0

    def cell(self, i: int) -> int:
        return self.tokens[i]

    def digest(self) -> str:
        import hashlib
        return hashlib.sha256(
            ",".join(str(t) for t in self.tokens).encode()
        ).hexdigest()


@dataclass(frozen=True)
class StructuralConstraint:
    """A single structural constraint declared in the context."""

    constraint_id: str
    scope: FrozenSet[int]  # cell indices this constraint applies to
    rule: str              # human-readable rule description
    violation_code: Optional[str] = None

    def __post_init__(self):
        for c in self.scope:
            if c < 0 or c >= GRID_SIZE:
                raise ValueError(
                    f"Constraint scope cell {c} out of range [0, {GRID_SIZE})"
                )


@dataclass(frozen=True)
class StructuralContext:
    """
    Immutable context C_t containing only declared structural constraints.

    No authority, no account internals, no Cortex, no telemetry, no clocks,
    no model identity.
    """

    semantic_space: str
    abi_version: str
    constraints: Tuple[StructuralConstraint, ...] = ()
    max_depth: int = 3
    is_adversarial: bool = False

    def __post_init__(self):
        if self.semantic_space != SEMANTIC_SPACE:
            raise ValueError(
                f"semantic_space '{self.semantic_space}' != '{SEMANTIC_SPACE}'"
            )
        if self.max_depth < 0:
            raise ValueError(f"max_depth {self.max_depth} must be non-negative")

    @classmethod
    def canonical(cls) -> "StructuralContext":
        """Return a default canonical context."""
        return cls(
            semantic_space=SEMANTIC_SPACE,
            abi_version=ABI_VERSION,
            constraints=(),
            max_depth=3,
        )


@dataclass(frozen=True)
class StructuralState:
    """
    S_t = (G_t, M_t, D_t, P_t)

    Formal structural state per GATE 6.
    """

    grid: StructuralGrid
    mask: Tuple[int, ...]  # 0 or 1 per cell, controller-owned writable mask
    depth: int
    provenance: Optional[ParentProvenance]

    def __post_init__(self):
        if len(self.mask) != GRID_SIZE:
            raise ValueError(
                f"Mask length {len(self.mask)} != {GRID_SIZE}"
            )
        for i, m in enumerate(self.mask):
            if m not in (0, 1):
                raise ValueError(f"Mask cell {i}: value {m} not in {{0, 1}}")
        if self.depth < 0:
            raise ValueError(f"depth {self.depth} must be non-negative")

    @property
    def as_array(self) -> np.ndarray:
        return self.grid.as_array

    @property
    def mask_array(self) -> np.ndarray:
        return np.array(self.mask, dtype=np.int64)

    @classmethod
    def root(
        cls,
        grid: StructuralGrid,
        mask: Optional[Tuple[int, ...]] = None,
    ) -> "StructuralState":
        """Create a root state with no provenance."""
        if mask is None:
            mask = (1,) * GRID_SIZE  # all cells writable by default
        return cls(
            grid=grid,
            mask=mask,
            depth=0,
            provenance=None,
        )

    def is_terminal(self) -> bool:
        """Grid has no expansion cells and all cells are resolved."""
        return self.grid.is_refinement_quiescent()

    def writable_cells(self) -> Tuple[int, ...]:
        return tuple(i for i, m in enumerate(self.mask) if m == 1)

    def is_cell_writable(self, i: int) -> bool:
        if i < 0 or i >= GRID_SIZE:
            return False
        return self.mask[i] == 1
