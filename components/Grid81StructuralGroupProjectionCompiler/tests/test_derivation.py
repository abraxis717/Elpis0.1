"""Test evidence derivation laws."""

import os
import sys
import json

BASE = '/mnt/primesauce/Elpis_Canon'
G4_REPORTS = os.path.join(BASE, 'reports', 'G4_0B_1_TypedProjectionCompiler')
PACKAGE = os.path.join(BASE, 'Grid81StructuralGroupProjectionCompiler')
REPORTS = os.path.join(BASE, 'reports', 'G5_0B_StructuralGroupProjectionCompiler')

sys.path.insert(0, os.path.join(PACKAGE, 'src'))

from elpis_grid81_groups.derivation import (
    derive_transition_edit,
    derive_transition_noop,
    derive_expansion_decomposition,
    derive_quiescence,
    derive_rationale_diagnostic,
    FULL_GRID,
)


def test_transition_edit_relevance():
    transition = {'delta_kind': 'EDIT', 'target_cell': 26}
    relevant, cells, witness = derive_transition_edit(transition)
    assert relevant is True
    assert cells == [26]
    assert witness == 'EDIT_TARGET_CELL'


def test_transition_edit_false():
    transition = {'delta_kind': 'NOOP', 'target_cell': None}
    relevant, cells, witness = derive_transition_edit(transition)
    assert relevant is False
    assert cells == list(FULL_GRID)
    assert witness == 'NO_EDIT_FULL_VIEW'


def test_transition_noop_relevance():
    transition = {'delta_kind': 'NOOP', 'target_cell': None}
    relevant, cells, witness = derive_transition_noop(transition)
    assert relevant is True
    assert cells == list(FULL_GRID)
    assert witness == 'NO_DELTA_FULL_VIEW'


def test_transition_noop_false():
    transition = {'delta_kind': 'EDIT', 'target_cell': 10}
    relevant, cells, witness = derive_transition_noop(transition)
    assert relevant is False
    assert cells == [10]
    assert witness == 'EDIT_COUNTEREXAMPLE'


def test_transition_mutual_exclusion():
    transition = {'delta_kind': 'EDIT', 'target_cell': 5}
    te_r, _, _ = derive_transition_edit(transition)
    tn_r, _, _ = derive_transition_noop(transition)
    assert te_r != tn_r


def test_expansion_relevant():
    expansion = {'expansion_cells': [0, 4, 8]}
    relevant, cells, witness = derive_expansion_decomposition(expansion)
    assert relevant is True
    assert cells == [0, 4, 8]
    assert witness == 'TOKEN6_LOCUS'


def test_expansion_not_relevant():
    expansion = {'expansion_cells': []}
    relevant, cells, witness = derive_expansion_decomposition(expansion)
    assert relevant is False
    assert cells == list(FULL_GRID)
    assert witness == 'NO_TOKEN6_FULL_VIEW'


def test_quiescence_relevant():
    quiescence = {'derived_quiescence': True, 'input_grid': [0]*81}
    relevant, cells, witness = derive_quiescence(quiescence)
    assert relevant is True
    assert cells == []
    assert witness == 'ABSENCE_0_AND_6_FULL_VIEW'


def test_quiescence_not_relevant():
    grid = [1]*81
    grid[13] = 6
    grid[26] = 0
    quiescence = {'derived_quiescence': False, 'input_grid': grid}
    relevant, cells, witness = derive_quiescence(quiescence)
    assert relevant is False
    assert 13 in cells
    assert 26 in cells
    assert witness == 'NONQUIESCENT_TOKEN_CELLS'
    assert len(cells) > 0


def test_rationale_relevant():
    rationale = {'rationale_codes': ['VOID_RESOLUTION']}
    transition = {'transition_delta': {'delta_cells': [26]}}
    relevant, cells, witness = derive_rationale_diagnostic(rationale, transition)
    assert relevant is True
    assert cells == [26]
    assert witness == 'RATIONALE_DELTA_CELLS'


def test_rationale_not_relevant():
    rationale = {'rationale_codes': []}
    transition = {'transition_delta': {'delta_cells': [26]}}
    relevant, cells, witness = derive_rationale_diagnostic(rationale, transition)
    assert relevant is False
    assert cells == list(FULL_GRID)
    assert witness == 'NO_RATIONALE_CODES_FULL_VIEW'


def test_cell_80_support_validity():
    """Cell 80 must be a valid supporting cell index."""
    transition = {'delta_kind': 'EDIT', 'target_cell': 80}
    relevant, cells, witness = derive_transition_edit(transition)
    assert cells == [80]
    assert 80 in FULL_GRID

