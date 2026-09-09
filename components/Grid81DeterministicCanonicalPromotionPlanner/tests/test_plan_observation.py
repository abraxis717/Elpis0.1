from dataclasses import replace
import hashlib
import json

import pytest

from elpis_grid81_promotion_planner.canonical import CanonicalPromotionPlan
from elpis_grid81_promotion_planner.verifier import verify_plan_nonexecutable, generate_authority_audit

INTENTIONS = (
    'VERIFY_CANONICAL_LEDGER_HEAD', 'VERIFY_CAPABILITY_GRANTED_UNCONSUMED',
    'VERIFY_ARTIFACT_CANONICALLY_UNAPPLIED', 'RESERVE_TRANSACTION_IDENTIFIER',
    'PERFORM_CANONICAL_APPLICATION', 'APPEND_CANONICAL_RECEIPT', 'VERIFY_POST_COMMIT_STATE',
)


def plan():
    return CanonicalPromotionPlan(INTENTIONS, '1'*64, '2'*64)


@pytest.mark.parametrize('field,value', [
    ('executable', True), ('self_applying', True), ('authoritative', True),
    ('canonical_write_permitted', True), ('executable', 0),
    ('intentions', ('exec(payload)',)), ('intentions', (lambda: None,)),
    ('decision_digest', 'unbound'), ('source_chain_digest', ''), ('planner_version', '2'),
])
def test_mutated_artifact_rejected(field, value):
    assert not verify_plan_nonexecutable(replace(plan(), **{field: value}))['plan_non_executable']


def test_extra_capability_field_rejected():
    artifact = plan()
    object.__setattr__(artifact, 'callback', lambda: None)
    assert not verify_plan_nonexecutable(artifact)['plan_non_executable']


def test_valid_data_has_deterministic_successor_observation():
    result = verify_plan_nonexecutable(plan())
    assert result == {
        'schema': 'elpis.grid81.promotion-plan-data-check.v2',
        'plan_non_executable': True, 'violations_found': 0, 'violation_details': [],
        'plan_digest': 'cc784dec9520b7f0137e069387dc8dfba25433e700f137cc50ee420aa26bbfed',
    }


def test_config_and_state_are_observed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {}
    for key, manifest in (
        ('g53b1_directory', 'G53B_RAW_EVIDENCE_MANIFEST.json'),
        ('g53c_directory', 'RAW_EVIDENCE_MANIFEST.json'),
        ('g53d_directory', 'RAW_EVIDENCE_MANIFEST.json'),
    ):
        directory = tmp_path / key
        directory.mkdir()
        (directory / manifest).write_text('{}')
        config[key] = key
    phase_c = tmp_path / 'g53c_directory'
    (phase_c / 'G53C_APPLICATION_RECEIPTS.jsonl').write_text('')
    for name in ('G53C_THREE_SEED_DETERMINISM.json', 'G53C_AUTHORITY_AUDIT.json',
                 'G53C_POST_QUALIFICATION_VERIFICATION.json'):
        (phase_c / name).write_text('{}')
    first = generate_authority_audit(config)
    assert first['plan_status'] == 'NOT_RENDERED'
    assert first['observation_digest'] == '7c11bb1621919a85eb19eef5a45f49b8c9f5be1a6262e3cb31963df1788cce47'
    assert set(first) == {'schema', 'source_chain_digest', 'decision_digest', 'plan_status', 'observation_digest'}
    changed = tmp_path / 'g53b1_directory' / 'G53B_RAW_EVIDENCE_MANIFEST.json'
    changed.write_text('{"observed_revision":2}')
    second = generate_authority_audit(config)
    assert first['source_chain_digest'] != second['source_chain_digest']
    assert first['observation_digest'] != second['observation_digest']
    digest = second.pop('observation_digest')
    assert hashlib.sha256(json.dumps(second, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest() == digest
