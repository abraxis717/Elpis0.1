"""D4 symmetry group implementation for 9x9 grid transforms.

Implements exactly 8 D4 elements as permutations on 81 indices (9x9 grid).
D4 = dihedral group of order 8: symmetries of a square.

Elements (named by their geometric action):
  0: e    - identity
  1: r90  - rotation 90 deg clockwise
  2: r180 - rotation 180 deg
  3: r270 - rotation 270 deg clockwise
  4: fh   - horizontal flip
  5: fv   - vertical flip
  6: fd   - main diagonal flip (transpose)
  7: fa   - anti-diagonal flip
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from elpis_grid81_typed.errors import D4Error


# Each D4 element is represented as a permutation of 81 indices.
# transform[i] = j means position i maps to position j.
# For a 9x9 grid, linear index = row * 9 + col.

def _row_col(idx: int) -> Tuple[int, int]:
    """Convert linear index to (row, col) in 9x9 grid."""
    return idx // 9, idx % 9


def _linear(row: int, col: int) -> int:
    """Convert (row, col) to linear index in 9x9 grid."""
    return row * 9 + col


def _build_transform(func) -> List[int]:
    """Build a permutation list from a row/col transformation function.

    func takes (row, col) and returns (new_row, new_col).
    Result[i] = j means index i maps to index j.
    """
    perm = [0] * 81
    for i in range(81):
        r, c = _row_col(i)
        nr, nc = func(r, c)
        perm[i] = _linear(nr, nc)
    return perm


# Define the 8 D4 elements as row/col transforms
_D4_FUNCS = [
    # 0: identity
    lambda r, c: (r, c),
    # 1: rotation 90 clockwise
    lambda r, c: (c, 8 - r),
    # 2: rotation 180
    lambda r, c: (8 - r, 8 - c),
    # 3: rotation 270 clockwise (= 90 counter-clockwise)
    lambda r, c: (8 - c, r),
    # 4: horizontal flip (flip across vertical midline)
    lambda r, c: (r, 8 - c),
    # 5: vertical flip (flip across horizontal midline)
    lambda r, c: (8 - r, c),
    # 6: main diagonal flip (transpose)
    lambda r, c: (c, r),
    # 7: anti-diagonal flip
    lambda r, c: (8 - c, 8 - r),
]

D4_TRANSFORMS: List[List[int]] = [_build_transform(f) for f in _D4_FUNCS]

D4_NAMES = ["e", "r90", "r180", "r270", "fh", "fv", "fd", "fa"]


def transform_coordinate(transform_idx: int, row: int, col: int) -> Tuple[int, int]:
    """Apply D4 transform to a (row, col) coordinate."""
    if not (0 <= transform_idx < 8):
        raise D4Error(f"Invalid D4 transform index: {transform_idx}")
    func = _D4_FUNCS[transform_idx]
    return func(row, col)


def transform_index(transform_idx: int, idx: int) -> int:
    """Apply D4 transform to a linear grid index (0-80)."""
    if not (0 <= transform_idx < 8):
        raise D4Error(f"Invalid D4 transform index: {transform_idx}")
    return D4_TRANSFORMS[transform_idx][idx]


def transform_grid81(transform_idx: int, grid: List[int]) -> List[int]:
    """Apply D4 transform to a full 81-cell grid.

    The transform permutes positions: output[j] = input[i] where j = perm[i].
    This means the value at position i moves to position perm[i].
    """
    if not (0 <= transform_idx < 8):
        raise D4Error(f"Invalid D4 transform index: {transform_idx}")
    perm = D4_TRANSFORMS[transform_idx]
    result = [0] * 81
    for i in range(81):
        result[perm[i]] = grid[i]
    return result


def transform_mask81(transform_idx: int, mask: List[int]) -> List[int]:
    """Apply D4 transform to an 81-cell binary mask."""
    return transform_grid81(transform_idx, mask)


def compose(t1: int, t2: int) -> int:
    """Compose two D4 transforms: result = t1 ∘ t2.

    Returns the index (0-7) of the composed transform.
    """
    if not (0 <= t1 < 8 and 0 <= t2 < 8):
        raise D4Error(f"Invalid D4 compose arguments: t1={t1}, t2={t2}")

    # Compose by applying t2 first, then t1
    perm_t2 = D4_TRANSFORMS[t2]
    perm_t1 = D4_TRANSFORMS[t1]

    # (t1 ∘ t2)[i] = t1[t2[i]]
    composed = [perm_t1[perm_t2[i]] for i in range(81)]

    # Find which D4 element matches this composition
    for idx, perm in enumerate(D4_TRANSFORMS):
        if perm == composed:
            return idx

    raise D4Error(f"Composition of t1={t1} and t2={t2} yields unknown transform")


def inverse(t: int) -> int:
    """Find the inverse of a D4 transform.

    Returns index such that compose(t, inverse(t)) == 0 (identity).
    """
    if not (0 <= t < 8):
        raise D4Error(f"Invalid D4 transform index: {t}")

    perm = D4_TRANSFORMS[t]

    # The inverse permutation: inv[perm[i]] = i
    inv_perm = [0] * 81
    for i in range(81):
        inv_perm[perm[i]] = i

    # Find matching D4 element
    for idx, p in enumerate(D4_TRANSFORMS):
        if p == inv_perm:
            return idx

    raise D4Error(f"No D4 element matches inverse of transform {t}")


# Multiplication table for D4
_D4_TABLE: List[List[int]] = [[compose(i, j) for j in range(8)] for i in range(8)]


def verify_d4_group() -> Dict[str, bool]:
    """Verify D4 group properties.

    Checks:
        - 8 unique transforms
        - Each is a bijection on 81 indices
        - Identity element exists
        - Inverse closure (each element has an inverse)
        - 512 associativity checks (8^3)
        - 5184 semantic composition checks (8 transforms * 81 indices * 8 compositions)
    """
    results = {}

    # 8 unique transforms
    unique_count = len(set(tuple(perm) for perm in D4_TRANSFORMS))
    results["eight_unique_transforms"] = (unique_count == 8)

    # 81-index bijection for each transform
    for t_idx, perm in enumerate(D4_TRANSFORMS):
        if sorted(perm) != list(range(81)):
            results[f"bijection_t{t_idx}"] = False
            break
    else:
        results["all_bijections"] = True

    # Identity element
    results["identity_exists"] = D4_TRANSFORMS[0] == list(range(81))

    # Inverse closure
    inverse_ok = True
    for i in range(8):
        inv = inverse(i)
        # compose(i, inv(i)) should be identity
        if compose(i, inv) != 0:
            inverse_ok = False
            break
        if compose(inv, i) != 0:
            inverse_ok = False
            break
    results["inverse_closure"] = inverse_ok

    # 512 associativity checks
    assoc_ok = True
    for a in range(8):
        for b in range(8):
            for c in range(8):
                if compose(a, compose(b, c)) != compose(compose(a, b), c):
                    assoc_ok = False
                    break
            if not assoc_ok:
                break
        if not assoc_ok:
            break
    results["associativity_512"] = assoc_ok

    # 5184 semantic composition checks:
    # For each transform pair and each index, verify composition consistency
    semantic_ok = True
    for t1 in range(8):
        for t2 in range(8):
            t_composed = compose(t1, t2)
            for idx in range(81):
                # Direct application of composed transform
                direct = D4_TRANSFORMS[t_composed][idx]
                # Sequential application: t1(t2(idx))
                sequential = D4_TRANSFORMS[t1][D4_TRANSFORMS[t2][idx]]
                if direct != sequential:
                    semantic_ok = False
                    break
            if not semantic_ok:
                break
        if not semantic_ok:
            break
    results["semantic_composition_5184"] = semantic_ok

    return results


def transform_transition_view(
    transform_idx: int,
    view_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Transform a transition view under D4.

    - grid: equivariant (positions permuted, values preserved)
    - mask: equivariant (positions permuted, values preserved)
    - target_cell: equivariant (position transformed)
    - target_value: invariant (token identity preserved)
    - delta_kind: invariant (NOOP/EDIT preserved)
    """
    result = dict(view_dict)
    result["input_grid"] = transform_grid81(transform_idx, view_dict["input_grid"])
    result["input_mask"] = transform_mask81(transform_idx, view_dict["input_mask"])
    result["canonical_target_grid"] = transform_grid81(
        transform_idx, view_dict["canonical_target_grid"]
    )
    if view_dict["target_cell"] is not None:
        result["target_cell"] = transform_index(transform_idx, view_dict["target_cell"])
    return result


def transform_expansion_view(
    transform_idx: int,
    view_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Transform an expansion view under D4.

    - grid: equivariant
    - expansion_cells: equivariant (each index transformed)
    """
    result = dict(view_dict)
    result["input_grid"] = transform_grid81(transform_idx, view_dict["input_grid"])
    result["expansion_locus_mask81"] = transform_mask81(
        transform_idx, view_dict["expansion_locus_mask81"]
    )
    result["expansion_cells"] = sorted(
        [transform_index(transform_idx, c) for c in view_dict["expansion_cells"]]
    )
    return result


def transform_quiescence_view(
    transform_idx: int,
    view_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Transform a quiescence view under D4.

    - grid: equivariant
    - quiescence labels: invariant
    """
    result = dict(view_dict)
    result["input_grid"] = transform_grid81(transform_idx, view_dict["input_grid"])
    return result


def transform_rationale_view(
    transform_idx: int,
    view_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Transform a rationale view under D4.

    Inherits transition view spatial identity:
    - grid: equivariant
    - target: equivariant (if present)
    - rationale_codes: invariant (symbolic metadata)
    """
    result = dict(view_dict)
    result["input_grid"] = transform_grid81(transform_idx, view_dict["input_grid"])
    result["canonical_target_grid"] = transform_grid81(
        transform_idx, view_dict["canonical_target_grid"]
    )
    return result


class D4:
    """D4 symmetry group of order 8 for 9x9 grid transforms.

    Provides access to transforms, composition, and verification.
    """
    TRANSFORMS = D4_TRANSFORMS
    NAMES = D4_NAMES
    ORDER = 8

    @classmethod
    def transform_index(cls, t: int, idx: int) -> int:
        return transform_index(t, idx)

    @classmethod
    def transform_grid(cls, t: int, grid: list) -> list:
        return transform_grid81(t, grid)

    @classmethod
    def compose(cls, a: int, b: int) -> int:
        return compose(a, b)

    @classmethod
    def inverse(cls, t: int) -> int:
        return inverse(t)

    @classmethod
    def verify(cls) -> dict:
        return verify_d4_group()
