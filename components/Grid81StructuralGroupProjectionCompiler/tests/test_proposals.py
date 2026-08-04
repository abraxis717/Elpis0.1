"""Test proposal compilation."""

import sys
import os

BASE = '/mnt/primesauce/Elpis_Canon'
PACKAGE = os.path.join(BASE, 'Grid81StructuralGroupProjectionCompiler')
sys.path.insert(0, os.path.join(PACKAGE, 'src'))

from elpis_grid81_groups.proposal import compile_proposal, ADMISSION_REASON_CODES, PROPOSAL_CLAIMS_NOT_MADE


def test_proposal_admissibility():
    evidence = {
        'canonical_payload_digest': 'a' * 64,
        'group_id': 'TRANSITION_EDIT',
        'group_relevant': True,
    }
    proposal = compile_proposal(evidence)
    assert proposal['admissible_for_adjudication'] is True


def test_proposal_negative_relevance_admissible():
    evidence = {
        'canonical_payload_digest': 'b' * 64,
        'group_id': 'TRANSITION_NOOP',
        'group_relevant': False,
    }
    proposal = compile_proposal(evidence)
    assert proposal['admissible_for_adjudication'] is True


def test_proposal_admission_reason_codes():
    evidence = {
        'canonical_payload_digest': 'c' * 64,
        'group_id': 'QUIESCENCE',
        'group_relevant': False,
    }
    proposal = compile_proposal(evidence)
    assert proposal['admission_reason_codes'] == ADMISSION_REASON_CODES
    assert len(proposal['admission_reason_codes']) == 4


def test_proposal_claims_not_made():
    evidence = {
        'canonical_payload_digest': 'd' * 64,
        'group_id': 'EXPANSION_DECOMPOSITION',
        'group_relevant': True,
    }
    proposal = compile_proposal(evidence)
    assert proposal['claims_not_made'] == PROPOSAL_CLAIMS_NOT_MADE
    assert len(proposal['claims_not_made']) > 0


def test_proposal_digest_deterministic():
    evidence = {
        'canonical_payload_digest': 'e' * 64,
        'group_id': 'RATIONALE_DIAGNOSTIC',
        'group_relevant': True,
    }
    p1 = compile_proposal(evidence)
    p2 = compile_proposal(evidence)
    assert p1['proposal_digest'] == p2['proposal_digest']


def test_proposal_group_id_carried():
    evidence = {
        'canonical_payload_digest': 'f' * 64,
        'group_id': 'QUIESCENCE',
        'group_relevant': True,
    }
    proposal = compile_proposal(evidence)
    assert proposal['group_id'] == 'QUIESCENCE'
    assert proposal['group_relevant'] is True

