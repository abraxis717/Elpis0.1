"""Structural D4 orbit identity computation.

Computes structural_orbit_digest for G5.0A evidence records.
Semantic-only: excludes provenance fields. Uses G4 D4 transforms via narrow adapter.
"""

import json
import hashlib
from typing import Any, Dict, List, Tuple

# D4 transforms imported from G4 package — read-only adapter
_D4_TRANSFORMS: List[List[int]] = None


def _load_d4_transforms():
    """Load D4 transform permutations from G4 canonical definitions."""
    global _D4_TRANSFORMS
    if _D4_TRANSFORMS is not None:
        return _D4_TRANSFORMS
    # Reproduce the exact D4 transforms from G4 d4.py (read-only reference)
    def _row_col(idx):
        return idx // 9, idx % 9

    def _linear(row, col):
        return row * 9 + col

    def _build_transform(func):
        perm = [0] * 81
        for i in range(81):
            r, c = _row_col(i)
            nr, nc = func(r, c)
            perm[i] = _linear(nr, nc)
        return perm

    _D4_TRANSFORMS = [
        _build_transform(lambda r, c: (r, c)),                     # e
        _build_transform(lambda r, c: (c, 8 - r)),                # r90
        _build_transform(lambda r, c: (8 - r, 8 - c)),            # r180
        _build_transform(lambda r, c: (8 - c, r)),                # r270
        _build_transform(lambda r, c: (r, 8 - c)),                # fh
        _build_transform(lambda r, c: (8 - r, c)),                # fv
        _build_transform(lambda r, c: (c, r)),                    # fd
        _build_transform(lambda r, c: (8 - c, 8 - r)),            # fa
    ]
    return _D4_TRANSFORMS


def transform_index(t: int, idx: int) -> int:
    transforms = _load_d4_transforms()
    return transforms[t][idx]


def transform_grid81(t: int, grid: List[int]) -> List[int]:
    transforms = _load_d4_transforms()
    perm = transforms[t]
    result = [0] * 81
    for i in range(81):
        result[perm[i]] = grid[i]
    return result


def transform_cells(t: int, cells: List[int]) -> List[int]:
    return sorted([transform_index(t, c) for c in cells])


# ── View transform adapters ───────────────────────────────────────────

def transform_transition_view(t: int, view: Dict[str, Any]) -> Dict[str, Any]:
    """Transform transition view semantics under D4."""
    result = {}
    result['input_grid'] = transform_grid81(t, view['input_grid'])
    result['input_mask'] = list(view['input_mask'])  # mask is all-1, invariant in practice
    result['canonical_target_grid'] = transform_grid81(t, view['canonical_target_grid'])
    result['delta_kind'] = view['delta_kind']  # invariant
    result['target_cell'] = transform_index(t, view['target_cell']) if view.get('target_cell') is not None else None
    result['target_value'] = view.get('target_value')  # invariant
    return result


def transform_expansion_view(t: int, view: Dict[str, Any]) -> Dict[str, Any]:
    """Transform expansion view semantics under D4."""
    result = {}
    result['input_grid'] = transform_grid81(t, view['input_grid'])
    result['expansion_locus_mask81'] = transform_grid81(t, view['expansion_locus_mask81'])
    result['expansion_cells'] = transform_cells(t, view['expansion_cells'])
    return result


def transform_quiescence_view(t: int, view: Dict[str, Any]) -> Dict[str, Any]:
    """Transform quiescence view semantics under D4."""
    result = {}
    result['input_grid'] = transform_grid81(t, view['input_grid'])
    result['derived_quiescence'] = view['derived_quiescence']
    return result


def transform_rationale_view(t: int, view: Dict[str, Any]) -> Dict[str, Any]:
    """Transform rationale view semantics under D4."""
    result = {}
    result['input_grid'] = transform_grid81(t, view['input_grid'])
    result['canonical_target_grid'] = transform_grid81(t, view['canonical_target_grid'])
    result['rationale_codes'] = list(view['rationale_codes'])
    return result


# ── View-to-semantic mapping ──────────────────────────────────────────

VIEW_TRANSFORMS = {
    'transition': transform_transition_view,
    'expansion': transform_expansion_view,
    'quiescence': transform_quiescence_view,
    'rationale': transform_rationale_view,
}

GROUP_VIEW_MAP = {
    'TRANSITION_EDIT': 'transition',
    'TRANSITION_NOOP': 'transition',
    'EXPANSION_DECOMPOSITION': 'expansion',
    'QUIESCENCE': 'quiescence',
    'RATIONALE_DIAGNOSTIC': 'rationale',
}

VIEW_SOURCE_MAP = {
    'transition': 'transition',
    'expansion': 'expansion',
    'quiescence': 'quiescence',
    'rationale': 'rationale',
}


def canonical_json_bytes(obj) -> bytes:
    """Canonical JSON as UTF-8 bytes (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def compute_orbit_digest(
    group_id: str,
    group_relevant: bool,
    supporting_cells: List[int],
    supporting_cell_count: int,
    witness_kind: str,
    source_view_type: str,
    source_view: Dict[str, Any],
) -> str:
    """Compute structural_orbit_digest.

    For each of 8 D4 transforms:
      1. Transform source view
      2. Transform supporting_cells
      3. Build orbit member payload
      4. Canonicalize
    Select lexicographically minimum canonical bytes. Hash with domain separator.
    """
    transform_fn = VIEW_TRANSFORMS[source_view_type]

    canonical_bytes_list = []

    for t in range(8):
        transformed_view = transform_fn(t, source_view)
        transformed_cells = transform_cells(t, supporting_cells)

        orbit_member = {
            'digest_scope': 'D4_STRUCTURAL_GROUP_ORBIT',
            'group_id': group_id,
            'group_relevant': group_relevant,
            'supporting_cells': transformed_cells,
            'supporting_cell_count': supporting_cell_count,
            'witness_kind': witness_kind,
            'source_view_semantics': transformed_view,
        }
        canonical_bytes_list.append(canonical_json_bytes(orbit_member))

    # Select lexicographically minimum
    min_bytes = min(canonical_bytes_list)

    # Hash with domain separator
    separator = b'g5.structural-group-evidence.v1\x00'
    digest = hashlib.sha256(separator + min_bytes).hexdigest()
    return digest
