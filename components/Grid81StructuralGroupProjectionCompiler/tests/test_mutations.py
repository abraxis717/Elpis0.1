"""Test mutation result integrity and verifier identity checks."""

import json
import os

import sys

BASE = '$ELPIS_CANON_ROOT/Elpis_Canon'
PACKAGE = os.path.join(BASE, 'Grid81StructuralGroupProjectionCompiler')
REPORTS = os.path.join(BASE, 'reports', 'G5_0B_StructuralGroupProjectionCompiler')

sys.path.insert(0, os.path.join(PACKAGE, 'src'))

from elpis_grid81_groups.verifier import verify_mutation_evidence_identity


def _make_results(mutations, total=30):
    """Build a mutation results dict from a list of mutation records."""
    return {
        'mutations': mutations,
        'total': total,
        'caught': sum(1 for m in mutations if m.get('caught')),
        'status': 'G50B_MUTATION_QUALIFICATION_PASS',
    }


def _write_temp_results(results, tmp_dir):
    """Write mutation results to a temp dir and return the path."""
    path = os.path.join(tmp_dir, 'G50B_MUTATION_RESULTS.json')
    with open(path, 'w') as f:
        json.dump(results, f)
    return path


# ── Self-tests: verifier rejects malformed mutation IDs ───────────────

def test_verify_rejects_missing_mutation_id(tmp_path):
    """Record with no mutation_id key must be rejected."""
    mutations = [
        {'mutation_name': 'test', 'expected_failure_code': 'CODE',
         'observed_failure_code': 'CODE', 'caught': True, 'canonical_source_unchanged': True},
    ]
    results = _make_results(mutations, total=1)
    _write_temp_results(results, str(tmp_path))
    errors = verify_mutation_evidence_identity(str(tmp_path))
    assert any('MUTATION_ID_MISSING' in e for e in errors), f"Expected MUTATION_ID_MISSING, got {errors}"


def test_verify_rejects_empty_mutation_id(tmp_path):
    """Record with mutation_id='' must be rejected."""
    mutations = [
        {'mutation_id': '', 'mutation_name': 'test', 'expected_failure_code': 'CODE',
         'observed_failure_code': 'CODE', 'caught': True, 'canonical_source_unchanged': True},
    ]
    results = _make_results(mutations, total=1)
    _write_temp_results(results, str(tmp_path))
    errors = verify_mutation_evidence_identity(str(tmp_path))
    assert any('MUTATION_ID_EMPTY' in e for e in errors), f"Expected MUTATION_ID_EMPTY, got {errors}"


def test_verify_rejects_duplicate_mutation_id(tmp_path):
    """Duplicate mutation_ids must be rejected."""
    mutations = [
        {'mutation_id': '01', 'mutation_name': 'dup', 'expected_failure_code': 'X',
         'observed_failure_code': 'X', 'caught': True, 'canonical_source_unchanged': True},
        {'mutation_id': '01', 'mutation_name': 'dup2', 'expected_failure_code': 'Y',
         'observed_failure_code': 'Y', 'caught': True, 'canonical_source_unchanged': True},
    ]
    results = _make_results(mutations, total=2)
    _write_temp_results(results, str(tmp_path))
    errors = verify_mutation_evidence_identity(str(tmp_path))
    assert any('MUTATION_ID_DUPLICATE' in e for e in errors), f"Expected MUTATION_ID_DUPLICATE, got {errors}"


def test_verify_rejects_single_digit_id(tmp_path):
    """mutation_id='1' instead of '01' must be rejected."""
    mutations = [
        {'mutation_id': '1', 'mutation_name': 'test', 'expected_failure_code': 'CODE',
         'observed_failure_code': 'CODE', 'caught': True, 'canonical_source_unchanged': True},
    ]
    results = _make_results(mutations, total=1)
    _write_temp_results(results, str(tmp_path))
    errors = verify_mutation_evidence_identity(str(tmp_path))
    assert any('MUTATION_ID_FORMAT_INVALID' in e for e in errors), f"Expected MUTATION_ID_FORMAT_INVALID, got {errors}"


def test_verify_rejects_id_out_of_range(tmp_path):
    """mutation_id='31' must be rejected (outside 01-30)."""
    mutations = [
        {'mutation_id': '31', 'mutation_name': 'test', 'expected_failure_code': 'CODE',
         'observed_failure_code': 'CODE', 'caught': True, 'canonical_source_unchanged': True},
    ]
    results = _make_results(mutations, total=1)
    _write_temp_results(results, str(tmp_path))
    errors = verify_mutation_evidence_identity(str(tmp_path))
    assert any('MUTATION_ID_SET_INCOMPLETE' in e for e in errors), f"Expected MUTATION_ID_SET_INCOMPLETE, got {errors}"


def test_verify_rejects_missing_id_in_set(tmp_path):
    """Set of IDs missing '17' must be rejected as incomplete."""
    mutations = []
    for i in range(1, 31):
        if i == 17:
            continue
        mid = f'{i:02d}'
        mutations.append({
            'mutation_id': mid,
            'mutation_name': f'mutation {mid}',
            'expected_failure_code': f'CODE_{mid}',
            'observed_failure_code': f'CODE_{mid}',
            'caught': True,
            'canonical_source_unchanged': True,
        })
    results = _make_results(mutations, total=29)
    _write_temp_results(results, str(tmp_path))
    errors = verify_mutation_evidence_identity(str(tmp_path))
    assert any('MUTATION_ID_SET_INCOMPLETE' in e for e in errors), f"Expected MUTATION_ID_SET_INCOMPLETE, got {errors}"


def test_verify_rejects_out_of_order(tmp_path):
    """Out-of-order ID sequence must be rejected."""
    mutations = []
    order = ['02', '01', '03']  # 01 and 02 swapped
    for mid in order:
        mutations.append({
            'mutation_id': mid,
            'mutation_name': f'mutation {mid}',
            'expected_failure_code': f'CODE_{mid}',
            'observed_failure_code': f'CODE_{mid}',
            'caught': True,
            'canonical_source_unchanged': True,
        })
    results = _make_results(mutations, total=3)
    _write_temp_results(results, str(tmp_path))
    errors = verify_mutation_evidence_identity(str(tmp_path))
    assert any('MUTATION_ID_ORDER_INVALID' in e for e in errors), f"Expected MUTATION_ID_ORDER_INVALID, got {errors}"


def test_verify_rejects_id_name_mismatch(tmp_path):
    """mutation_id with wrong name must be rejected."""
    # ID '01' should map to 'G4 manifest digest changed'
    mutations = [
        {'mutation_id': '01', 'mutation_name': 'WRONG NAME',
         'expected_failure_code': 'UPSTREAM_G40B1_SEAL_DIGEST_MISMATCH',
         'observed_failure_code': 'UPSTREAM_G40B1_SEAL_DIGEST_MISMATCH',
         'caught': True, 'canonical_source_unchanged': True},
    ]
    results = _make_results(mutations, total=1)
    _write_temp_results(results, str(tmp_path))
    errors = verify_mutation_evidence_identity(str(tmp_path))
    assert any('MUTATION_ID_NAME_MISMATCH' in e for e in errors), f"Expected MUTATION_ID_NAME_MISMATCH, got {errors}"


def test_verify_rejects_id_expected_code_mismatch(tmp_path):
    """mutation_id with wrong expected_failure_code must be rejected."""
    mutations = [
        {'mutation_id': '01', 'mutation_name': 'G4 manifest digest changed',
         'expected_failure_code': 'WRONG_CODE',
         'observed_failure_code': 'WRONG_CODE',
         'caught': True, 'canonical_source_unchanged': True},
    ]
    results = _make_results(mutations, total=1)
    _write_temp_results(results, str(tmp_path))
    errors = verify_mutation_evidence_identity(str(tmp_path))
    assert any('MUTATION_ID_FAILURE_CODE_MISMATCH' in e for e in errors), f"Expected MUTATION_ID_FAILURE_CODE_MISMATCH, got {errors}"


def test_verify_rejects_caught_false(tmp_path):
    """Record with caught=false must be rejected."""
    mutations = [
        {'mutation_id': '01', 'mutation_name': 'G4 manifest digest changed',
         'expected_failure_code': 'UPSTREAM_G40B1_SEAL_DIGEST_MISMATCH',
         'observed_failure_code': 'UPSTREAM_G40B1_SEAL_DIGEST_MISMATCH',
         'caught': False, 'canonical_source_unchanged': True},
    ]
    results = _make_results(mutations, total=1)
    _write_temp_results(results, str(tmp_path))
    errors = verify_mutation_evidence_identity(str(tmp_path))
    assert any('MUTATION_RESULT_NOT_CAUGHT' in e for e in errors), f"Expected MUTATION_RESULT_NOT_CAUGHT, got {errors}"


def test_verify_rejects_canonical_source_changed(tmp_path):
    """Record with canonical_source_unchanged=false must be rejected."""
    mutations = [
        {'mutation_id': '01', 'mutation_name': 'G4 manifest digest changed',
         'expected_failure_code': 'UPSTREAM_G40B1_SEAL_DIGEST_MISMATCH',
         'observed_failure_code': 'UPSTREAM_G40B1_SEAL_DIGEST_MISMATCH',
         'caught': True, 'canonical_source_unchanged': False},
    ]
    results = _make_results(mutations, total=1)
    _write_temp_results(results, str(tmp_path))
    errors = verify_mutation_evidence_identity(str(tmp_path))
    assert any('MUTATION_CANONICAL_SOURCE_CHANGED' in e for e in errors), f"Expected MUTATION_CANONICAL_SOURCE_CHANGED, got {errors}"


# ── Acceptance test: canonical set 01-30 ──────────────────────────────

def test_verify_accepts_canonical_id_set(tmp_path):
    """The exact canonical set of 30 records with IDs 01-30 must pass."""
    from elpis_grid81_groups.verifier import MUTATION_ID_REGISTRY
    mutations = []
    for mid in sorted(MUTATION_ID_REGISTRY.keys()):
        name, code = MUTATION_ID_REGISTRY[mid]
        mutations.append({
            'mutation_id': mid,
            'mutation_name': name,
            'expected_failure_code': code,
            'observed_failure_code': code,
            'caught': True,
            'canonical_source_unchanged': True,
        })
    results = _make_results(mutations, total=30)
    _write_temp_results(results, str(tmp_path))
    errors = verify_mutation_evidence_identity(str(tmp_path))
    assert len(errors) == 0, f"Expected no errors for canonical set, got {errors}"


# ── Existing tests (preserved) ────────────────────────────────────────

def test_mutation_results_exist():
    path = os.path.join(REPORTS, 'G50B_MUTATION_RESULTS.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'mutations' in data
        assert len(data['mutations']) == 30


def test_mutation_qualification_pass():
    path = os.path.join(REPORTS, 'G50B_MUTATION_RESULTS.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
        assert data['status'] == 'G50B_MUTATION_QUALIFICATION_PASS'
        caught = sum(1 for m in data['mutations'] if m['caught'])
        assert caught == 30


def test_mutation_canonical_unchanged():
    path = os.path.join(REPORTS, 'G50B_MUTATION_RESULTS.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
        for m in data['mutations']:
            assert m['canonical_source_unchanged'] is True


def test_mutation_ids_complete():
    """All 30 mutation records must have non-empty mutation_id."""
    path = os.path.join(REPORTS, 'G50B_MUTATION_RESULTS.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
        ids = [m['mutation_id'] for m in data['mutations']]
        expected = [f'{i:02d}' for i in range(1, 31)]
        assert ids == expected, f"mutation_id_set mismatch: got {ids}"


def test_mutation_ids_unique():
    """All mutation IDs must be unique."""
    path = os.path.join(REPORTS, 'G50B_MUTATION_RESULTS.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
        ids = [m['mutation_id'] for m in data['mutations']]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"


def test_mutation_id_set_field():
    """Top-level mutation_id_set must equal ['01', ..., '30']."""
    path = os.path.join(REPORTS, 'G50B_MUTATION_RESULTS.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'mutation_id_set' in data
        expected = [f'{i:02d}' for i in range(1, 31)]
        assert data['mutation_id_set'] == expected
