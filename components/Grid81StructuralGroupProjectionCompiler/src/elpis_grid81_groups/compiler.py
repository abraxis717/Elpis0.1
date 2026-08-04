"""G5.0B compiler orchestration.

Orchestrates the full compilation pipeline:
  upstream seals → source join → evidence → proposals → ordering → conflicts
"""

import json
import os
from typing import Any, Dict, List

from elpis_grid81_groups.canonical import canonical_json
from elpis_grid81_groups.upstream import (
    verify_g4_seal,
    verify_g50a_seal,
    validate_g50a_contract,
    compute_manifest_digest,
    tree_digest,
)
from elpis_grid81_groups.source_join import join_inventories
from elpis_grid81_groups.evidence import compile_all_evidence
from elpis_grid81_groups.proposal import compile_all_proposals
from elpis_grid81_groups.ordering import compile_all_orderings
from elpis_grid81_groups.conflicts import compile_all_conflicts


def write_jsonl(records: List[Dict[str, Any]], path: str):
    """Write canonical JSONL with final newline."""
    with open(path, 'w') as f:
        for record in records:
            f.write(canonical_json(record) + '\n')


def write_json(data: Dict[str, Any], path: str):
    """Write JSON with indentation."""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write('\n')


def compile_row_index(
    joined_rows: List[Dict[str, Any]],
    evidence_records: List[Dict[str, Any]],
    proposals: List[Dict[str, Any]],
    orderings: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build the G50B_ROW_COMPILATION_INDEX.jsonl."""
    # Index conflicts by source_row_digest
    conflict_by_row = {}
    for c in conflicts:
        srd = c['source_row_digest']
        if srd not in conflict_by_row:
            conflict_by_row[srd] = []
        conflict_by_row[srd].append(c)

    index_rows = []
    ev_idx = 0
    prop_idx = 0
    for i, row in enumerate(joined_rows):
        srd = row['source_row_digest']
        row_evidence = evidence_records[ev_idx:ev_idx + 5]
        row_proposals = proposals[prop_idx:prop_idx + 5]

        evidence_digests = [e['canonical_payload_digest'] for e in row_evidence]
        proposal_digests = [p['proposal_digest'] for p in row_proposals]
        relevant_groups = [e['group_id'] for e in row_evidence if e['group_relevant']]

        row_conflicts = conflict_by_row.get(srd, [])
        conflict_digests = [c['canonical_conflict_digest'] for c in row_conflicts]

        ordering = orderings[i]

        index_rows.append({
            'source_row_digest': srd,
            'source_split': row['identity'].get('source_split', 'unknown'),
            'evidence_digests': evidence_digests,
            'proposal_digests': proposal_digests,
            'ordering_digest': ordering['ordering_digest'],
            'conflict_digests': conflict_digests,
            'relevant_group_ids': relevant_groups,
            'evidence_count': len(row_evidence),
            'proposal_count': len(row_proposals),
            'conflict_count': len(row_conflicts),
        })

        ev_idx += 5
        prop_idx += 5

    # Sort by source_row_digest
    index_rows.sort(key=lambda r: r['source_row_digest'])
    return index_rows


def run_compiler(
    base_dir: str,
    g4_reports_dir: str,
    g50a_package_dir: str,
    g50a_reports_dir: str,
    reports_dir: str,
    output_dir: str = None,
) -> Dict[str, Any]:
    """Run the full G5.0B compilation pipeline.

    Returns audit report dict.
    """
    if output_dir is None:
        output_dir = reports_dir

    # ── Step 1: Upstream seals ──────────────────────────────────────
    g4_manifest_path = os.path.join(g4_reports_dir, 'G40B1_RAW_EVIDENCE_MANIFEST.json')
    g50a_manifest_path = os.path.join(g50a_reports_dir, 'G50A_RAW_EVIDENCE_MANIFEST.json')

    g4_seal = verify_g4_seal(g4_manifest_path, g4_reports_dir)
    g50a_seal = verify_g50a_seal(g50a_manifest_path, g50a_reports_dir)

    # Contract source revalidation
    g50a_schema_dir = os.path.join(g50a_package_dir, 'schemas')
    g50a_spec_dir = os.path.join(g50a_package_dir, 'spec')
    contract_validation = validate_g50a_contract(g50a_schema_dir, g50a_spec_dir, g50a_reports_dir)

    # Contract tree digest
    contract_tree_sha = tree_digest(g50a_schema_dir)
    contract_tree_sha2 = tree_digest(g50a_spec_dir)
    import hashlib
    combined_tree = hashlib.sha256((contract_tree_sha + contract_tree_sha2).encode()).hexdigest()

    contract_revalidation = {
        'g4_manifest_sha256': g4_seal['manifest_sha256'],
        'g4_manifest_entries_verified': g4_seal['entries_verified'],
        'g50a_manifest_sha256': g50a_seal['manifest_sha256'],
        'g50a_manifest_entries_verified': g50a_seal['entries_verified'],
        'g50a_contract_tree_sha256': combined_tree,
        'schema_count': contract_validation['schema_count'],
        'schema_validation_status': contract_validation['schema_validation_status'],
        'decision_record_status': contract_validation['decision_record_status'],
        'cell_domain_status': contract_validation['cell_domain_status'],
        'authority_boundary_status': contract_validation['authority_boundary_status'],
    }
    write_json(contract_revalidation, os.path.join(output_dir, 'G50B_CONTRACT_SOURCE_REVALIDATION.json'))

    # Upstream seal consumption report
    write_json({
        'g4_seal': g4_seal,
        'g50a_seal': g50a_seal,
    }, os.path.join(output_dir, 'G50B_UPSTREAM_SEAL_CONSUMPTION.json'))

    # ── Step 2: Source join ─────────────────────────────────────────
    # Locate inventories via G4 manifest or direct paths
    identity_path = os.path.join(g4_reports_dir, 'G40B1_SOURCE_IDENTITY_INVENTORY.jsonl')
    transition_path = os.path.join(g4_reports_dir, 'G40B1_TRANSITION_INVENTORY.jsonl')
    expansion_path = os.path.join(g4_reports_dir, 'G40B1_EXPANSION_INVENTORY.jsonl')
    quiescence_path = os.path.join(g4_reports_dir, 'G40B1_QUIESCENCE_INVENTORY.jsonl')
    rationale_path = os.path.join(g4_reports_dir, 'G40B1_RATIONALE_INVENTORY.jsonl')

    joined_rows, join_audit = join_inventories(
        identity_path, transition_path, expansion_path, quiescence_path, rationale_path
    )
    write_json(join_audit, os.path.join(output_dir, 'G50B_SOURCE_JOIN_AUDIT.json'))

    # ── Step 3: Evidence compilation ────────────────────────────────
    source_manifest_sha = g4_seal['manifest_sha256']

    evidence_records = compile_all_evidence(joined_rows, source_manifest_sha)

    # Compute relevance counts
    counts_by_group = {}
    true_counts = {}
    for group_id in ['TRANSITION_EDIT', 'TRANSITION_NOOP', 'EXPANSION_DECOMPOSITION', 'QUIESCENCE', 'RATIONALE_DIAGNOSTIC']:
        group_records = [e for e in evidence_records if e['group_id'] == group_id]
        true_count = sum(1 for e in group_records if e['group_relevant'])
        false_count = sum(1 for e in group_records if not e['group_relevant'])
        counts_by_group[group_id] = {'true': true_count, 'false': false_count}
        true_counts[group_id] = true_count

    evidence_audit = {
        'total_records': len(evidence_records),
        'records_per_row': 5,
        'total_rows': len(joined_rows),
        'relevance_counts': counts_by_group,
        'transition_edit_true': true_counts['TRANSITION_EDIT'],
        'transition_noop_true': true_counts['TRANSITION_NOOP'],
        'transition_mutual_exclusion': (
            true_counts['TRANSITION_EDIT'] + true_counts['TRANSITION_NOOP'] == len(joined_rows)
        ),
        'explicit_negative_evidence': True,
        'explicit_quiescence_evidence': len([e for e in evidence_records if e['group_id'] == 'QUIESCENCE']) == len(joined_rows),
    }
    write_json(evidence_audit, os.path.join(output_dir, 'G50B_EVIDENCE_COMPILER_AUDIT.json'))

    # ── Step 4: Proposal compilation ────────────────────────────────
    proposals = compile_all_proposals(evidence_records)

    proposal_audit = {
        'total_proposals': len(proposals),
        'proposals_per_row': 5,
        'all_admissible': all(p['admissible_for_adjudication'] for p in proposals),
    }
    write_json(proposal_audit, os.path.join(output_dir, 'G50B_PROPOSAL_COMPILER_AUDIT.json'))

    # ── Step 5: Ordering compilation ────────────────────────────────
    orderings = compile_all_orderings(joined_rows, evidence_records, proposals)

    ordering_audit = {
        'total_orderings': len(orderings),
        'all_permutations': all(
            sorted(o['proposal_digests']) == sorted(o['ordered_proposal_digests'])
            for o in orderings
        ),
        'all_length_5': all(len(o['ordered_proposal_digests']) == 5 for o in orderings),
    }
    write_json(ordering_audit, os.path.join(output_dir, 'G50B_ORDERING_AUDIT.json'))

    # ── Step 6: Conflict compilation ────────────────────────────────
    conflicts = compile_all_conflicts(joined_rows, evidence_records, proposals)

    # Count by kind
    conflict_counts = {}
    for c in conflicts:
        kind = c['conflict_kind']
        conflict_counts[kind] = conflict_counts.get(kind, 0) + 1

    logical_contradictions = conflict_counts.get('LOGICAL_CONTRADICTION', 0)

    conflict_audit = {
        'total_conflicts': len(conflicts),
        'conflict_counts_by_kind': conflict_counts,
        'logical_contradictions': logical_contradictions,
    }
    write_json(conflict_audit, os.path.join(output_dir, 'G50B_CONFLICT_AUDIT.json'))

    # ── Step 7: Row compilation index ───────────────────────────────
    row_index = compile_row_index(joined_rows, evidence_records, proposals, orderings, conflicts)

    # ── Step 8: Write canonical inventories ──────────────────────────
    # Sort by source_row_digest, group_id
    evidence_sorted = sorted(evidence_records, key=lambda e: (e['source_row_digest'], e['group_id']))
    proposals_sorted = sorted(proposals, key=lambda p: (
        # Need to map proposal → source_row_digest via evidence
        # We'll use the evidence index
        0, p['group_id']
    ))

    # For proposal sorting, we need source_row_digest. Rebuild from evidence.
    evidence_by_digest = {e['canonical_payload_digest']: e for e in evidence_records}
    proposals_with_row = []
    for p in proposals:
        e = evidence_by_digest.get(p['evidence_digest'])
        srd = e['source_row_digest'] if e else ''
        proposals_with_row.append((srd, p['group_id'], p))
    proposals_with_row.sort()
    proposals_sorted = [p for _, _, p in proposals_with_row]

    # Ordering sort
    orderings_sorted = sorted(orderings, key=lambda o: o['source_row_digest'])

    # Conflicts sort
    conflicts_sorted = sorted(conflicts, key=lambda c: (
        c['source_row_digest'],
        c['conflict_kind'],
        c['group_ids'],
        c['proposal_digests'],
    ))

    write_jsonl(evidence_sorted, os.path.join(output_dir, 'G50B_STRUCTURAL_GROUP_EVIDENCE_INVENTORY.jsonl'))
    write_jsonl(proposals_sorted, os.path.join(output_dir, 'G50B_STRUCTURAL_GROUP_PROPOSAL_INVENTORY.jsonl'))
    write_jsonl(orderings_sorted, os.path.join(output_dir, 'G50B_PROPOSAL_ORDERING_INVENTORY.jsonl'))
    write_jsonl(conflicts_sorted, os.path.join(output_dir, 'G50B_STRUCTURAL_CONFLICT_INVENTORY.jsonl'))
    write_jsonl(row_index, os.path.join(output_dir, 'G50B_ROW_COMPILATION_INDEX.jsonl'))

    # ── Return summary ──────────────────────────────────────────────
    return {
        'g4_seal_status': g4_seal['status'],
        'g50a_seal_status': g50a_seal['status'],
        'source_join_status': join_audit['status'],
        'evidence_count': len(evidence_records),
        'proposal_count': len(proposals),
        'ordering_count': len(orderings),
        'conflict_count': len(conflicts),
        'row_index_count': len(row_index),
        'relevance_counts': counts_by_group,
        'logical_contradictions': logical_contradictions,
    }
