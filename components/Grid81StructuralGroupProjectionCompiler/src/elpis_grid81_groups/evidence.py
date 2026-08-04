"""StructuralGroupEvidenceV1 compilation.

Compiles evidence records for all five groups across all source rows.
"""

import json
from typing import Any, Dict, List

from elpis_grid81_groups.canonical import canonical_json_bytes, compute_digest, EVIDENCE_DOMAIN
from elpis_grid81_groups.derivation import derive_all, GROUP_VIEW_MAP
from elpis_grid81_groups.orbit import compute_orbit_digest


def compile_evidence_record(
    joined_row: Dict[str, Any],
    group_id: str,
    group_relevant: bool,
    supporting_cells: List[int],
    witness_kind: str,
    source_manifest_sha256: str,
) -> Dict[str, Any]:
    """Compile a single StructuralGroupEvidenceV1 record."""
    source_row_digest = joined_row['source_row_digest']

    # Determine source view type
    view_type_map = {
        'TRANSITION_EDIT': 'transition',
        'TRANSITION_NOOP': 'transition',
        'EXPANSION_DECOMPOSITION': 'expansion',
        'QUIESCENCE': 'quiescence',
        'RATIONALE_DIAGNOSTIC': 'rationale',
    }
    source_view_type = view_type_map[group_id]

    # Get the source view
    view_key = source_view_type
    source_view = joined_row[view_key]

    # Compute source view digest from G4 inventory
    view_digest_field = {
        'transition': 'transition_digest',
        'expansion': 'expansion_view_digest',
        'quiescence': 'quiescence_view_digest',
        'rationale': 'rationale_view_digest',
    }
    source_view_digest = source_view.get(view_digest_field.get(view_key, ''), '')
    if not source_view_digest:
        # Fallback: compute from view data
        source_view_digest = ''

    supporting_cell_count = len(supporting_cells)

    # Compute structural orbit digest
    structural_orbit_digest = compute_orbit_digest(
        group_id=group_id,
        group_relevant=group_relevant,
        supporting_cells=supporting_cells,
        supporting_cell_count=supporting_cell_count,
        witness_kind=witness_kind,
        source_view_type=source_view_type,
        source_view=source_view,
    )

    # Build payload for canonical_payload_digest
    # Excludes the digest field itself
    payload = {
        'source_manifest_sha256': source_manifest_sha256,
        'source_view_digest': source_view_digest,
        'source_row_digest': source_row_digest,
        'source_view_type': source_view_type,
        'group_id': group_id,
        'group_relevant': group_relevant,
        'supporting_cells': supporting_cells,
        'supporting_cell_count': supporting_cell_count,
        'witness_kind': witness_kind,
        'structural_orbit_digest': structural_orbit_digest,
    }

    canonical_payload_digest = compute_digest(EVIDENCE_DOMAIN, payload)

    record = {
        'schema_version': 'structural-group-evidence.v1',
        'source_gate': 'G4.0B.1',
        'source_manifest_sha256': source_manifest_sha256,
        'source_view_type': source_view_type,
        'source_view_digest': source_view_digest,
        'source_row_digest': source_row_digest,
        'group_id': group_id,
        'group_relevant': group_relevant,
        'supporting_cells': supporting_cells,
        'supporting_cell_count': supporting_cell_count,
        'witness_kind': witness_kind,
        'structural_orbit_digest': structural_orbit_digest,
        'canonical_payload_digest': canonical_payload_digest,
    }

    return record


def compile_evidence_for_row(
    joined_row: Dict[str, Any],
    source_manifest_sha256: str,
) -> List[Dict[str, Any]]:
    """Compile all 5 evidence records for a single joined row."""
    derivations = derive_all(joined_row)
    records = []
    for group_id, group_relevant, supporting_cells, witness_kind in derivations:
        record = compile_evidence_record(
            joined_row,
            group_id,
            group_relevant,
            supporting_cells,
            witness_kind,
            source_manifest_sha256,
        )
        records.append(record)
    return records


def compile_all_evidence(
    joined_rows: List[Dict[str, Any]],
    source_manifest_sha256: str,
) -> List[Dict[str, Any]]:
    """Compile evidence for all joined rows."""
    all_evidence = []
    for row in joined_rows:
        row_evidence = compile_evidence_for_row(row, source_manifest_sha256)
        all_evidence.extend(row_evidence)
    return all_evidence
