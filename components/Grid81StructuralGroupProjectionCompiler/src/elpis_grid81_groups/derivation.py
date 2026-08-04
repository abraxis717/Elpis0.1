"""Structural relevance and witness derivation laws.

Implements the five group derivation laws from G5.0A:
  TRANSITION_EDIT, TRANSITION_NOOP, EXPANSION_DECOMPOSITION, QUIESCENCE, RATIONALE_DIAGNOSTIC

FULL_GRID = [0, 1, ..., 80]
"""

FULL_GRID = list(range(81))


def derive_transition_edit(transition: dict):
    """TRANSITION_EDIT relevance and witness.

    Relevant iff transition.delta_kind == 'EDIT'.
    When true: supporting_cells = [target_cell], witness = EDIT_TARGET_CELL
    When false: supporting_cells = FULL_GRID, witness = NO_EDIT_FULL_VIEW
    """
    delta_kind = transition['delta_kind']
    group_relevant = delta_kind == 'EDIT'
    if group_relevant:
        supporting_cells = [transition['target_cell']]
        witness_kind = 'EDIT_TARGET_CELL'
    else:
        supporting_cells = list(FULL_GRID)
        witness_kind = 'NO_EDIT_FULL_VIEW'
    return group_relevant, supporting_cells, witness_kind


def derive_transition_noop(transition: dict):
    """TRANSITION_NOOP relevance and witness.

    Relevant iff transition.delta_kind == 'NOOP'.
    When true: supporting_cells = FULL_GRID, witness = NO_DELTA_FULL_VIEW
    When false: supporting_cells = [target_cell], witness = EDIT_COUNTEREXAMPLE
    """
    delta_kind = transition['delta_kind']
    group_relevant = delta_kind == 'NOOP'
    if group_relevant:
        supporting_cells = list(FULL_GRID)
        witness_kind = 'NO_DELTA_FULL_VIEW'
    else:
        supporting_cells = [transition['target_cell']]
        witness_kind = 'EDIT_COUNTEREXAMPLE'
    return group_relevant, supporting_cells, witness_kind


def derive_expansion_decomposition(expansion: dict):
    """EXPANSION_DECOMPOSITION relevance and witness.

    Relevant iff len(expansion.expansion_cells) > 0.
    When true: supporting_cells = sorted(expansion_cells), witness = TOKEN6_LOCUS
    When false: supporting_cells = FULL_GRID, witness = NO_TOKEN6_FULL_VIEW
    """
    expansion_cells = expansion['expansion_cells']
    group_relevant = len(expansion_cells) > 0
    if group_relevant:
        supporting_cells = sorted(expansion_cells)
        witness_kind = 'TOKEN6_LOCUS'
    else:
        supporting_cells = list(FULL_GRID)
        witness_kind = 'NO_TOKEN6_FULL_VIEW'
    return group_relevant, supporting_cells, witness_kind


def derive_quiescence(quiescence: dict):
    """QUIESCENCE relevance and witness.

    Relevant iff quiescence.derived_quiescence == true.
    When true: supporting_cells = [], witness = ABSENCE_0_AND_6_FULL_VIEW
    When false: supporting_cells = sorted indices i where input_grid[i] in {0, 6}
    """
    derived = quiescence['derived_quiescence']
    group_relevant = derived is True
    if group_relevant:
        supporting_cells = []
        witness_kind = 'ABSENCE_0_AND_6_FULL_VIEW'
    else:
        input_grid = quiescence['input_grid']
        supporting_cells = sorted([i for i, v in enumerate(input_grid) if v in (0, 6)])
        witness_kind = 'NONQUIESCENT_TOKEN_CELLS'
    return group_relevant, supporting_cells, witness_kind


def derive_rationale_diagnostic(rationale: dict, transition: dict):
    """RATIONALE_DIAGNOSTIC relevance and witness.

    Relevant iff len(rationale.rationale_codes) > 0.
    When true and transition delta cells nonempty: supporting_cells = delta_cells
    When true and transition delta cells empty: supporting_cells = FULL_GRID
    When false: supporting_cells = FULL_GRID, witness = NO_RATIONALE_CODES_FULL_VIEW
    """
    rationale_codes = rationale.get('rationale_codes', [])
    group_relevant = len(rationale_codes) > 0

    transition_delta = transition.get('transition_delta', {})
    delta_cells = transition_delta.get('delta_cells', [])

    if group_relevant:
        if len(delta_cells) > 0:
            supporting_cells = sorted(delta_cells)
            witness_kind = 'RATIONALE_DELTA_CELLS'
        else:
            supporting_cells = list(FULL_GRID)
            witness_kind = 'RATIONALE_FULL_VIEW'
    else:
        supporting_cells = list(FULL_GRID)
        witness_kind = 'NO_RATIONALE_CODES_FULL_VIEW'

    return group_relevant, supporting_cells, witness_kind


def derive_all(joined_row: dict):
    """Derive all five evidence records for a single joined row.

    Returns list of (group_id, group_relevant, supporting_cells, witness_kind).
    """
    transition = joined_row['transition']
    expansion = joined_row['expansion']
    quiescence = joined_row['quiescence']
    rationale = joined_row['rationale']

    results = []

    te_relevant, te_cells, te_witness = derive_transition_edit(transition)
    results.append(('TRANSITION_EDIT', te_relevant, te_cells, te_witness))

    tn_relevant, tn_cells, tn_witness = derive_transition_noop(transition)
    results.append(('TRANSITION_NOOP', tn_relevant, tn_cells, tn_witness))

    ed_relevant, ed_cells, ed_witness = derive_expansion_decomposition(expansion)
    results.append(('EXPANSION_DECOMPOSITION', ed_relevant, ed_cells, ed_witness))

    qu_relevant, qu_cells, qu_witness = derive_quiescence(quiescence)
    results.append(('QUIESCENCE', qu_relevant, qu_cells, qu_witness))

    rd_relevant, rd_cells, rd_witness = derive_rationale_diagnostic(rationale, transition)
    results.append(('RATIONALE_DIAGNOSTIC', rd_relevant, rd_cells, rd_witness))

    return results


# Map from view_type to the G4 D4 transform function name
GROUP_D4_MAP = {
    'TRANSITION_EDIT': 'transition_d4_index_map',
    'TRANSITION_NOOP': 'transition_d4_index_map',
    'EXPANSION_DECOMPOSITION': 'expansion_d4_index_map',
    'QUIESCENCE': 'quiescence_d4_index_map',
    'RATIONALE_DIAGNOSTIC': 'rationale_d4_index_map',
}

# Map from group_id to source view type
GROUP_VIEW_MAP = {
    'TRANSITION_EDIT': 'transition',
    'TRANSITION_NOOP': 'transition',
    'EXPANSION_DECOMPOSITION': 'expansion',
    'QUIESCENCE': 'quiescence',
    'RATIONALE_DIAGNOSTIC': 'rationale',
}
