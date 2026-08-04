"""Source inventory join across all five G4.0B.1 typed view inventories.

Joins by source_row_digest. Verifies exact set equality across all five views.
"""

import json
from typing import Any, Dict, List, Tuple


def read_inventory(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def join_inventories(
    identity_path: str,
    transition_path: str,
    expansion_path: str,
    quiescence_path: str,
    rationale_path: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Join all five inventories by source_row_digest.

    Returns (joined_rows, audit_report).
    """
    identities = read_inventory(identity_path)
    transitions = read_inventory(transition_path)
    expansions = read_inventory(expansion_path)
    quiescences = read_inventory(quiescence_path)
    rationales = read_inventory(rationale_path)

    # Index by source_row_digest
    identity_map = {r['source_row_digest']: r for r in identities}
    transition_map = {r['source_row_digest']: r for r in transitions}
    expansion_map = {r['source_row_digest']: r for r in expansions}
    quiescence_map = {r['source_row_digest']: r for r in quiescences}
    rationale_map = {r['source_row_digest']: r for r in rationales}

    identity_digests = set(identity_map.keys())
    transition_digests = set(transition_map.keys())
    expansion_digests = set(expansion_map.keys())
    quiescence_digests = set(quiescence_map.keys())
    rationale_digests = set(rationale_map.keys())

    all_digests = identity_digests | transition_digests | expansion_digests | quiescence_digests | rationale_digests

    # Check set equality
    sets_equal = (
        identity_digests == transition_digests
        and identity_digests == expansion_digests
        and identity_digests == quiescence_digests
        and identity_digests == rationale_digests
    )

    # Check for duplicates within each inventory
    identity_unique = len(identities) == len(identity_digests)
    transition_unique = len(transitions) == len(transition_digests)
    expansion_unique = len(expansions) == len(expansion_digests)
    quiescence_unique = len(quiescences) == len(quiescence_digests)
    rationale_unique = len(rationales) == len(rationale_digests)

    # Check no orphans
    no_missing = (
        len(all_digests - identity_digests) == 0
        and len(all_digests - transition_digests) == 0
        and len(all_digests - expansion_digests) == 0
        and len(all_digests - quiescence_digests) == 0
        and len(all_digests - rationale_digests) == 0
    )

    joined_rows = []
    for digest in sorted(identity_digests):
        joined_rows.append({
            'source_row_digest': digest,
            'identity': identity_map[digest],
            'transition': transition_map[digest],
            'expansion': expansion_map[digest],
            'quiescence': quiescence_map[digest],
            'rationale': rationale_map[digest],
        })

    status = 'SOURCE_JOIN_VERIFIED' if (
        sets_equal
        and identity_unique and transition_unique and expansion_unique
        and quiescence_unique and rationale_unique
        and no_missing
        and len(joined_rows) == 8192
    ) else 'SOURCE_JOIN_FAILED'

    audit = {
        'status': status,
        'identity_count': len(identities),
        'transition_count': len(transitions),
        'expansion_count': len(expansions),
        'quiescence_count': len(quiescences),
        'rationale_count': len(rationales),
        'unique_source_identities': len(identity_digests),
        'unique_transition_views': len(transition_digests),
        'unique_expansion_views': len(expansion_digests),
        'unique_quiescence_views': len(quiescence_digests),
        'unique_rationale_views': len(rationale_digests),
        'digest_set_equality': sets_equal,
        'no_duplicates': identity_unique and transition_unique and expansion_unique and quiescence_unique and rationale_unique,
        'no_missing_rows': no_missing,
        'no_orphan_views': no_missing,
        'no_cross_row_digest_reuse': no_missing,
        'joined_row_count': len(joined_rows),
    }

    return joined_rows, audit
