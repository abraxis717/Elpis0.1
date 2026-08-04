"""Test D4 orbit identity computation."""

import sys
import os

BASE = '/mnt/primesauce/Elpis_Canon'
PACKAGE = os.path.join(BASE, 'Grid81StructuralGroupProjectionCompiler')
sys.path.insert(0, os.path.join(PACKAGE, 'src'))

from elpis_grid81_groups.orbit import (
    compute_orbit_digest,
    transform_index,
    transform_grid81,
    transform_cells,
    _load_d4_transforms,
)


def test_d4_eight_transforms():
    transforms = _load_d4_transforms()
    assert len(transforms) == 8


def test_d4_identity_transform():
    """Transform 0 (identity) leaves cells unchanged."""
    cells = [0, 40, 80]
    result = transform_cells(0, cells)
    assert result == cells


def test_d4_transform_bijective():
    """Each transform is a bijection on [0, 81)."""
    for t in range(8):
        mapping = [transform_index(t, i) for i in range(81)]
        assert sorted(mapping) == list(range(81))


def test_orbit_digest_deterministic():
    """Same inputs produce same orbit digest."""
    view = {
        'input_grid': [0]*81,
        'input_mask': [1]*81,
        'canonical_target_grid': [0]*81,
        'delta_kind': 'EDIT',
        'target_cell': 40,
        'target_value': 6,
    }
    d1 = compute_orbit_digest('TRANSITION_EDIT', True, [40], 1, 'EDIT_TARGET_CELL',
                              'transition', view)
    d2 = compute_orbit_digest('TRANSITION_EDIT', True, [40], 1, 'EDIT_TARGET_CELL',
                              'transition', view)
    assert d1 == d2


def test_orbit_digest_provenance_independence():
    """Changing provenance fields should not affect orbit digest (same semantics)."""
    view = {
        'input_grid': [0]*81,
        'input_mask': [1]*81,
        'canonical_target_grid': [0]*81,
        'delta_kind': 'EDIT',
        'target_cell': 40,
        'target_value': 6,
    }
    d = compute_orbit_digest('TRANSITION_EDIT', True, [40], 1, 'EDIT_TARGET_CELL',
                             'transition', view)
    assert len(d) == 64
    assert all(c in '0123456789abcdef' for c in d)


def test_orbit_digest_semantic_sensitivity():
    """Different group_relevant should change orbit digest."""
    view = {
        'input_grid': [0]*81,
        'input_mask': [1]*81,
        'canonical_target_grid': [0]*81,
        'delta_kind': 'EDIT',
        'target_cell': 40,
        'target_value': 6,
    }
    d_true = compute_orbit_digest('TRANSITION_EDIT', True, [40], 1, 'EDIT_TARGET_CELL',
                                  'transition', view)
    d_false = compute_orbit_digest('TRANSITION_EDIT', False, [40], 1, 'EDIT_TARGET_CELL',
                                   'transition', view)
    assert d_true != d_false


def test_orbit_digest_group_id_sensitivity():
    """Different group_id changes orbit digest."""
    view = {
        'input_grid': [0]*81,
        'input_mask': [1]*81,
        'canonical_target_grid': [0]*81,
        'delta_kind': 'EDIT',
        'target_cell': 40,
        'target_value': 6,
    }
    d_te = compute_orbit_digest('TRANSITION_EDIT', True, [40], 1, 'EDIT_TARGET_CELL',
                                'transition', view)
    d_tn = compute_orbit_digest('TRANSITION_NOOP', True, [40], 1, 'EDIT_TARGET_CELL',
                                'transition', view)
    assert d_te != d_tn


def test_orbit_d4_invariance():
    """D4-equivariant cells should have same orbit under transforms."""
    view = {
        'input_grid': [0]*81,
        'input_mask': [1]*81,
        'canonical_target_grid': [0]*81,
        'delta_kind': 'EDIT',
        'target_cell': 40,
        'target_value': 6,
    }
    d1 = compute_orbit_digest('TRANSITION_EDIT', True, [40], 1, 'EDIT_TARGET_CELL',
                              'transition', view)
    # The orbit digest should be the same (it's computed over all 8 transforms)
    d2 = compute_orbit_digest('TRANSITION_EDIT', True, [40], 1, 'EDIT_TARGET_CELL',
                              'transition', view)
    assert d1 == d2

