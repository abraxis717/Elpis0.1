"""ProposalOrderingV1 compilation.

Deterministic ordering of five proposals per row.
Ordering is not selection.
"""

from typing import Any, Dict, List, Tuple

from elpis_grid81_groups.canonical import compute_digest, ORDERING_DOMAIN


ORDERING_CLAIMS_NOT_MADE = [
    'ordering does not select',
    'ordering does not authorize',
    'ordering does not suppress',
    'ordering does not resolve conflict',
    'ordering does not imply execution priority',
]


def compile_ordering(
    source_row_digest: str,
    proposals: List[Dict[str, Any]],
    evidence_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compile a ProposalOrderingV1 for a source row.

    Deterministic ordering:
      1. supporting_cell_count descending
      2. group_id ascending
      3. structural_orbit_digest ascending
      4. proposal_digest ascending
    """
    proposal_digests = [p['proposal_digest'] for p in proposals]

    # Build evidence lookup by digest
    evidence_by_digest = {e['canonical_payload_digest']: e for e in evidence_records}

    # Build sort keys for each proposal
    def sort_key(p):
        e = evidence_by_digest.get(p['evidence_digest'], {})
        supporting_cell_count = e.get('supporting_cell_count', 0)
        group_id = p['group_id']
        structural_orbit_digest = e.get('structural_orbit_digest', '')
        proposal_digest = p['proposal_digest']
        # Negate supporting_cell_count for descending order
        return (-supporting_cell_count, group_id, structural_orbit_digest, proposal_digest)

    ordered = sorted(proposals, key=sort_key)
    ordered_proposal_digests = [p['proposal_digest'] for p in ordered]

    ordering_rule = 'supporting_cell_count desc, group_id asc, structural_orbit_digest asc, proposal_digest asc'

    # Compute ordering digest
    payload = {
        'source_row_digest': source_row_digest,
        'proposal_digests': proposal_digests,
        'ordered_proposal_digests': ordered_proposal_digests,
        'ordering_rule': ordering_rule,
        'claims_not_made': ORDERING_CLAIMS_NOT_MADE,
    }
    ordering_digest = compute_digest(ORDERING_DOMAIN, payload)

    record = {
        'schema_version': 'proposal-ordering.v1',
        'source_row_digest': source_row_digest,
        'proposal_digests': proposal_digests,
        'ordered_proposal_digests': ordered_proposal_digests,
        'ordering_rule': ordering_rule,
        'ordering_digest': ordering_digest,
        'claims_not_made': ORDERING_CLAIMS_NOT_MADE,
    }

    return record


def compile_all_orderings(
    joined_rows: List[Dict[str, Any]],
    evidence_records: List[Dict[str, Any]],
    proposals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compile orderings for all rows. Assumes evidence/proposals are in row-major order."""
    orderings = []
    evidence_idx = 0
    proposal_idx = 0
    for row in joined_rows:
        row_evidence = evidence_records[evidence_idx:evidence_idx + 5]
        row_proposals = proposals[proposal_idx:proposal_idx + 5]
        ordering = compile_ordering(
            row['source_row_digest'],
            row_proposals,
            row_evidence,
        )
        orderings.append(ordering)
        evidence_idx += 5
        proposal_idx += 5
    return orderings
