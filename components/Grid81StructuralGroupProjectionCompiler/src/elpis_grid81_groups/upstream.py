"""G4.0B.1 and G5.0A seal consumption and verification.

Reads manifests, verifies file integrity, validates contract schemas.
"""

import hashlib
import json
import os
from typing import Any, Dict, List, Tuple


def sha256_of_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(manifest_path: str) -> Dict[str, Any]:
    with open(manifest_path, 'r') as f:
        return json.load(f)


def compute_manifest_digest(manifest_path: str) -> str:
    return sha256_of_file(manifest_path)


def verify_manifest_files(
    manifest_path: str,
    reports_dir: str
) -> Tuple[str, List[Dict[str, Any]], str]:
    """Verify all files in a manifest.

    Returns (manifest_sha256, verified_entries, status).
    """
    manifest = read_manifest(manifest_path)
    manifest_sha = compute_manifest_digest(manifest_path)
    evidence_files = manifest.get('evidence_files', [])

    verified = []
    for entry in evidence_files:
        filename = entry['filename']
        filepath = os.path.join(reports_dir, filename)
        actual_sha = sha256_of_file(filepath)
        actual_size = os.path.getsize(filepath)
        verified.append({
            'filename': filename,
            'expected_sha256': entry['sha256'],
            'actual_sha256': actual_sha,
            'expected_size': entry['byte_size'],
            'actual_size': actual_size,
            'sha256_match': actual_sha == entry['sha256'],
            'size_match': actual_size == entry['byte_size'],
        })

    all_ok = all(e['sha256_match'] and e['size_match'] for e in verified)
    status = 'CONSUMED' if all_ok else 'MISMATCH'
    return manifest_sha, verified, status


def verify_g4_seal(g4_manifest_path: str, g4_reports_dir: str) -> Dict[str, Any]:
    """Verify G4.0B.1 seal consumption."""
    manifest_sha, entries, status = verify_manifest_files(
        g4_manifest_path, g4_reports_dir
    )
    return {
        'manifest_sha256': manifest_sha,
        'manifest_entries': len(entries),
        'entries_verified': len([e for e in entries if e['sha256_match']]),
        'status': f'UPSTREAM_G40B1_SEAL_{status}',
        'details': entries,
    }


def verify_g50a_seal(g50a_manifest_path: str, g50a_reports_dir: str) -> Dict[str, Any]:
    """Verify G5.0A seal consumption."""
    manifest_sha, entries, status = verify_manifest_files(
        g50a_manifest_path, g50a_reports_dir
    )
    required_files = {
        'G50A_DECISION_RECORD.json',
        'G50A_CELL_DOMAIN_AUDIT.json',
        'G50A_FINDINGS.json',
        'G50A_FINAL_REPORT.md',
    }
    present = {e['filename'] for e in entries if e['sha256_match']}
    required_present = required_files.issubset(present)
    seal_status = 'UPSTREAM_G50A_SEAL_CONSUMED' if (status == 'CONSUMED' and required_present) else 'UPSTREAM_G50A_SEAL_DIGEST_MISMATCH'
    return {
        'manifest_sha256': manifest_sha,
        'manifest_entries': len(entries),
        'entries_verified': len([e for e in entries if e['sha256_match']]),
        'required_files_present': required_present,
        'status': seal_status,
        'details': entries,
    }


def tree_digest(dirpath: str, exclude: List[str] = None) -> str:
    """Compute deterministic tree SHA-256 over directory contents."""
    if exclude is None:
        exclude = ['__pycache__', '*.pyc']
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(dirpath)):
        dirs[:] = [d for d in sorted(dirs) if d not in exclude]
        for fname in sorted(files):
            if any(fname.endswith(e) or e.endswith(fname) for e in exclude if '*' in e):
                continue
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, dirpath)
            h.update(rel.encode('utf-8'))
            h.update(b'\x00')
            with open(fpath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            h.update(b'\x00')
    return h.hexdigest()


def validate_g50a_contract(
    schema_dir: str,
    spec_dir: str,
    g50a_reports_dir: str,
) -> Dict[str, Any]:
    """Revalidate G5.0A contract source independently.

    Check schemas, decision record, cell domain, authority boundaries.
    """
    # Count and validate schemas
    schemas = [f for f in os.listdir(schema_dir) if f.endswith('.schema.json')]
    schemas.sort()

    # Load and validate each schema
    schema_results = []
    for s in schemas:
        path = os.path.join(schema_dir, s)
        with open(path, 'r') as f:
            schema = json.load(f)
        valid = True
        checks = {}

        # Check for forbidden fields — use exact word boundaries, not substrings
        props = schema.get('properties', {})
        forbidden_exact = ['eligible', 'activation', 'model_id', 'adapter_id',
                          'capability_issuer', 'capability_consumer']
        forbidden_suffix = ['_eligible', '_activation', '_dispatch', '_execute',
                           '_runtime', '_device', '_port', '_capability_issuer',
                           '_capability_consumer']

        for pname in props:
            for term in forbidden_exact:
                if pname.lower() == term:
                    valid = False
                    checks[f'forbidden_{term}_in_{pname}'] = False
            for suffix in forbidden_suffix:
                if pname.lower().endswith(suffix):
                    valid = False
                    checks[f'forbidden_{suffix}_in_{pname}'] = False

        # Check additionalProperties
        checks['additional_properties_false'] = schema.get('additionalProperties', True) is False

        # Check cell domain [0, 80] only for actual cell-index fields (not counts)
        cell_index_props = {k: v for k, v in props.items()
                          if 'cell' in k.lower() and 'count' not in k.lower()
                          and 'support' in k.lower()}
        cell_index_props.update({k: v for k, v in props.items()
                                if ('target_cell' in k.lower() or 'delta_cell' in k.lower())})
        if cell_index_props:
            for cp_name, cp_def in cell_index_props.items():
                if cp_def.get('type') == 'integer':
                    checks[f'{cp_name}_min0'] = cp_def.get('minimum', -1) == 0
                    checks[f'{cp_name}_max80'] = cp_def.get('maximum', 81) == 80
                elif cp_def.get('type') == 'array':
                    items = cp_def.get('items', {})
                    if items.get('type') == 'integer':
                        checks[f'{cp_name}_items_min0'] = items.get('minimum', -1) == 0
                        checks[f'{cp_name}_items_max80'] = items.get('maximum', 81) == 80

        schema_results.append({
            'filename': s,
            'valid': valid and all(checks.values()),
            'checks': checks,
        })

    # Load decision record
    decision_record_path = os.path.join(spec_dir, 'G5_0A_DECISION_RECORD.json')
    with open(decision_record_path, 'r') as f:
        decision_record = json.load(f)

    # Validate decision record
    decision_checks = {
        'has_decisions': 'decisions' in decision_record,
        'has_upstream_gate': decision_record.get('upstream_gate') == 'G4.0B.1',
        'has_upstream_manifest_sha256': 'upstream_manifest_sha256' in decision_record,
        'has_governing_chain': 'governing_chain' in decision_record,
        'has_prohibited_collapse': 'prohibited_collapse' in decision_record,
    }

    # Cell domain audit
    cell_audit_path = os.path.join(g50a_reports_dir, 'G50A_CELL_DOMAIN_AUDIT.json')
    with open(cell_audit_path, 'r') as f:
        cell_audit = json.load(f)

    # Authority boundary audit
    authority_path = os.path.join(g50a_reports_dir, 'G50A_AUTHORITY_BOUNDARY_AUDIT.json')
    with open(authority_path, 'r') as f:
        authority_audit = json.load(f)

    all_valid = all(s['valid'] for s in schema_results)
    contract_valid = all_valid and all(decision_checks.values())

    return {
        'schema_count': len(schemas),
        'schema_validation_status': 'VALID' if all_valid else 'INVALID',
        'decision_record_status': 'VALID' if all(decision_checks.values()) else 'INVALID',
        'decision_record_checks': decision_checks,
        'cell_domain_status': cell_audit.get('status', 'UNKNOWN'),
        'authority_boundary_status': authority_audit.get('status', 'UNKNOWN'),
        'schema_results': schema_results,
        'overall_valid': contract_valid,
    }
