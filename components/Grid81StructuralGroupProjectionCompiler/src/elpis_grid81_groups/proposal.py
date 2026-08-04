"""StructuralGroupProposalV1 compilation.

Every evidence record gets exactly one proposal. All proposals are admissible.
"""

import json
from typing import Any, Dict, List

from elpis_grid81_groups.canonical import compute_digest, PROPOSAL_DOMAIN


# Fixed admission reason codes (deterministic, sorted)
ADMISSION_REASON_CODES = [
    'CANONICAL_DIGEST_VALID',
    'DERIVATION_LAW_SATISFIED',
    'SCHEMA_VALID',
    'UPSTREAM_BOUND',
]

# Fixed claims not made
PROPOSAL_CLAIMS_NOT_MADE = [
    'proposal does not select',
    'proposal does not authorize',
    'proposal does not imply lifecycle eligibility',
    'proposal does not permit activation',
    'proposal does not dispatch',
    'proposal does not load models',
    'proposal does not load adapters',
]


def compile_proposal(
    evidence_record: Dict[str, Any],
) -> Dict[str, Any]:
    """Compile a single StructuralGroupProposalV1 from an evidence record."""
    evidence_digest = evidence_record['canonical_payload_digest']
    group_id = evidence_record['group_id']
    group_relevant = evidence_record['group_relevant']

    # Build proposal payload (all fields except proposal_digest)
    payload = {
        'evidence_digest': evidence_digest,
        'group_id': group_id,
        'group_relevant': group_relevant,
        'admissible_for_adjudication': True,
        'admission_reason_codes': ADMISSION_REASON_CODES,
        'claims_not_made': PROPOSAL_CLAIMS_NOT_MADE,
    }

    proposal_digest = compute_digest(PROPOSAL_DOMAIN, payload)

    record = {
        'schema_version': 'structural-group-proposal.v1',
        'evidence_digest': evidence_digest,
        'group_id': group_id,
        'group_relevant': group_relevant,
        'admissible_for_adjudication': True,
        'admission_reason_codes': ADMISSION_REASON_CODES,
        'proposal_digest': proposal_digest,
        'claims_not_made': PROPOSAL_CLAIMS_NOT_MADE,
    }

    return record


def compile_all_proposals(
    evidence_records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compile proposals for all evidence records."""
    return [compile_proposal(e) for e in evidence_records]
