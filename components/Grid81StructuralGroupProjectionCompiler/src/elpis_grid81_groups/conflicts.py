"""StructuralConflictEvidenceV1 compilation.

Detects three conflict kinds:
  SIMULTANEOUS_RELEVANCE: more than one relevant group per row
  LOGICAL_CONTRADICTION: both TRANSITION_EDIT and TRANSITION_NOOP relevant
  SHARED_SUPPORT: nonempty intersection of supporting cells between relevant proposals
"""

from typing import Any, Dict, List, Set, Tuple

from elpis_grid81_groups.canonical import compute_digest, CONFLICT_DOMAIN


CONFLICT_CLAIMS_NOT_MADE = [
    'conflict evidence does not select a winner',
    'conflict evidence does not resolve the conflict',
    'conflict evidence does not authorize activation',
    'conflict evidence does not imply priority',
]


def compile_simultaneous_relevance(
    source_row_digest: str,
    relevant_proposals: List[Dict[str, Any]],
    relevant_evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """SIMULTANEOUS_RELEVANCE: one record per row when >1 group is relevant."""
    proposal_digests = [p['proposal_digest'] for p in relevant_proposals]
    group_ids = [p['group_id'] for p in relevant_proposals]

    # Shared supporting cells: union of all relevant supporting cells
    all_cells: Set[int] = set()
    for e in relevant_evidence:
        all_cells.update(e['supporting_cells'])
    shared_supporting_cells = sorted(all_cells)

    payload = {
        'source_row_digest': source_row_digest,
        'proposal_digests': proposal_digests,
        'group_ids': group_ids,
        'conflict_kind': 'SIMULTANEOUS_RELEVANCE',
        'shared_supporting_cells': shared_supporting_cells,
        'claims_not_made': CONFLICT_CLAIMS_NOT_MADE,
    }
    digest = compute_digest(CONFLICT_DOMAIN, payload)

    return {
        'schema_version': 'structural-conflict-evidence.v1',
        'source_row_digest': source_row_digest,
        'proposal_digests': proposal_digests,
        'group_ids': group_ids,
        'conflict_kind': 'SIMULTANEOUS_RELEVANCE',
        'shared_supporting_cells': shared_supporting_cells,
        'canonical_conflict_digest': digest,
        'claims_not_made': CONFLICT_CLAIMS_NOT_MADE,
    }


def compile_logical_contradiction(
    source_row_digest: str,
    edit_proposal: Dict[str, Any],
    noop_proposal: Dict[str, Any],
    edit_evidence: Dict[str, Any],
    noop_evidence: Dict[str, Any],
) -> Dict[str, Any]:
    """LOGICAL_CONTRADICTION: both TRANSITION_EDIT and TRANSITION_NOOP relevant.
    
    Should be 0 in canonical corpus but must still detect.
    """
    proposal_digests = [edit_proposal['proposal_digest'], noop_proposal['proposal_digest']]
    proposal_digests.sort()
    group_ids = ['TRANSITION_EDIT', 'TRANSITION_NOOP']

    # Intersection of supporting cells
    edit_cells = set(edit_evidence['supporting_cells'])
    noop_cells = set(noop_evidence['supporting_cells'])
    shared_supporting_cells = sorted(edit_cells & noop_cells)

    payload = {
        'source_row_digest': source_row_digest,
        'proposal_digests': proposal_digests,
        'group_ids': group_ids,
        'conflict_kind': 'LOGICAL_CONTRADICTION',
        'shared_supporting_cells': shared_supporting_cells,
        'claims_not_made': CONFLICT_CLAIMS_NOT_MADE,
    }
    digest = compute_digest(CONFLICT_DOMAIN, payload)

    return {
        'schema_version': 'structural-conflict-evidence.v1',
        'source_row_digest': source_row_digest,
        'proposal_digests': proposal_digests,
        'group_ids': group_ids,
        'conflict_kind': 'LOGICAL_CONTRADICTION',
        'shared_supporting_cells': shared_supporting_cells,
        'canonical_conflict_digest': digest,
        'claims_not_made': CONFLICT_CLAIMS_NOT_MADE,
    }


def compile_shared_support(
    source_row_digest: str,
    proposal_a: Dict[str, Any],
    proposal_b: Dict[str, Any],
    evidence_a: Dict[str, Any],
    evidence_b: Dict[str, Any],
) -> Dict[str, Any]:
    """SHARED_SUPPORT: pairwise record for relevant proposals with overlapping supporting cells."""
    proposal_digests = sorted([proposal_a['proposal_digest'], proposal_b['proposal_digest']])
    group_ids = sorted([proposal_a['group_id'], proposal_b['group_id']])

    cells_a = set(evidence_a['supporting_cells'])
    cells_b = set(evidence_b['supporting_cells'])
    shared = sorted(cells_a & cells_b)

    if not shared:
        return None

    payload = {
        'source_row_digest': source_row_digest,
        'proposal_digests': proposal_digests,
        'group_ids': group_ids,
        'conflict_kind': 'SHARED_SUPPORT',
        'shared_supporting_cells': shared,
        'claims_not_made': CONFLICT_CLAIMS_NOT_MADE,
    }
    digest = compute_digest(CONFLICT_DOMAIN, payload)

    return {
        'schema_version': 'structural-conflict-evidence.v1',
        'source_row_digest': source_row_digest,
        'proposal_digests': proposal_digests,
        'group_ids': group_ids,
        'conflict_kind': 'SHARED_SUPPORT',
        'shared_supporting_cells': shared,
        'canonical_conflict_digest': digest,
        'claims_not_made': CONFLICT_CLAIMS_NOT_MADE,
    }


def compile_conflicts_for_row(
    source_row_digest: str,
    evidence_records: List[Dict[str, Any]],
    proposals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compile all conflict evidence for a single source row."""
    conflicts = []

    # Build lookup maps
    by_group = {e['group_id']: e for e in evidence_records}
    proposal_by_group = {p['group_id']: p for p in proposals}

    # Find relevant groups
    relevant_evidence = [e for e in evidence_records if e['group_relevant']]
    relevant_proposals = [p for p in proposals if p['group_relevant']]

    # SIMULTANEOUS_RELEVANCE: more than one relevant group
    if len(relevant_evidence) > 1:
        conflict = compile_simultaneous_relevance(
            source_row_digest,
            relevant_proposals,
            relevant_evidence,
        )
        conflicts.append(conflict)

    # LOGICAL_CONTRADICTION: both TRANSITION_EDIT and TRANSITION_NOOP relevant
    edit_e = by_group.get('TRANSITION_EDIT')
    noop_e = by_group.get('TRANSITION_NOOP')
    if edit_e and edit_e['group_relevant'] and noop_e and noop_e['group_relevant']:
        conflict = compile_logical_contradiction(
            source_row_digest,
            proposal_by_group['TRANSITION_EDIT'],
            proposal_by_group['TRANSITION_NOOP'],
            edit_e,
            noop_e,
        )
        conflicts.append(conflict)

    # SHARED_SUPPORT: pairwise for relevant proposals
    for i in range(len(relevant_evidence)):
        for j in range(i + 1, len(relevant_evidence)):
            e_a = relevant_evidence[i]
            e_b = relevant_evidence[j]
            p_a = proposal_by_group[e_a['group_id']]
            p_b = proposal_by_group[e_b['group_id']]
            shared = compile_shared_support(
                source_row_digest, p_a, p_b, e_a, e_b
            )
            if shared is not None:
                conflicts.append(shared)

    # Sort conflicts deterministically
    conflicts.sort(key=lambda c: (
        c['source_row_digest'],
        c['conflict_kind'],
        c['group_ids'],
        c['proposal_digests'],
    ))

    return conflicts


def compile_all_conflicts(
    joined_rows: List[Dict[str, Any]],
    evidence_records: List[Dict[str, Any]],
    proposals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compile conflicts for all rows."""
    all_conflicts = []
    idx = 0
    for row in joined_rows:
        row_evidence = evidence_records[idx:idx + 5]
        row_proposals = proposals[idx:idx + 5]
        row_conflicts = compile_conflicts_for_row(
            row['source_row_digest'],
            row_evidence,
            row_proposals,
        )
        all_conflicts.extend(row_conflicts)
        idx += 5
    return all_conflicts
