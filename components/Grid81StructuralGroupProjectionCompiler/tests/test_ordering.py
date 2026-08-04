"""Test proposal ordering."""

import sys
import os

BASE = '$ELPIS_CANON_ROOT/Elpis_Canon'
PACKAGE = os.path.join(BASE, 'Grid81StructuralGroupProjectionCompiler')
sys.path.insert(0, os.path.join(PACKAGE, 'src'))

from elpis_grid81_groups.ordering import compile_ordering, ORDERING_CLAIMS_NOT_MADE


def test_ordering_permutation():
    group_ids = [
        'TRANSITION_EDIT', 'TRANSITION_NOOP', 'EXPANSION_DECOMPOSITION',
        'QUIESCENCE', 'RATIONALE_DIAGNOSTIC'
    ]
    evidence = []
    proposals = []
    for i in range(5):
        evidence.append({
            'canonical_payload_digest': f'{i:064x}',
            'group_id': group_ids[i],
            'supporting_cells': list(range(5 - i)),
            'supporting_cell_count': 5 - i,
            'structural_orbit_digest': f'{i:064x}o',
        })
        proposals.append({
            'evidence_digest': f'{i:064x}',
            'group_id': group_ids[i],
            'proposal_digest': f'{i:064x}p',
            'group_relevant': True,
        })

    ordering = compile_ordering('test_row', proposals, evidence)
    assert len(ordering['ordered_proposal_digests']) == 5
    assert set(ordering['ordered_proposal_digests']) == set(ordering['proposal_digests'])


def test_ordering_claims_not_made():
    proposals = []
    evidence = []
    ordering = compile_ordering('test_row', proposals, evidence)
    assert ordering['claims_not_made'] == ORDERING_CLAIMS_NOT_MADE


def test_ordering_not_selection():
    proposals = [
        {'evidence_digest': 'a' * 64, 'group_id': 'TRANSITION_EDIT',
         'proposal_digest': 'p1', 'group_relevant': True}
    ]
    evidence = [
        {'canonical_payload_digest': 'a' * 64, 'group_id': 'TRANSITION_EDIT',
         'supporting_cell_count': 1, 'structural_orbit_digest': 'o1'}
    ]
    ordering = compile_ordering('test_row', proposals, evidence)
    assert any('does not select' in c for c in ordering['claims_not_made'])
    assert any('does not authorize' in c for c in ordering['claims_not_made'])

