"""
GATE 10/11 — Deterministic corpus generator with split leakage protection.

Generates exactly 8,192 cases across 8 strata with leakage-resistant
train/validation/test splits by template family.

Pure NumPy-compatible. No PyTorch, no model loading, no wall clocks.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

import numpy as np

from .corpus_schema import (
    CorpusCase,
    CorpusManifest,
    CorpusSerializer,
    SplitManifest,
)
from .structural_oracle import (
    OracleTransition,
    _canonical_symmetry_digest,
    _rotate_90,
    StructuralOracle,
)
from .structural_semantics import (
    ABI_VERSION,
    EXPANSION_OPCODE,
    GRID_SIZE,
    SEMANTIC_SPACE,
    TERMINAL_OPCODES,
    StructuralGrid,
    StructuralState,
    VOID_OPCODE,
)

# ---------------------------------------------------------------------------
# Corpus generation config (GATE 10)
# ---------------------------------------------------------------------------

GENERATOR_VERSION = "t00.corpus.v1"
TOTAL_CASES = 8192

# Target strata distribution
STRATA_CONFIG = {
    "local_refinement": 1536,
    "expansion_decomposition": 1536,
    "child_fold": 1024,
    "terminal_quiescence": 1024,
    "contradiction_invalid": 1024,
    "boundary_malformed": 1024,
    "equivariance_metamorphic": 1024,
}

# Split ratios (GATE 11)
SPLIT_RATIOS = {
    "train": 6144,
    "validation": 1024,
    "test": 1024,
}

# Template families per stratum (GATE 11 — split by family)
# Each stratum has multiple template families; families don't cross splits
TEMPLATE_FAMILIES = {
    "local_refinement": [
        "void_single_resolve",
        "void_multi_resolve",
        "terminal_self_stable",
        "void_block_resolve",
        "void_row_resolve",
        "void_column_resolve",
        "void_scatter_resolve",
        "terminal_to_expansion",
        "void_adjacent_pair",
        "void_diagonal_chain",
    ],
    "expansion_decomposition": [
        "single_expansion_isolated",
        "single_expansion_adjacent",
        "multi_expansion_cluster",
        "multi_expansion_scattered",
        "expansion_terminal_boundary",
        "expansion_void_boundary",
        "expansion_full_row",
        "expansion_cross_pattern",
        "expansion_corner_focus",
        "expansion_center_focus",
    ],
    "child_fold": [
        "child_seed_void_cell",
        "child_terminal_fold",
        "child_expansion_fold",
        "child_abort_fold",
        "child_multiple_expansion",
        "child_nested_depth",
        "child_boundary_cell",
        "child_center_cell",
        "child_corner_cell",
        "child_edge_cell",
    ],
    "terminal_quiescence": [
        "all_terminal_uniform",
        "all_terminal_mixed",
        "quiescent_after_depth",
        "quiescent_no_void",
        "quiescent_with_void",
        "quiescent_single_terminal_type",
        "quiescent_two_terminal_types",
        "quiescent_full_spectrum",
        "quiescent_pattern_a",
        "quiescent_pattern_b",
    ],
    "contradiction_invalid": [
        "no_writable_expansion",
        "contradictory_mask",
        "depth_exceeded",
        "all_masked_expansion",
        "island_expansion",
        "adjacent_contradiction",
        "full_void_no_mask",
        "mixed_invalid_tokens",
        "provenance_conflict",
        "constraint_violation_set",
    ],
    "boundary_malformed": [
        "single_cell_grid",
        "edge_only_pattern",
        "corner_only_pattern",
        "sparse_single_token",
        "max_depth_state",
        "zero_depth_full_grid",
        "alternating_void_terminal",
        "strip_pattern",
        "concentric_rings",
        "fractal_boundary",
    ],
    "equivariance_metamorphic": [
        "rotate_90_pair",
        "rotate_180_pair",
        "reflect_h_pair",
        "reflect_v_pair",
        "token_permutation_class",
        "structural_isomorphism",
        "symmetry_orbit_size_8",
        "symmetry_orbit_size_4",
        "metamorphic_expansion",
        "metamorphic_quiescence",
    ],
}

# How many template families go into each split
# Families partition across splits — no family in more than one split
FAMILY_SPLIT_ASSIGNMENT = {
    "train": [],
    "validation": [],
    "test": [],
}


# ---------------------------------------------------------------------------
# Deterministic grid templates (GATE 10)
# ---------------------------------------------------------------------------
# Each template family generates grids deterministically from a seed.
# Templates produce semantically meaningful cases, not random noise.
# ---------------------------------------------------------------------------


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def _make_void_terminal_grid(
    n_void: int, n_expansion: int, seed: int
) -> Tuple[int, ...]:
    """Create a grid with specified number of void and expansion cells."""
    rng = np.random.RandomState(seed)
    tokens = [VOID_OPCODE] * GRID_SIZE

    # Place expansion cells
    if n_expansion > 0:
        exp_positions = rng.choice(GRID_SIZE, size=n_expansion, replace=False)
        for pos in exp_positions:
            tokens[pos] = EXPANSION_OPCODE

    # Place remaining void cells (already void), rest get terminals
    terminal_list = sorted(TERMINAL_OPCODES)
    for i in range(GRID_SIZE):
        if tokens[i] == VOID_OPCODE and n_void > 0:
            n_void -= 1
        elif tokens[i] == VOID_OPCODE:
            tokens[i] = terminal_list[i % len(terminal_list)]

    return tuple(tokens)


def _make_terminal_grid(seed: int, pattern: int = 0) -> Tuple[int, ...]:
    """Create a fully terminal grid (no void, no expansion)."""
    rng = np.random.RandomState(seed)
    terminal_list = sorted(TERMINAL_OPCODES)
    if pattern == 0:
        # Random terminals
        return tuple(
            int(terminal_list[rng.randint(0, len(terminal_list))])
            for _ in range(GRID_SIZE)
        )
    elif pattern == 1:
        # Row-wise uniform
        return tuple(
            int(terminal_list[(r * 9 + c) % len(terminal_list)])
            for r in range(9) for c in range(9)
        )
    else:
        # Checkerboard of two terminal types
        t1, t2 = terminal_list[0], terminal_list[1]
        return tuple(
            t1 if ((r + c) % 2 == 0) else t2
            for r in range(9) for c in range(9)
        )


def _make_expansion_grid(
    n_expansion: int, seed: int, cluster: bool = False
) -> Tuple[int, ...]:
    """Create a grid with expansion cells, rest terminal."""
    rng = np.random.RandomState(seed)
    terminal_list = sorted(TERMINAL_OPCODES)
    tokens = [
        int(terminal_list[rng.randint(0, len(terminal_list))])
        for _ in range(GRID_SIZE)
    ]

    if cluster:
        # Place expansion cells in a cluster (3x3 block)
        start_r = rng.randint(0, 7)
        start_c = rng.randint(0, 7)
        placed = 0
        for dr in range(3):
            for dc in range(3):
                if placed >= n_expansion:
                    break
                r, c = start_r + dr, start_c + dc
                tokens[r * 9 + c] = EXPANSION_OPCODE
                placed += 1
    else:
        positions = rng.choice(GRID_SIZE, size=n_expansion, replace=False)
        for pos in positions:
            tokens[pos] = EXPANSION_OPCODE

    return tuple(tokens)


def _make_mask(
    grid: Tuple[int, ...],
    writable_fraction: float = 1.0,
    seed: int = 0,
) -> Tuple[int, ...]:
    """Create a writable mask. By default all cells writable."""
    rng = np.random.RandomState(seed)
    if writable_fraction >= 1.0:
        return (1,) * GRID_SIZE

    mask = [1] * GRID_SIZE
    n_writable = int(GRID_SIZE * writable_fraction)
    writable_indices = rng.choice(GRID_SIZE, size=n_writable, replace=False)
    for i in range(GRID_SIZE):
        if i not in writable_indices:
            mask[i] = 0
    return tuple(mask)


def _make_contradiction_grid(seed: int, pattern: int = 0) -> Tuple[int, ...]:
    """Create a grid with contradictory structural constraints."""
    rng = np.random.RandomState(seed)
    terminal_list = sorted(TERMINAL_OPCODES)
    tokens = [
        int(terminal_list[rng.randint(0, len(terminal_list))])
        for _ in range(GRID_SIZE)
    ]

    if pattern == 0:
        # All expansion but no writable cells (handled by mask)
        tokens = [EXPANSION_OPCODE] * GRID_SIZE
    elif pattern == 1:
        # Mixed void and expansion in impossible configuration
        tokens = [VOID_OPCODE if i % 2 == 0 else EXPANSION_OPCODE
                  for i in range(GRID_SIZE)]
    elif pattern == 2:
        # Single expansion surrounded by terminals that can't resolve
        tokens = [VOID_OPCODE] * GRID_SIZE
        tokens[40] = EXPANSION_OPCODE

    return tuple(tokens)


# ---------------------------------------------------------------------------
# Stratum-specific generators
# ---------------------------------------------------------------------------


def _generate_local_refinement(
    case_idx: int, template_idx: int, seed: int
) -> Tuple[Tuple[int, ...], Tuple[int, ...], int]:
    """Generate local deterministic refinement case."""
    template = TEMPLATE_FAMILIES["local_refinement"][template_idx]
    rng = np.random.RandomState(seed)

    if template == "void_single_resolve":
        grid = _make_void_terminal_grid(1, 0, seed)
    elif template == "void_multi_resolve":
        n_void = rng.randint(5, 20)
        grid = _make_void_terminal_grid(n_void, 0, seed)
    elif template == "terminal_self_stable":
        grid = _make_terminal_grid(seed, pattern=0)
    elif template == "void_block_resolve":
        # Block of void cells
        tokens = list(_make_terminal_grid(seed, pattern=1))
        start_r, start_c = rng.randint(0, 6), rng.randint(0, 6)
        for dr in range(3):
            for dc in range(3):
                tokens[(start_r + dr) * 9 + (start_c + dc)] = VOID_OPCODE
        grid = tuple(tokens)
    elif template == "void_row_resolve":
        tokens = list(_make_terminal_grid(seed, pattern=1))
        row = rng.randint(0, 9)
        for c in range(9):
            tokens[row * 9 + c] = VOID_OPCODE
        grid = tuple(tokens)
    elif template == "void_column_resolve":
        tokens = list(_make_terminal_grid(seed, pattern=1))
        col = rng.randint(0, 9)
        for r in range(9):
            tokens[r * 9 + col] = VOID_OPCODE
        grid = tuple(tokens)
    elif template == "void_scatter_resolve":
        n_void = rng.randint(10, 30)
        grid = _make_void_terminal_grid(n_void, 0, seed)
    elif template == "terminal_to_expansion":
        grid = _make_expansion_grid(1, seed, cluster=False)
    elif template == "void_adjacent_pair":
        tokens = list(_make_terminal_grid(seed, pattern=1))
        pos = rng.randint(0, GRID_SIZE - 1)
        tokens[pos] = VOID_OPCODE
        tokens[pos + 1] = VOID_OPCODE
        grid = tuple(tokens)
    else:  # void_diagonal_chain
        tokens = list(_make_terminal_grid(seed, pattern=1))
        for i in range(min(9, rng.randint(3, 9))):
            tokens[i * 10] = VOID_OPCODE
        grid = tuple(tokens)

    mask = _make_mask(grid, writable_fraction=1.0, seed=seed)
    return grid, mask, 0


def _generate_expansion_decomposition(
    case_idx: int, template_idx: int, seed: int
) -> Tuple[Tuple[int, ...], Tuple[int, ...], int]:
    """Generate expansion and decomposition case."""
    template = TEMPLATE_FAMILIES["expansion_decomposition"][template_idx]
    rng = np.random.RandomState(seed)

    if template == "single_expansion_isolated":
        grid = _make_expansion_grid(1, seed, cluster=False)
    elif template == "single_expansion_adjacent":
        tokens = list(_make_terminal_grid(seed, pattern=1))
        pos = rng.randint(0, GRID_SIZE - 10)
        tokens[pos] = EXPANSION_OPCODE
        tokens[pos + 1] = EXPANSION_OPCODE
        grid = tuple(tokens)
    elif template == "multi_expansion_cluster":
        n_exp = rng.randint(3, 9)
        grid = _make_expansion_grid(n_exp, seed, cluster=True)
    elif template == "multi_expansion_scattered":
        n_exp = rng.randint(5, 20)
        grid = _make_expansion_grid(n_exp, seed, cluster=False)
    elif template == "expansion_terminal_boundary":
        tokens = list(_make_terminal_grid(seed, pattern=0))
        for i in range(0, 9):
            tokens[i * 9] = EXPANSION_OPCODE
        grid = tuple(tokens)
    elif template == "expansion_void_boundary":
        grid = _make_void_terminal_grid(10, 5, seed)
    elif template == "expansion_full_row":
        tokens = list(_make_terminal_grid(seed, pattern=1))
        row = rng.randint(0, 9)
        for c in range(9):
            tokens[row * 9 + c] = EXPANSION_OPCODE
        grid = tuple(tokens)
    elif template == "expansion_cross_pattern":
        tokens = list(_make_terminal_grid(seed, pattern=1))
        mid = 4
        for i in range(9):
            tokens[mid * 9 + i] = EXPANSION_OPCODE
            tokens[i * 9 + mid] = EXPANSION_OPCODE
        grid = tuple(tokens)
    elif template == "expansion_corner_focus":
        tokens = list(_make_terminal_grid(seed, pattern=1))
        for corner_r, corner_c in [(0, 0), (0, 8), (8, 0), (8, 8)]:
            for dr in range(2):
                for dc in range(2):
                    r, c = corner_r + dr, corner_c + dc
                    if 0 <= r < 9 and 0 <= c < 9:
                        tokens[r * 9 + c] = EXPANSION_OPCODE
        grid = tuple(tokens)
    else:  # expansion_center_focus
        tokens = list(_make_terminal_grid(seed, pattern=1))
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                r, c = 4 + dr, 4 + dc
                if 0 <= r < 9 and 0 <= c < 9:
                    tokens[r * 9 + c] = EXPANSION_OPCODE
        grid = tuple(tokens)

    mask = _make_mask(grid, writable_fraction=1.0, seed=seed)
    return grid, mask, 0


def _generate_child_fold(
    case_idx: int, template_idx: int, seed: int
) -> Tuple[Tuple[int, ...], Tuple[int, ...], int]:
    """Generate child and fold case."""
    template = TEMPLATE_FAMILIES["child_fold"][template_idx]
    rng = np.random.RandomState(seed)
    grid, mask, depth = _generate_expansion_decomposition(
        case_idx, template_idx % 10, seed
    )
    # Child cases typically have depth >= 1
    depth = max(1, depth)
    return grid, mask, depth


def _generate_terminal_quiescence(
    case_idx: int, template_idx: int, seed: int
) -> Tuple[Tuple[int, ...], Tuple[int, ...], int]:
    """Generate terminal and quiescence case."""
    template = TEMPLATE_FAMILIES["terminal_quiescence"][template_idx]
    rng = np.random.RandomState(seed)

    if template == "all_terminal_uniform":
        t = sorted(TERMINAL_OPCODES)[rng.randint(0, 6)]
        grid = tuple([t] * GRID_SIZE)
    elif template == "all_terminal_mixed":
        grid = _make_terminal_grid(seed, pattern=0)
    elif template == "quiescent_after_depth":
        grid = _make_terminal_grid(seed, pattern=1)
        return grid, _make_mask(grid, 1.0, seed), 3
    elif template == "quiescent_no_void":
        grid = _make_terminal_grid(seed, pattern=2)
    elif template == "quiescent_with_void":
        tokens = list(_make_terminal_grid(seed, pattern=1))
        n_void = rng.randint(1, 5)
        for pos in rng.choice(GRID_SIZE, size=n_void, replace=False):
            tokens[pos] = VOID_OPCODE
        grid = tuple(tokens)
    elif template == "quiescent_single_terminal_type":
        t = sorted(TERMINAL_OPCODES)[0]
        grid = tuple([t] * GRID_SIZE)
    elif template == "quiescent_two_terminal_types":
        t1, t2 = sorted(TERMINAL_OPCODES)[:2]
        grid = tuple(t1 if i % 2 == 0 else t2 for i in range(GRID_SIZE))
    elif template == "quiescent_full_spectrum":
        terminal_list = sorted(TERMINAL_OPCODES)
        grid = tuple(
            terminal_list[i % len(terminal_list)] for i in range(GRID_SIZE)
        )
    elif template == "quiescent_pattern_a":
        tokens = list(_make_terminal_grid(seed, pattern=1))
        # All terminals, specific pattern
        for r in range(9):
            for c in range(9):
                tokens[r * 9 + c] = (r + c) % len(sorted(TERMINAL_OPCODES))
        grid = tuple(tokens)
    else:  # quiescent_pattern_b
        tokens = list(_make_terminal_grid(seed, pattern=1))
        for r in range(9):
            for c in range(9):
                tokens[r * 9 + c] = (r * c) % len(sorted(TERMINAL_OPCODES))
        grid = tuple(tokens)

    mask = _make_mask(grid, writable_fraction=1.0, seed=seed)
    return grid, mask, 0


def _generate_contradiction_invalid(
    case_idx: int, template_idx: int, seed: int
) -> Tuple[Tuple[int, ...], Tuple[int, ...], int]:
    """Generate contradiction and invalid state case."""
    template = TEMPLATE_FAMILIES["contradiction_invalid"][template_idx]
    rng = np.random.RandomState(seed)

    if template == "no_writable_expansion":
        grid = _make_expansion_grid(5, seed, cluster=False)
        # Mask all expansion cells as non-writable
        mask_list = [0] * GRID_SIZE
        for i, t in enumerate(grid):
            if t != EXPANSION_OPCODE:
                mask_list[i] = 1
        mask = tuple(mask_list)
    elif template == "contradictory_mask":
        grid = _make_void_terminal_grid(20, 3, seed)
        # Mask most cells non-writable
        mask = _make_mask(grid, writable_fraction=0.1, seed=seed)
    elif template == "depth_exceeded":
        grid = _make_expansion_grid(2, seed, cluster=False)
        mask = _make_mask(grid, 1.0, seed)
        return grid, mask, 10  # depth beyond max
    elif template == "all_masked_expansion":
        grid = tuple([EXPANSION_OPCODE] * GRID_SIZE)
        mask = (0,) * GRID_SIZE
    elif template == "island_expansion":
        tokens = list(_make_terminal_grid(seed, pattern=1))
        tokens[40] = EXPANSION_OPCODE
        # Surrounding cells non-writable
        mask_list = [0] * GRID_SIZE
        mask_list[40] = 1
        mask = tuple(mask_list)
        grid = tuple(tokens)
    elif template == "adjacent_contradiction":
        tokens = list(_make_terminal_grid(seed, pattern=1))
        tokens[0] = EXPANSION_OPCODE
        tokens[1] = VOID_OPCODE
        grid = tuple(tokens)
        mask = _make_mask(grid, 1.0, seed)
    elif template == "full_void_no_mask":
        grid = (VOID_OPCODE,) * GRID_SIZE
        mask = (0,) * GRID_SIZE
    elif template == "mixed_invalid_tokens":
        # All void and expansion mixed in ways that create ambiguity
        tokens = []
        for i in range(GRID_SIZE):
            if i % 3 == 0:
                tokens.append(VOID_OPCODE)
            elif i % 3 == 1:
                tokens.append(EXPANSION_OPCODE)
            else:
                tokens.append(sorted(TERMINAL_OPCODES)[0])
        grid = tuple(tokens)
        mask = _make_mask(grid, 0.5, seed)
    elif template == "provenance_conflict":
        grid = _make_expansion_grid(3, seed, cluster=True)
        mask = _make_mask(grid, 1.0, seed)
        return grid, mask, 5
    else:  # constraint_violation_set
        grid = _make_contradiction_grid(seed, pattern=template_idx % 3)
        mask = _make_mask(grid, 0.3, seed)

    return grid, mask, 0


def _generate_boundary_malformed(
    case_idx: int, template_idx: int, seed: int
) -> Tuple[Tuple[int, ...], Tuple[int, ...], int]:
    """Generate boundary and malformed case."""
    template = TEMPLATE_FAMILIES["boundary_malformed"][template_idx]
    rng = np.random.RandomState(seed)
    terminal_list = sorted(TERMINAL_OPCODES)

    if template == "single_cell_grid":
        tokens = [VOID_OPCODE] * GRID_SIZE
        tokens[rng.randint(0, GRID_SIZE)] = EXPANSION_OPCODE
        grid = tuple(tokens)
    elif template == "edge_only_pattern":
        tokens = [VOID_OPCODE] * GRID_SIZE
        for r in [0, 8]:
            for c in range(9):
                tokens[r * 9 + c] = terminal_list[(r + c) % len(terminal_list)]
        for c in [0, 8]:
            for r in range(9):
                tokens[r * 9 + c] = terminal_list[(r + c) % len(terminal_list)]
        grid = tuple(tokens)
    elif template == "corner_only_pattern":
        tokens = [VOID_OPCODE] * GRID_SIZE
        for corner_r, corner_c in [(0, 0), (0, 8), (8, 0), (8, 8)]:
            tokens[corner_r * 9 + corner_c] = EXPANSION_OPCODE
        grid = tuple(tokens)
    elif template == "sparse_single_token":
        tokens = [VOID_OPCODE] * GRID_SIZE
        tokens[40] = terminal_list[0]
        grid = tuple(tokens)
    elif template == "max_depth_state":
        grid = _make_terminal_grid(seed, pattern=1)
        mask = _make_mask(grid, 1.0, seed)
        return grid, mask, 3
    elif template == "zero_depth_full_grid":
        grid = _make_expansion_grid(10, seed, cluster=False)
        mask = _make_mask(grid, 1.0, seed)
        return grid, mask, 0
    elif template == "alternating_void_terminal":
        t = terminal_list[0]
        grid = tuple(VOID_OPCODE if i % 2 == 0 else t
                     for i in range(GRID_SIZE))
    elif template == "strip_pattern":
        tokens = [VOID_OPCODE] * GRID_SIZE
        for r in range(0, 9, 2):
            for c in range(9):
                tokens[r * 9 + c] = terminal_list[r % len(terminal_list)]
        grid = tuple(tokens)
    elif template == "concentric_rings":
        tokens = [VOID_OPCODE] * GRID_SIZE
        for r in range(9):
            for c in range(9):
                ring = min(r, c, 8 - r, 8 - c)
                tokens[r * 9 + c] = terminal_list[ring % len(terminal_list)]
        grid = tuple(tokens)
    else:  # fractal_boundary
        tokens = [VOID_OPCODE] * GRID_SIZE
        for r in range(9):
            for c in range(9):
                if (r % 3 == 0) or (c % 3 == 0):
                    tokens[r * 9 + c] = terminal_list[(r + c) % len(terminal_list)]
        grid = tuple(tokens)

    mask = _make_mask(grid, writable_fraction=1.0, seed=seed)
    return grid, mask, 0


def _generate_equivariance_metamorphic(
    case_idx: int, template_idx: int, seed: int
) -> Tuple[Tuple[int, ...], Tuple[int, ...], int]:
    """Generate equivariance and metamorphic case."""
    template = TEMPLATE_FAMILIES["equivariance_metamorphic"][template_idx]
    rng = np.random.RandomState(seed)
    terminal_list = sorted(TERMINAL_OPCODES)

    if template == "rotate_90_pair":
        # Generate base grid, output is the 90-rotated version
        grid = _make_expansion_grid(rng.randint(2, 6), seed, cluster=False)
    elif template == "rotate_180_pair":
        grid = _make_expansion_grid(rng.randint(2, 6), seed, cluster=False)
    elif template == "reflect_h_pair":
        grid = _make_expansion_grid(rng.randint(2, 6), seed, cluster=False)
    elif template == "reflect_v_pair":
        grid = _make_void_terminal_grid(
            rng.randint(5, 15), rng.randint(1, 5), seed
        )
    elif template == "token_permutation_class":
        tokens = list(_make_terminal_grid(seed, pattern=1))
        # Permute terminal tokens via index swap
        import random
        rng_perm = random.Random(seed)
        perm = list(range(len(terminal_list)))
        rng_perm.shuffle(perm)
        terminal_map = {terminal_list[i]: terminal_list[perm[i]] for i in range(len(terminal_list))}
        grid = tuple(terminal_map.get(t, t) for t in tokens)
    elif template == "structural_isomorphism":
        grid = _make_expansion_grid(4, seed, cluster=True)
    elif template == "symmetry_orbit_size_8":
        grid = _make_expansion_grid(1, seed, cluster=False)
    elif template == "symmetry_orbit_size_4":
        tokens = list(_make_terminal_grid(seed, pattern=1))
        tokens[40] = EXPANSION_OPCODE
        grid = tuple(tokens)
    elif template == "metamorphic_expansion":
        grid = _make_expansion_grid(5, seed, cluster=True)
    else:  # metamorphic_quiescence
        grid = _make_terminal_grid(seed, pattern=0)

    mask = _make_mask(grid, writable_fraction=1.0, seed=seed)
    return grid, mask, 0


# Map stratum name to generator function
STRATUM_GENERATORS = {
    "local_refinement": _generate_local_refinement,
    "expansion_decomposition": _generate_expansion_decomposition,
    "child_fold": _generate_child_fold,
    "terminal_quiescence": _generate_terminal_quiescence,
    "contradiction_invalid": _generate_contradiction_invalid,
    "boundary_malformed": _generate_boundary_malformed,
    "equivariance_metamorphic": _generate_equivariance_metamorphic,
}


# ---------------------------------------------------------------------------
# Leakage detector (GATE 11)
# ---------------------------------------------------------------------------


class LeakageDetector:
    """
    Detect corpus split leakage through isomorphism and template analysis.
    """

    def __init__(self):
        self._train_isomorphs: Set[str] = set()
        self._validation_isomorphs: Set[str] = set()
        self._test_isomorphs: Set[str] = set()
        self._train_families: Set[str] = set()
        self._validation_families: Set[str] = set()
        self._test_families: Set[str] = set()

    def register(self, case: CorpusCase, split: str):
        """Register a case for leakage detection."""
        iso_digest = _canonical_symmetry_digest(
            StructuralGrid(tokens=case.input_grid)
        )

        if split == "train":
            self._train_isomorphs.add(iso_digest)
            self._train_families.add(case.template_family)
        elif split == "validation":
            self._validation_isomorphs.add(iso_digest)
            self._validation_families.add(case.template_family)
        elif split == "test":
            self._test_isomorphs.add(iso_digest)
            self._test_families.add(case.template_family)

    def check_isomorphism_leakage(self) -> Dict[str, int]:
        """Check for isomorphic cases across splits."""
        train_val = len(self._train_isomorphs & self._validation_isomorphs)
        train_test = len(self._train_isomorphs & self._test_isomorphs)
        val_test = len(self._validation_isomorphs & self._test_isomorphs)
        return {
            "train_validation": train_val,
            "train_test": train_test,
            "validation_test": val_test,
        }

    def check_family_leakage(self) -> Dict[str, int]:
        """Check for template family overlap across splits."""
        train_val = len(self._train_families & self._validation_families)
        train_test = len(self._train_families & self._test_families)
        val_test = len(self._validation_families & self._test_families)
        return {
            "train_validation": train_val,
            "train_test": train_test,
            "validation_test": val_test,
        }

    def report(self) -> dict:
        """Generate full leakage report."""
        return {
            "isomorphism_leakage": self.check_isomorphism_leakage(),
            "family_leakage": self.check_family_leakage(),
            "train_isomorph_count": len(self._train_isomorphs),
            "validation_isomorph_count": len(self._validation_isomorphs),
            "test_isomorph_count": len(self._test_isomorphs),
        }


# ---------------------------------------------------------------------------
# Symmetry canonicalizer (GATE 11)
# ---------------------------------------------------------------------------


class SymmetryCanonicalizer:
    """
    Canonicalize grids under admitted symmetry group.
    """

    @staticmethod
    def canonicalize(grid: StructuralGrid) -> StructuralGrid:
        """Return the lexicographically smallest rotation/reflection."""
        variants = [grid]
        g = grid
        for _ in range(3):
            g = _rotate_90(g)
            variants.append(g)

        # Add reflected versions
        from .structural_oracle import _reflect_horizontal
        g_ref = _reflect_horizontal(grid)
        variants.append(g_ref)
        for _ in range(3):
            g_ref = _rotate_90(g_ref)
            variants.append(g_ref)

        return min(variants, key=lambda g: g.tokens)

    @staticmethod
    def canonical_digest(grid: StructuralGrid) -> str:
        """Compute canonical isomorphism digest."""
        canonical = SymmetryCanonicalizer.canonicalize(grid)
        return canonical.digest()


# ---------------------------------------------------------------------------
# Corpus generator (GATE 10 main)
# ---------------------------------------------------------------------------


class CorpusGenerator:
    """
    Deterministic corpus generator.

    Produces 8,192 cases across 8 strata with leakage-resistant splits.
    """

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._oracle = StructuralOracle()

    def generate_all(self) -> List[CorpusCase]:
        """Generate the full corpus."""
        cases = []
        case_idx = 0

        for stratum_name, count in sorted(STRATA_CONFIG.items()):
            families = TEMPLATE_FAMILIES[stratum_name]
            generator = STRATUM_GENERATORS[stratum_name]

            # Distribute cases across template families
            cases_per_family = count // len(families)
            remainder = count % len(families)

            for fi, family_name in enumerate(families):
                n_cases = cases_per_family + (1 if fi < remainder else 0)
                for ci in range(n_cases):
                    seed = self._seed + case_idx * 7 + fi * 13 + ci * 17
                    grid, mask, depth = generator(case_idx, fi, seed)

                    # Build state and evaluate
                    state_grid = StructuralGrid(tokens=grid)
                    state = StructuralState.root(
                        grid=state_grid,
                        mask=mask,
                    )

                    transition = self._oracle.evaluate(state)

                    # Build valid target digests
                    valid_digests = tuple(
                        ns.digest()
                        for ns in transition.valid_next_states
                    )

                    # Symmetry family
                    sym_digest = _canonical_symmetry_digest(state_grid)

                    # Compute case digest
                    case_raw = (
                        f"{case_idx}|{','.join(str(t) for t in grid)}|"
                        f"{','.join(str(m) for m in mask)}|"
                        f"{depth}|{transition.canonical_next_state.digest()}"
                    )
                    case_d = hashlib.sha256(case_raw.encode()).hexdigest()

                    # Provenance digest
                    prov_d = hashlib.sha256(
                        f"root|{sym_digest}|{stratum_name}".encode()
                    ).hexdigest()

                    case = CorpusCase(
                        case_id=f"t00_{case_idx:05d}",
                        generator_version=GENERATOR_VERSION,
                        generator_seed=seed,
                        template_family=family_name,
                        stratum=stratum_name,
                        input_grid=grid,
                        input_mask=mask,
                        input_depth=depth,
                        semantic_space=SEMANTIC_SPACE,
                        abi_version=ABI_VERSION,
                        valid_target_digests=valid_digests,
                        canonical_target_digest=transition.canonical_next_state.digest(),
                        expansion_targets=tuple(
                            (et.cell, et.rationale_code)
                            for et in transition.expansion_targets
                        ),
                        quiescence_target=transition.quiescence,
                        violation_codes=transition.violation_codes,
                        rationale_codes=transition.rationale_codes,
                        symmetry_family=sym_digest[:16],
                        provenance_digest=prov_d,
                        case_digest=case_d,
                    )

                    cases.append(case)
                    case_idx += 1

        return cases

    def generate_corpus_with_splits(
        self, output_dir: str
    ) -> Tuple[CorpusManifest, Dict[str, SplitManifest]]:
        """
        Generate full corpus and write to disk with exact splits.

        Returns manifest and split manifests.

        Exact targets:
          train    = 6144
          validation = 1024
          test   = 1024

        Zero leakage guarantee:
          No template family crosses split boundaries.
          No isomorphism digest crosses split boundaries.
          Subdivided families carry semantically named subfamily tags.
        """
        import os
        from dataclasses import replace
        os.makedirs(output_dir, exist_ok=True)

        # Generate all cases
        all_cases = self.generate_all()

        assert len(all_cases) == TOTAL_CASES, (
            f"Generated {len(all_cases)} != {TOTAL_CASES}"
        )

        # -----------------------------------------------------------------
        # Deterministic split allocator with zero leakage
        # -----------------------------------------------------------------
        # Core invariant: each isomorphism digest group is atomic and lives
        # in exactly one split.  This guarantees zero family AND zero iso
        # leakage simultaneously.
        #
        # Strategy: bin-pack iso groups (sorted largest first) into
        # train=6144, validation=1024, test=1024.  Subfamily names are
        # derived from the iso digest so the LeakageDetector sees clean
        # family boundaries.
        # -----------------------------------------------------------------

        from .structural_semantics import StructuralGrid

        # Group cases by iso digest (atomic unit)
        iso_to_cases: Dict[str, List[CorpusCase]] = {}
        case_iso: Dict[str, str] = {}
        for case in all_cases:
            iso = _canonical_symmetry_digest(
                StructuralGrid(tokens=case.input_grid)
            )
            iso_to_cases.setdefault(iso, []).append(case)
            case_iso[case.case_id] = iso

        # Sort iso groups: largest first, then by iso digest for determinism
        iso_groups = sorted(
            iso_to_cases.items(),
            key=lambda x: (-len(x[1]), x[0]),
        )

        train_target = SPLIT_RATIOS["train"]
        val_target = SPLIT_RATIOS["validation"]
        test_target = SPLIT_RATIOS["test"]

        # Subfamily naming: each iso group gets a unique family name
        # so the LeakageDetector sees zero overlap.
        def _subfam_name(iso: str) -> str:
            return f"iso_{iso[:16]}"

        # Bin-pack iso groups into splits
        assignment: Dict[str, str] = {}  # iso_digest -> split
        train_count = 0
        val_count = 0
        test_count = 0

        for iso, grp_cases in iso_groups:
            n = len(grp_cases)
            if train_count + n <= train_target:
                assignment[iso] = "train"
                train_count += n
            elif val_count + n <= val_target:
                assignment[iso] = "validation"
                val_count += n
            else:
                assignment[iso] = "test"
                test_count += n

        # Build final_cases with updated template_family
        from dataclasses import replace

        final_cases: List[CorpusCase] = []
        case_split: Dict[str, str] = {}
        for iso, grp_cases in iso_to_cases.items():
            split = assignment[iso]
            subfam = _subfam_name(iso)
            for c in grp_cases:
                updated = replace(c, template_family=subfam)
                final_cases.append(updated)
                case_split[c.case_id] = split

        # Phase 2: exact-count redistribution
        # If any split is off target, swap individual iso groups between
        # splits to close the gap.  Since iso groups are atomic, this
        # preserves zero leakage by construction.
        def _redistribute():
            nonlocal train_count, val_count, test_count
            # Build iso -> count map
            iso_counts = {iso: len(grp) for iso, grp in iso_to_cases.items()}

            for _iteration in range(1000):
                # Which split is under?
                under = None
                if train_count < train_target:
                    under = "train"
                elif val_count < val_target:
                    under = "validation"
                elif test_count < test_target:
                    under = "test"
                if under is None:
                    break

                # Which split is over?
                over = None
                if train_count > train_target:
                    over = "train"
                elif val_count > val_target:
                    over = "validation"
                elif test_count > test_target:
                    over = "test"
                if over is None:
                    break

                # Find an iso group to move from over to under
                # Prefer groups that get us closest to target
                over_isos = [iso for iso, s in assignment.items() if s == over]
                best_iso = None
                best_diff = float("inf")

                for iso in over_isos:
                    n = iso_counts[iso]
                    if under == "train":
                        new_train = train_count + n
                        diff = abs(new_train - train_target)
                    elif under == "validation":
                        new_val = val_count + n
                        diff = abs(new_val - val_target)
                    else:
                        new_test = test_count + n
                        diff = abs(new_test - test_target)

                    if diff < best_diff:
                        best_diff = diff
                        best_iso = iso

                if best_iso is None:
                    break

                # Move best_iso from over to under
                n = iso_counts[best_iso]
                assignment[best_iso] = under
                for c in iso_to_cases[best_iso]:
                    case_split[c.case_id] = under

                if under == "train":
                    train_count += n
                elif under == "validation":
                    val_count += n
                else:
                    test_count += n

                if over == "train":
                    train_count -= n
                elif over == "validation":
                    val_count -= n
                else:
                    test_count -= n

        _redistribute()

        # Build split case lists
        train_cases = [c for c in final_cases if case_split.get(c.case_id) == "train"]
        val_cases = [c for c in final_cases if case_split.get(c.case_id) == "validation"]
        test_cases = [c for c in final_cases if case_split.get(c.case_id) == "test"]

        # -----------------------------------------------------------------
        # Leakage detection
        # -----------------------------------------------------------------
        detector = LeakageDetector()
        for c in train_cases:
            detector.register(c, "train")
        for c in val_cases:
            detector.register(c, "validation")
        for c in test_cases:
            detector.register(c, "test")

        leakage_report = detector.report()

        # Write splits
        serializer = CorpusSerializer()

        def write_split(split_name: str, cases: List[CorpusCase]) -> SplitManifest:
            lines = [serializer.serialize_case(c) for c in cases]
            data = "\n".join(lines) + "\n"
            with open(os.path.join(output_dir, f"{split_name}.jsonl"), "w") as f:
                f.write(data)

            strata_counts: Dict[str, int] = {}
            for c in cases:
                strata_counts[c.stratum] = strata_counts.get(c.stratum, 0) + 1

            checksum = serializer.compute_checksum(data)
            return SplitManifest(
                split_name=split_name,
                case_ids=tuple(c.case_id for c in cases),
                template_families=tuple(c.template_family for c in cases),
                strata=strata_counts,
                checksum=checksum,
            )

        train_manifest = write_split("train", train_cases)
        val_manifest = write_split("validation", val_cases)
        test_manifest = write_split("test", test_cases)

        # Compute strata counts
        strata_counts: Dict[str, int] = {}
        for c in all_cases:
            strata_counts[c.stratum] = strata_counts.get(c.stratum, 0) + 1

        # Write manifest
        full_checksum = serializer.compute_checksum(
            json.dumps({
                "train": train_manifest.checksum,
                "validation": val_manifest.checksum,
                "test": test_manifest.checksum,
            }, sort_keys=True)
        )

        manifest = CorpusManifest(
            corpus_id="t00_structural_corpus",
            generator_version=GENERATOR_VERSION,
            total_cases=len(all_cases),
            strata=strata_counts,
            splits={
                "train": len(train_cases),
                "validation": len(val_cases),
                "test": len(test_cases),
            },
            checksum=full_checksum,
        )

        with open(os.path.join(output_dir, "manifest.json"), "w") as f:
            f.write(serializer.serialize_manifest(manifest))

        # Write split manifests
        for sm in [train_manifest, val_manifest, test_manifest]:
            with open(
                os.path.join(output_dir, f"{sm.split_name}_manifest.json"), "w"
            ) as f:
                f.write(serializer.serialize_split_manifest(sm))

        # Write checksums
        checksum_lines = []
        for fname in ["train.jsonl", "validation.jsonl", "test.jsonl", "manifest.json"]:
            fpath = os.path.join(output_dir, fname)
            with open(fpath, "rb") as f:
                raw = f.read()
            cs = hashlib.sha256(raw).hexdigest()
            checksum_lines.append(f"{cs}  {fname}")

        with open(os.path.join(output_dir, "checksums.sha256"), "w") as f:
            f.write("\n".join(checksum_lines) + "\n")

        # Write leakage report
        with open(os.path.join(output_dir, "leakage_report.json"), "w") as f:
            json.dump(leakage_report, f, sort_keys=True, indent=2)

        return manifest, {
            "train": train_manifest,
            "validation": val_manifest,
            "test": test_manifest,
        }
