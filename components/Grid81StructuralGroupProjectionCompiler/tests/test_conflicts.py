"""Test conflict evidence compilation."""

import sys
import os

BASE = '/mnt/primesauce/Elpis_Canon'
PACKAGE = os.path.join(BASE, 'Grid81StructuralGroupProjectionCompiler')
sys.path.insert(0, os.path.join(PACKAGE, 'src'))

from elpis_grid81_groups.conflicts import compile_conflicts_for_row


def test_simultaneous_relevance():
    evidence = [
        {'group_id': 'TRANSITION_EDIT', 'group_relevant': True, 'supporting_cells': [5],
         'canonical_payload_digest': 'a' * 64},
        {'group_id': 'TRANSITION_NOOP', 'group_relevant': False, 'supporting_cells': list(range(81)),
         'canonical_payload_digest': 'b' * 64},
        {'group_id': 'EXPANSION_DECOMPOSITION', 'group_relevant': True, 'supporting_cells': [0, 4],
         'canonical_payload_digest': 'c' * 64},
        {'group_id': 'QUIESCENCE', 'group_relevant': False, 'supporting_cells': [13],
         'canonical_payload_digest': 'd' * 64},
        {'group_id': 'RATIONALE_DIAGNOSTIC', 'group_relevant': False, 'supporting_cells': list(range(81)),
         'canonical_payload_digest': 'e' * 64},
    ]
    proposals = [
        {'group_id': e['group_id'], 'group_relevant': e['group_relevant'],
         'proposal_digest': e['canonical_payload_digest'] + 'p'}
        for e in evidence
    ]
    conflicts = compile_conflicts_for_row('test_row', evidence, proposals)
    # Should have SIMULTANEOUS_RELEVANCE (2 relevant groups)
    kinds = [c['conflict_kind'] for c in conflicts]
    assert 'SIMULTANEOUS_RELEVANCE' in kinds


def test_no_logical_contradiction_in_canonical():
    """Canonical corpus should not have both transition groups relevant."""
    evidence = [
        {'group_id': 'TRANSITION_EDIT', 'group_relevant': True, 'supporting_cells': [5],
         'canonical_payload_digest': 'a' * 64},
        {'group_id': 'TRANSITION_NOOP', 'group_relevant': False, 'supporting_cells': list(range(81)),
         'canonical_payload_digest': 'b' * 64},
        {'group_id': 'EXPANSION_DECOMPOSITION', 'group_relevant': False, 'supporting_cells': list(range(81)),
         'canonical_payload_digest': 'c' * 64},
        {'group_id': 'QUIESCENCE', 'group_relevant': False, 'supporting_cells': [13],
         'canonical_payload_digest': 'd' * 64},
        {'group_id': 'RATIONALE_DIAGNOSTIC', 'group_relevant': False, 'supporting_cells': list(range(81)),
         'canonical_payload_digest': 'e' * 64},
    ]
    proposals = [
        {'group_id': e['group_id'], 'group_relevant': e['group_relevant'],
         'proposal_digest': e['canonical_payload_digest'] + 'p'}
        for e in evidence
    ]
    conflicts = compile_conflicts_for_row('test_row', evidence, proposals)
    kinds = [c['conflict_kind'] for c in conflicts]
    assert 'LOGICAL_CONTRADICTION' not in kinds


def test_shared_support():
    """Relevant groups with overlapping supporting cells should produce SHARED_SUPPORT."""
    evidence = [
        {'group_id': 'TRANSITION_EDIT', 'group_relevant': True, 'supporting_cells': [5],
         'canonical_payload_digest': 'a' * 64},
        {'group_id': 'TRANSITION_NOOP', 'group_relevant': False, 'supporting_cells': list(range(81)),
         'canonical_payload_digest': 'b' * 64},
        {'group_id': 'EXPANSION_DECOMPOSITION', 'group_relevant': True, 'supporting_cells': [5, 10],
         'canonical_payload_digest': 'c' * 64},
        {'group_id': 'QUIESCENCE', 'group_relevant': False, 'supporting_cells': [13],
         'canonical_payload_digest': 'd' * 64},
        {'group_id': 'RATIONALE_DIAGNOSTIC', 'group_relevant': False, 'supporting_cells': list(range(81)),
         'canonical_payload_digest': 'e' * 64},
    ]
    proposals = [
        {'group_id': e['group_id'], 'group_relevant': e['group_relevant'],
         'proposal_digest': e['canonical_payload_digest'] + 'p'}
        for e in evidence
    ]
    conflicts = compile_conflicts_for_row('test_row', evidence, proposals)
    kinds = [c['conflict_kind'] for c in conflicts]
    assert 'SHARED_SUPPORT' in kinds


def test_conflict_no_authority_fields():
    """Conflict records must not contain authority language."""
    evidence = [
        {'group_id': 'TRANSITION_EDIT', 'group_relevant': True, 'supporting_cells': [5],
         'canonical_payload_digest': 'a' * 64},
        {'group_id': 'TRANSITION_NOOP', 'group_relevant': False, 'supporting_cells': list(range(81)),
         'canonical_payload_digest': 'b' * 64},
        {'group_id': 'EXPANSION_DECOMPOSITION', 'group_relevant': False, 'supporting_cells': list(range(81)),
         'canonical_payload_digest': 'c' * 64},
        {'group_id': 'QUIESCENCE', 'group_relevant': False, 'supporting_cells': [13],
         'canonical_payload_digest': 'd' * 64},
        {'group_id': 'RATIONALE_DIAGNOSTIC', 'group_relevant': False, 'supporting_cells': list(range(81)),
         'canonical_payload_digest': 'e' * 64},
    ]
    proposals = [
        {'group_id': e['group_id'], 'group_relevant': e['group_relevant'],
         'proposal_digest': e['canonical_payload_digest'] + 'p'}
        for e in evidence
    ]
    conflicts = compile_conflicts_for_row('test_row', evidence, proposals)
    for c in conflicts:
        assert 'winner' not in c
        assert 'selected_proposal' not in c
        assert 'resolution' not in c
        assert 'priority' not in c

