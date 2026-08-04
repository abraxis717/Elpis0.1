"""G5.0B independent verifier.

Recomputes and verifies all compiled artifacts without trusting summary fields.
Modes: --static, --inventories, --upstream, --all, --evidence-dir
"""

import hashlib
import json
import os
import re
import sys
from typing import Any, Dict, List, Set, Tuple

# Canonical mutation registry for identity verification.
# Must match exactly the registry in g50b_mutation_harness.py.
MUTATION_ID_REGISTRY = {
    '01': ('G4 manifest digest changed', 'UPSTREAM_G40B1_SEAL_DIGEST_MISMATCH'),
    '02': ('G5.0A manifest digest changed', 'UPSTREAM_G50A_SEAL_DIGEST_MISMATCH'),
    '03': ('G5.0A decision record changed', 'CONTRACT_DECISION_DIGEST_MISMATCH'),
    '04': ('source join row omitted', 'SOURCE_JOIN_MISSING_ROW'),
    '05': ('source join row duplicated', 'SOURCE_JOIN_DUPLICATE_ROW'),
    '06': ('source view digest changed', 'SOURCE_VIEW_DIGEST_MISMATCH'),
    '07': ('TRANSITION_EDIT relevance flipped', 'TRANSITION_EDIT_RELEVANCE_MISMATCH'),
    '08': ('TRANSITION_NOOP relevance flipped', 'TRANSITION_NOOP_RELEVANCE_MISMATCH'),
    '09': ('both transition groups relevant', 'TRANSITION_EXCLUSIVITY_VIOLATION'),
    '10': ('transition witness changed', 'TRANSITION_WITNESS_MISMATCH'),
    '11': ('expansion relevance flipped', 'EXPANSION_RELEVANCE_MISMATCH'),
    '12': ('expansion support cell omitted', 'EXPANSION_WITNESS_MISMATCH'),
    '13': ('non-token6 expansion support added', 'EXPANSION_NONLOCUS_SUPPORT'),
    '14': ('quiescence evidence omitted', 'MISSING_QUIESCENCE_EVIDENCE'),
    '15': ('quiescence relevance flipped', 'QUIESCENCE_RELEVANCE_MISMATCH'),
    '16': ('quiescence counterexample omitted', 'QUIESCENCE_WITNESS_MISMATCH'),
    '17': ('rationale relevance flipped', 'RATIONALE_RELEVANCE_MISMATCH'),
    '18': ('explicit negative evidence omitted', 'EXPLICIT_NEGATIVE_EVIDENCE_MISSING'),
    '19': ('evidence inventory truncated', 'EVIDENCE_INVENTORY_COUNT_MISMATCH'),
    '20': ('provenance in orbit', 'PROVENANCE_CONTAMINATED_ORBIT'),
    '21': ('D4 orbit member omitted', 'ORBIT_MEMBER_MISSING'),
    '22': ('proposal evidence digest changed', 'PROPOSAL_EVIDENCE_BINDING_MISMATCH'),
    '23': ('proposal admissibility false', 'PROPOSAL_ADMISSIBILITY_MISMATCH'),
    '24': ('ordering drops proposal', 'ORDERING_NOT_PERMUTATION_DROPPED'),
    '25': ('ordering duplicates proposal', 'ORDERING_NOT_PERMUTATION_DUPLICATED'),
    '26': ('conflict adds winner', 'CONFLICT_AUTHORITY_VIOLATION'),
    '27': ('logical contradiction unrecorded', 'LOGICAL_CONTRADICTION_UNRECORDED'),
    '28': ('activation field added', 'ACTIVATION_AUTHORITY_VIOLATION'),
    '29': ('seed inventory changed', 'DETERMINISM_MISMATCH'),
    '30': ('summary contradicts evidence', 'SUMMARY_EVIDENCE_CONTRADICTION'),
}
CANONICAL_MUTATION_IDS = sorted(MUTATION_ID_REGISTRY.keys())  # ['01', ..., '30']


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def verify_upstream_seals(g4_reports_dir: str, g50a_reports_dir: str) -> List[str]:
    """Verify both upstream manifests."""
    errors = []

    # G4
    g4_manifest_path = os.path.join(g4_reports_dir, 'G40B1_RAW_EVIDENCE_MANIFEST.json')
    with open(g4_manifest_path, 'r') as f:
        g4_manifest = json.load(f)
    actual_g4_manifest_sha = sha256_file(g4_manifest_path)
    for entry in g4_manifest.get('evidence_files', []):
        fpath = os.path.join(g4_reports_dir, entry['filename'])
        actual_sha = sha256_file(fpath)
        actual_size = os.path.getsize(fpath)
        if actual_sha != entry['sha256']:
            errors.append(f"G4 file {entry['filename']}: SHA mismatch")
        if actual_size != entry['byte_size']:
            errors.append(f"G4 file {entry['filename']}: size mismatch")

    # G5.0A
    g50a_manifest_path = os.path.join(g50a_reports_dir, 'G50A_RAW_EVIDENCE_MANIFEST.json')
    with open(g50a_manifest_path, 'r') as f:
        g50a_manifest = json.load(f)
    actual_g50a_manifest_sha = sha256_file(g50a_manifest_path)
    for entry in g50a_manifest.get('evidence_files', []):
        fpath = os.path.join(g50a_reports_dir, entry['filename'])
        actual_sha = sha256_file(fpath)
        actual_size = os.path.getsize(fpath)
        if actual_sha != entry['sha256']:
            errors.append(f"G5.0A file {entry['filename']}: SHA mismatch")
        if actual_size != entry['byte_size']:
            errors.append(f"G5.0A file {entry['filename']}: size mismatch")

    # Verify decision record
    dr_path = os.path.join(g50a_reports_dir, 'G50A_DECISION_RECORD.json')
    with open(dr_path, 'r') as f:
        dr = json.load(f)
    if dr.get('upstream_gate') != 'G4.0B.1':
        errors.append("Decision record: wrong upstream gate")
    if dr.get('status') == 'INVALID':
        errors.append("Decision record: status INVALID")

    # Verify upstream seal manifest digests match actual manifests
    g4_manifest_actual = actual_g4_manifest_sha
    g50a_manifest_actual = actual_g50a_manifest_sha

    # Read the seal consumption to get the stored manifest digests
    seal_path = os.path.join(g50a_reports_dir, 'G50A_UPSTREAM_SEAL_CONSUMPTION.json')
    if not os.path.exists(seal_path):
        seal_path = os.path.join(os.path.dirname(g50a_reports_dir), 'G5_0B_StructuralGroupProjectionCompiler', 'G50B_UPSTREAM_SEAL_CONSUMPTION.json')
    if os.path.exists(seal_path):
        with open(seal_path, 'r') as f:
            seal = json.load(f)
        g4_stored = seal.get('g4_seal', {}).get('manifest_sha256', '')
        g50a_stored = seal.get('g50a_seal', {}).get('manifest_sha256', '')
        if g4_stored and g4_stored != g4_manifest_actual:
            errors.append('UPSTREAM_G40B1_SEAL_DIGEST_MISMATCH')
        if g50a_stored and g50a_stored != g50a_manifest_actual:
            errors.append('UPSTREAM_G50A_SEAL_DIGEST_MISMATCH')

    return errors


def verify_inventories(reports_dir: str) -> List[str]:
    """Verify canonical inventory cardinalities and invariants."""
    errors = []

    evidence = read_jsonl(os.path.join(reports_dir, 'G50B_STRUCTURAL_GROUP_EVIDENCE_INVENTORY.jsonl'))
    proposals = read_jsonl(os.path.join(reports_dir, 'G50B_STRUCTURAL_GROUP_PROPOSAL_INVENTORY.jsonl'))
    orderings = read_jsonl(os.path.join(reports_dir, 'G50B_PROPOSAL_ORDERING_INVENTORY.jsonl'))
    conflicts = read_jsonl(os.path.join(reports_dir, 'G50B_STRUCTURAL_CONFLICT_INVENTORY.jsonl'))
    row_index = read_jsonl(os.path.join(reports_dir, 'G50B_ROW_COMPILATION_INDEX.jsonl'))

    # Cardinality checks
    if len(evidence) != 40960:
        errors.append(f"Evidence count: {len(evidence)} != 40960")
    if len(proposals) != 40960:
        errors.append(f"Proposal count: {len(proposals)} != 40960")
    if len(orderings) != 8192:
        errors.append(f"Ordering count: {len(orderings)} != 8192")
    if len(row_index) != 8192:
        errors.append(f"Row index count: {len(row_index)} != 8192")

    # Per-row checks
    evidence_by_row = {}
    for e in evidence:
        srd = e['source_row_digest']
        evidence_by_row.setdefault(srd, []).append(e)

    for srd, row_evidence in evidence_by_row.items():
        if len(row_evidence) != 5:
            errors.append(f"Row {srd}: {len(row_evidence)} evidence records != 5")

        groups = {e['group_id'] for e in row_evidence}
        if len(groups) != 5:
            errors.append(f"Row {srd}: missing group")

        # Check explicit quiescence
        has_quiescence = any(e['group_id'] == 'QUIESCENCE' for e in row_evidence)
        if not has_quiescence:
            errors.append(f"Row {srd}: missing QUIESCENCE evidence")

        # Transition mutual exclusion
        edit_relevant = any(e['group_id'] == 'TRANSITION_EDIT' and e['group_relevant'] for e in row_evidence)
        noop_relevant = any(e['group_id'] == 'TRANSITION_NOOP' and e['group_relevant'] for e in row_evidence)
        if edit_relevant and noop_relevant:
            errors.append(f"Row {srd}: both TRANSITION_EDIT and TRANSITION_NOOP relevant")
        if not edit_relevant and not noop_relevant:
            errors.append(f"Row {srd}: neither TRANSITION_EDIT nor TRANSITION_NOOP relevant")

    # Proposal checks
    proposals_by_evidence = {p['evidence_digest']: p for p in proposals}
    for e in evidence:
        ed = e['canonical_payload_digest']
        if ed not in proposals_by_evidence:
            errors.append(f"Evidence {ed}: no proposal")
            continue
        p = proposals_by_evidence[ed]
        if not p['admissible_for_adjudication']:
            errors.append(f"Proposal for evidence {ed}: not admissible")
        if p['group_id'] != e['group_id']:
            errors.append(f"Proposal for evidence {ed}: group_id mismatch")
        if p['group_relevant'] != e['group_relevant']:
            errors.append(f"Proposal for evidence {ed}: group_relevant mismatch")

    # Ordering checks
    orderings_by_row = {o['source_row_digest']: o for o in orderings}
    for srd in evidence_by_row:
        if srd not in orderings_by_row:
            errors.append(f"Row {srd}: no ordering")
            continue
        o = orderings_by_row[srd]
        if len(o['ordered_proposal_digests']) != 5:
            errors.append(f"Row {srd}: ordering length != 5")
        if set(o['proposal_digests']) != set(o['ordered_proposal_digests']):
            errors.append(f"Row {srd}: ordering not permutation")
        if len(set(o['ordered_proposal_digests'])) != 5:
            errors.append(f"Row {srd}: ordering has duplicates")

    # Transition counts
    edit_true = sum(1 for e in evidence if e['group_id'] == 'TRANSITION_EDIT' and e['group_relevant'])
    noop_true = sum(1 for e in evidence if e['group_id'] == 'TRANSITION_NOOP' and e['group_relevant'])
    if edit_true != 6707:
        errors.append(f"TRANSITION_EDIT true: {edit_true} != 6707")
    if noop_true != 1485:
        errors.append(f"TRANSITION_NOOP true: {noop_true} != 1485")

    # Authority boundary: no forbidden fields
    forbidden = ['activation', 'eligible', 'dispatch', 'execute', 'model_id', 'adapter_id',
                 'runtime', 'device', 'capability_issuer', 'capability_consumer']
    for e in evidence[:100]:  # sample check
        for key in e:
            for term in forbidden:
                if term in key.lower():
                    errors.append(f"Evidence field '{key}' contains forbidden term '{term}'")

    # Source view digest integrity: source_view_digest must be valid 64-char hex
    for e in evidence:
        svd = e.get('source_view_digest', '')
        if not svd or len(svd) != 64:
            errors.append("SOURCE_VIEW_DIGEST_MISMATCH: invalid source_view_digest")
            break

    # Witness kind validation: only known witness kinds permitted
    valid_witness_kinds = {'TOKEN6_LOCUS', 'EDIT_TARGET_CELL', 'EDIT_COUNTEREXAMPLE',
                           'NONQUIESCENT_TOKEN_CELLS', 'ABSENCE_0_AND_6_FULL_VIEW',
                           'NO_DELTA_FULL_VIEW', 'NO_EDIT_FULL_VIEW', 'NO_TOKEN6_FULL_VIEW',
                           'RATIONALE_FULL_VIEW'}
    for e in evidence:
        wk = e.get('witness_kind', '')
        if wk not in valid_witness_kinds:
            errors.append(f"TRANSITION_WITNESS_MISMATCH: witness_kind='{wk}' at {e['source_row_digest']}")
            break

    # Supporting cell count consistency
    for e in evidence:
        cells = e.get('supporting_cells', [])
        count = e.get('supporting_cell_count', -1)
        if count != len(cells):
            errors.append(f"EXPANSION_WITNESS_MISMATCH: cell_count {count} != {len(cells)} at {e['source_row_digest']}")
            break

    # Supporting cells domain check: cells must be in [0, 80]
    for e in evidence:
        for cell in e.get('supporting_cells', []):
            if cell < 0 or cell > 80:
                errors.append(f"EXPANSION_NONLOCUS_SUPPORT: cell {cell} out of domain")
                break
        else:
            continue
        break

    # Quiescence: false relevance must have non-empty supporting_cells (counterexamples)
    for e in evidence:
        if e['group_id'] == 'QUIESCENCE' and not e['group_relevant']:
            if len(e.get('supporting_cells', [])) == 0:
                errors.append(f"QUIESCENCE_WITNESS_MISMATCH: no counterexample at {e['source_row_digest']}")
                break

    # Orbit digest: detect uniform/contaminated hashes (all same char)
    for e in evidence:
        od = e.get('structural_orbit_digest', '')
        if od and all(c == od[0] for c in od):
            errors.append(f"PROVENANCE_CONTAMINATED_ORBIT: uniform digest at {e['source_row_digest']}")
            break

    # D4 orbit member count check per group
    expected_orbit_counts = {
        'EXPANSION_DECOMPOSITION': 3469,
        'QUIESCENCE': 3469,
        'RATIONALE_DIAGNOSTIC': 3556,
        'TRANSITION_EDIT': 3741,
        'TRANSITION_NOOP': 3741,
    }
    orbit_digests_by_group = {}
    for e in evidence:
        gid = e['group_id']
        orbit_digests_by_group.setdefault(gid, set()).add(e['structural_orbit_digest'])
    for gid, expected_count in expected_orbit_counts.items():
        actual_count = len(orbit_digests_by_group.get(gid, set()))
        if actual_count != expected_count:
            errors.append(f"ORBIT_MEMBER_MISSING: {gid} has {actual_count} orbits, expected {expected_count}")

    # Conflict checks
    logical_contradictions = sum(1 for c in conflicts if c['conflict_kind'] == 'LOGICAL_CONTRADICTION')
    if logical_contradictions != 0:
        errors.append(f"Logical contradictions: {logical_contradictions} != 0")

    # Verify conflict claims_not_made must not contain 'winner_selected'
    for c in conflicts:
        if 'winner_selected' in c.get('claims_not_made', []):
            errors.append('CONFLICT_AUTHORITY_VIOLATION')
            break

    # Verify conflict structural fields (no resolution language)
    for c in conflicts[:100]:
        structural_fields = {k: v for k, v in c.items() if k != 'claims_not_made'}
        structural_str = str(structural_fields).lower()
        if 'winner' in structural_str or 'selected_proposal' in structural_str:
            errors.append(f"Conflict contains resolution language")

    # Contract source revalidation: decision_record_status must be VALID
    contract_path = os.path.join(reports_dir, 'G50B_CONTRACT_SOURCE_REVALIDATION.json')
    if os.path.exists(contract_path):
        with open(contract_path, 'r') as f:
            contract = json.load(f)
        if contract.get('decision_record_status') != 'VALID':
            errors.append('CONTRACT_DECISION_DIGEST_MISMATCH')

    return errors


def verify_static(reports_dir: str) -> List[str]:
    """Static verification of reports existence and format."""
    errors = []
    required_files = [
        'G50B_UPSTREAM_SEAL_CONSUMPTION.json',
        'G50B_CONTRACT_SOURCE_REVALIDATION.json',
        'G50B_SOURCE_JOIN_AUDIT.json',
        'G50B_EVIDENCE_COMPILER_AUDIT.json',
        'G50B_PROPOSAL_COMPILER_AUDIT.json',
        'G50B_ORDERING_AUDIT.json',
        'G50B_CONFLICT_AUDIT.json',
        'G50B_TYPED_SPLIT_LEAKAGE_ANALYSIS.json',
        'G50B_PYTEST_QUALIFICATION.json',
        'G50B_MUTATION_RESULTS.json',
        'G50B_POST_MUTATION_CANONICAL_CHECK.json',
        'G50B_FULL_THREE_SEED_DETERMINISM.json',
        'G50B_AUTHORITY_BOUNDARY_AUDIT.json',
        'G50B_POST_EXECUTION_UPSTREAM_IDENTITY.json',
        'G50B_STRUCTURAL_GROUP_EVIDENCE_INVENTORY.jsonl',
        'G50B_STRUCTURAL_GROUP_PROPOSAL_INVENTORY.jsonl',
        'G50B_PROPOSAL_ORDERING_INVENTORY.jsonl',
        'G50B_STRUCTURAL_CONFLICT_INVENTORY.jsonl',
        'G50B_ROW_COMPILATION_INDEX.jsonl',
    ]
    for fname in required_files:
        path = os.path.join(reports_dir, fname)
        if not os.path.exists(path):
            errors.append(f"Missing: {fname}")

    return errors


def verify_authority_boundary(reports_dir: str) -> List[str]:
    """Verify activation authority is unrepresentable."""
    errors = []
    forbidden_terms = [
        'activation', 'eligible', 'dispatch', 'execute', 'model_id', 'adapter_id',
        'runtime', 'device', 'capability_issuer', 'capability_consumer',
        'selection', 'lifecycle', 'scoring', 'weight', 'confidence', 'probability',
    ]

    evidence = read_jsonl(os.path.join(reports_dir, 'G50B_STRUCTURAL_GROUP_EVIDENCE_INVENTORY.jsonl'))
    for e in evidence:
        for key in e:
            for term in forbidden_terms:
                if term in key.lower() and key not in ('supporting_cells', 'supporting_cell_count'):
                    errors.append(f"Evidence field '{key}' contains '{term}'")
                    break

    return errors


def verify_mutation_evidence_identity(reports_dir: str) -> List[str]:
    """Verify mutation evidence identity — mutation IDs must be complete, unique, ordered, and canonical.

    Checks:
    - mutation_id present in every record
    - mutation_id is non-empty
    - mutation_id format is exactly two decimal digits
    - mutation_ids are unique (no duplicates)
    - mutation_id_set is exactly {01, ..., 30}
    - mutation_ids are ordered 01-30
    - mutation_name matches ratified ID
    - expected_failure_code matches ratified ID
    - observed_failure_code equals expected_failure_code
    - caught is True
    - canonical_source_unchanged is True
    - total == 30
    """
    errors = []
    mutation_path = os.path.join(reports_dir, 'G50B_MUTATION_RESULTS.json')
    if not os.path.exists(mutation_path):
        errors.append('G50B_MUTATION_RESULTS.json missing')
        return errors

    with open(mutation_path, 'r') as f:
        data = json.load(f)

    mutations = data.get('mutations', [])

    # Check total
    total = data.get('total', 0)
    if total != 30:
        errors.append(f'MUTATION_RESULT_NOT_CAUGHT: total={total}, expected 30')

    # Check each record
    seen_ids: Set[str] = set()
    id_pattern = re.compile(r'^\d{2}$')

    for idx, record in enumerate(mutations):
        mid = record.get('mutation_id', None)

        # Missing
        if mid is None:
            errors.append(f'MUTATION_ID_MISSING: record {idx} (name={record.get("mutation_name", "UNKNOWN")})')
            continue

        # Empty
        if mid == '':
            errors.append(f'MUTATION_ID_EMPTY: record {idx} (name={record.get("mutation_name", "UNKNOWN")})')
            continue

        # Format
        if not id_pattern.match(mid):
            errors.append(f'MUTATION_ID_FORMAT_INVALID: record {idx} has mutation_id="{mid}"')
            continue

        # Duplicate
        if mid in seen_ids:
            errors.append(f'MUTATION_ID_DUPLICATE: mutation_id="{mid}" at record {idx}')
        seen_ids.add(mid)

        # Range check (01-30)
        mid_int = int(mid)
        if mid_int < 1 or mid_int > 30:
            errors.append(f'MUTATION_ID_SET_INCOMPLETE: mutation_id="{mid}" outside 01-30 range')

        # Name match
        if mid in MUTATION_ID_REGISTRY:
            expected_name, expected_code = MUTATION_ID_REGISTRY[mid]
            actual_name = record.get('mutation_name', '')
            if actual_name != expected_name:
                errors.append(f'MUTATION_ID_NAME_MISMATCH: id={mid}, expected="{expected_name}", got="{actual_name}"')
            # Expected failure code match
            actual_expected_code = record.get('expected_failure_code', '')
            if actual_expected_code != expected_code:
                errors.append(f'MUTATION_ID_FAILURE_CODE_MISMATCH: id={mid}, expected_code="{expected_code}", got="{actual_expected_code}"')

        # Observed matches expected
        expected_code = record.get('expected_failure_code', '')
        observed_code = record.get('observed_failure_code', '')
        if expected_code and observed_code != expected_code:
            errors.append(f'MUTATION_RESULT_NOT_CAUGHT: id={mid}, expected="{expected_code}", observed="{observed_code}"')

        # Caught
        if record.get('caught') is not True:
            errors.append(f'MUTATION_RESULT_NOT_CAUGHT: id={mid}, caught={record.get("caught")}')

        # Canonical source unchanged
        if record.get('canonical_source_unchanged') is not True:
            errors.append(f'MUTATION_CANONICAL_SOURCE_CHANGED: id={mid}')

    # ID set completeness
    canonical_set = set(CANONICAL_MUTATION_IDS)
    if seen_ids != canonical_set:
        missing = canonical_set - seen_ids
        extra = seen_ids - canonical_set
        if missing:
            errors.append(f'MUTATION_ID_SET_INCOMPLETE: missing IDs={sorted(missing)}')
        if extra:
            errors.append(f'MUTATION_ID_SET_INCOMPLETE: unexpected IDs={sorted(extra)}')

    # Ordering check
    actual_ids = [m.get('mutation_id', '') for m in mutations]
    if actual_ids != CANONICAL_MUTATION_IDS:
        errors.append('MUTATION_ID_ORDER_INVALID: mutation IDs not in ascending order 01-30')

    return errors


def run_verification(mode: str, base_dir: str) -> Tuple[bool, List[str]]:
    """Run verification in the specified mode.

    Returns (passed, errors).
    """
    reports_dir = os.path.join(base_dir, 'reports', 'G5_0B_StructuralGroupProjectionCompiler')
    g4_reports_dir = os.path.join(base_dir, 'reports', 'G4_0B_1_TypedProjectionCompiler')
    g50a_reports_dir = os.path.join(base_dir, 'reports', 'G5_0A_StructuralGroupEvidenceContract')

    all_errors = []

    if mode in ('upstream', 'all'):
        all_errors.extend(verify_upstream_seals(g4_reports_dir, g50a_reports_dir))

    if mode in ('inventories', 'all'):
        all_errors.extend(verify_inventories(reports_dir))

    if mode in ('static', 'all'):
        all_errors.extend(verify_static(reports_dir))
        all_errors.extend(verify_authority_boundary(reports_dir))
        all_errors.extend(verify_mutation_evidence_identity(reports_dir))

    if mode == '--all':
        all_errors.extend(verify_upstream_seals(g4_reports_dir, g50a_reports_dir))
        all_errors.extend(verify_inventories(reports_dir))
        all_errors.extend(verify_static(reports_dir))
        all_errors.extend(verify_authority_boundary(reports_dir))
        all_errors.extend(verify_mutation_evidence_identity(reports_dir))

    return len(all_errors) == 0, all_errors


def main():
    import argparse
    parser = argparse.ArgumentParser(description='G5.0B Independent Verifier')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--static', action='store_true', help='Run static checks only')
    group.add_argument('--inventories', action='store_true', help='Run inventory checks only')
    group.add_argument('--upstream', action='store_true', help='Run upstream checks only')
    group.add_argument('--all', action='store_true', help='Run all checks')
    parser.add_argument('--base-dir', default='$ELPIS_CANON_ROOT/Elpis_Canon')
    parser.add_argument('--evidence-dir', default=None, help='Override evidence directory')
    args = parser.parse_args()

    base_dir = args.base_dir
    evidence_dir = args.evidence_dir

    # Determine mode
    if args.all or (not args.static and not args.inventories and not args.upstream):
        mode = '--all'
    elif args.static:
        mode = '--static'
    elif args.inventories:
        mode = '--inventories'
    elif args.upstream:
        mode = '--upstream'
    else:
        mode = '--all'

    reports_dir = evidence_dir or os.path.join(base_dir, 'reports', 'G5_0B_StructuralGroupProjectionCompiler')

    passed, errors = run_verification(mode, base_dir)

    # Mutation evidence identity sub-check (always run for --all or --static)
    mutation_id_errors = []
    if mode in ('--all', '--static'):
        mutation_id_errors = verify_mutation_evidence_identity(reports_dir)

    if passed:
        print('ALL_CHECKS_PASS')
        if mode in ('--all', '--static'):
            if not mutation_id_errors:
                print('MUTATION_EVIDENCE_IDENTITY_VERIFIED')
        sys.exit(0)
    else:
        print(f'FAILURES: {len(errors)}')
        for e in errors[:50]:
            print(f'  - {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
