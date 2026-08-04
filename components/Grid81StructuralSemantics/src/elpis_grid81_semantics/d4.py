"""D4 dihedral group enumeration for 9x9 Grid81 (G4.0B Phase 5-6).

Eight elements, row-major convention frozen by G4.0A:
  IDENTITY, ROTATE_90, ROTATE_180, ROTATE_270,
  REFLECT_HORIZONTAL, REFLECT_VERTICAL,
  REFLECT_MAIN_DIAGONAL, REFLECT_ANTI_DIAGONAL

N=9. Row-major: index = row * 9 + col,  row = index // 9,  col = index % 9.

Transform rules (G4.0A frozen):
  identity:       (r, c) -> (r, c)
  rotation_90:    (r, c) -> (c, N-1-r)
  rotation_180:   (r, c) -> (N-1-r, N-1-c)
  rotation_270:   (r, c) -> (N-1-c, r)
  reflection_h:   (r, c) -> (N-1-r, c)
  reflection_v:   (r, c) -> (r, N-1-c)
  reflection_d:   (r, c) -> (c, r)
  reflection_ad:  (r, c) -> (N-1-c, N-1-r)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Final

N: Final = 9


class D4(Enum):
    IDENTITY = auto()
    ROTATE_90 = auto()
    ROTATE_180 = auto()
    ROTATE_270 = auto()
    REFLECT_HORIZONTAL = auto()
    REFLECT_VERTICAL = auto()
    REFLECT_MAIN_DIAGONAL = auto()
    REFLECT_ANTI_DIAGONAL = auto()


# Ordered list for iteration (stable, enum definition order)
D4_ELEMENTS: Final[list[D4]] = [
    D4.IDENTITY,
    D4.ROTATE_90,
    D4.ROTATE_180,
    D4.ROTATE_270,
    D4.REFLECT_HORIZONTAL,
    D4.REFLECT_VERTICAL,
    D4.REFLECT_MAIN_DIAGONAL,
    D4.REFLECT_ANTI_DIAGONAL,
]


def _transform_coordinate_internal(r: int, c: int, element: D4) -> tuple[int, int]:
    """Apply D4 element to a (row, col) coordinate. Returns (r', c')."""
    if element == D4.IDENTITY:
        return (r, c)
    if element == D4.ROTATE_90:
        return (c, N - 1 - r)
    if element == D4.ROTATE_180:
        return (N - 1 - r, N - 1 - c)
    if element == D4.ROTATE_270:
        return (N - 1 - c, r)
    if element == D4.REFLECT_HORIZONTAL:
        return (N - 1 - r, c)
    if element == D4.REFLECT_VERTICAL:
        return (r, N - 1 - c)
    if element == D4.REFLECT_MAIN_DIAGONAL:
        return (c, r)
    if element == D4.REFLECT_ANTI_DIAGONAL:
        return (N - 1 - c, N - 1 - r)
    raise ValueError(f"Unknown D4 element: {element}")


def transform_coordinate(row: int, col: int, element: D4) -> tuple[int, int]:
    """Apply D4 transform to (row, col). Returns (row', col')."""
    return _transform_coordinate_internal(row, col, element)


def transform_index(index: int, element: D4) -> int:
    """Apply D4 transform to a flat row-major index. Returns new index."""
    r = index // N
    c = index % N
    nr, nc = _transform_coordinate_internal(r, c, element)
    return nr * N + nc


# Pre-compute the 81-element permutation for each D4 element
_PERMUTATION_TABLE: Final[dict[D4, tuple[int, ...]]] = {}
for elem in D4_ELEMENTS:
    _PERMUTATION_TABLE[elem] = tuple(transform_index(i, elem) for i in range(81))


def transform_grid81(grid81: tuple[int, ...], element: D4) -> tuple[int, ...]:
    """Transform a grid81 tuple under D4 element.

    D4 acts on positions: new_grid[transform(i)] = grid[i]
    Equivalently: new_grid[j] = grid[inverse_transform(j)]
    We use: output[t(i)] = input[i] for all i.
    """
    perm = _PERMUTATION_TABLE[element]
    out = [0] * 81
    for i in range(81):
        out[perm[i]] = grid81[i]
    return tuple(out)


def transform_mask81(mask81: tuple[int, ...], element: D4) -> tuple[int, ...]:
    """Transform a mask81 tuple under D4 element (same as grid transform)."""
    return transform_grid81(mask81, element)


def transform_action(action: dict, element: D4) -> dict:
    """Transform an action dict under D4.

    action: {'kind': 'noop'|'edit', 'target_cell': int|None, 'target_value': int|None}
    D4 acts on positions, not values.
    NOOP is invariant. EDIT target_cell transforms, target_value stays.
    """
    if action["kind"] == "noop":
        return {"kind": "noop", "target_cell": None, "target_value": None}
    # EDIT
    old_cell = action["target_cell"]
    new_cell = transform_index(old_cell, element)
    return {
        "kind": "edit",
        "target_cell": new_cell,
        "target_value": action["target_value"],
    }


def transform_pair(pair: dict, element: D4) -> dict:
    """Transform a full pair payload under D4 element."""
    return {
        "grid81": list(transform_grid81(tuple(pair["grid81"]), element)),
        "writable_mask81": list(transform_mask81(tuple(pair["writable_mask81"]), element)),
        "action": transform_action(pair["action"], element),
    }


# --- Composition helpers (must exist before tables use them) ---

def _compose_unchecked(left: D4, right: D4) -> D4:
    """Compute compose(left, right) by checking the composed permutation.

    compose(left, right) means: apply right first, then left.
    We find the unique D4 element whose permutation matches the composition.
    """
    composed_perm = [0] * 81
    right_perm = _PERMUTATION_TABLE[right]
    left_perm = _PERMUTATION_TABLE[left]
    for i in range(81):
        ri = right_perm[i]
        li = left_perm[ri]
        composed_perm[i] = li
    composed_perm = tuple(composed_perm)
    for elem in D4_ELEMENTS:
        if _PERMUTATION_TABLE[elem] == composed_perm:
            return elem
    raise RuntimeError(f"No D4 element matches compose({left}, {right})")


# Pre-computed composition table
_COMPOSE_TABLE: Final[dict[tuple[D4, D4], D4]] = {}
for left in D4_ELEMENTS:
    for right in D4_ELEMENTS:
        result = _compose_unchecked(left, right)
        _COMPOSE_TABLE[(left, right)] = result


def compose(left: D4, right: D4) -> D4:
    """Compose two D4 elements: compose(left, right) = left o right.

    Applies right first, then left.
    """
    return _COMPOSE_TABLE[(left, right)]


# --- Inverse helpers (must exist before _INVERSE_TABLE uses them) ---

def _find_inverse(elem: D4) -> D4:
    """Find the inverse of a D4 element."""
    for other in D4_ELEMENTS:
        if compose(elem, other) == D4.IDENTITY:
            return other
    raise RuntimeError(f"No inverse found for {elem}")


# Pre-computed inverse table
_INVERSE_TABLE: Final[dict[D4, D4]] = {}
for elem in D4_ELEMENTS:
    _INVERSE_TABLE[elem] = _find_inverse(elem)


def inverse(element: D4) -> D4:
    """Return the inverse of a D4 element."""
    return _INVERSE_TABLE[element]


def build_composition_table() -> dict[str, dict[str, str]]:
    """Build the full 8x8 composition table as nested dict of names."""
    table = {}
    for left in D4_ELEMENTS:
        row = {}
        for right in D4_ELEMENTS:
            result = compose(left, right)
            row[right.name] = result.name
        table[left.name] = row
    return table


def build_inverse_table() -> dict[str, str]:
    """Build inverse table as dict of names."""
    return {elem.name: inverse(elem).name for elem in D4_ELEMENTS}
