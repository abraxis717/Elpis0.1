"""Test G4 and G5.0A seal consumption."""

import json
import os

BASE = '$ELPIS_CANON_ROOT/Elpis_Canon'
G4_REPORTS = os.path.join(BASE, 'reports', 'G4_0B_1_TypedProjectionCompiler')
G50A_REPORTS = os.path.join(BASE, 'reports', 'G5_0A_StructuralGroupEvidenceContract')
G50A_PACKAGE = os.path.join(BASE, 'Grid81StructuralGroupContract')


def test_g4_manifest_exists():
    path = os.path.join(G4_REPORTS, 'G40B1_RAW_EVIDENCE_MANIFEST.json')
    assert os.path.exists(path), 'G4 manifest missing'


def test_g4_manifest_readable():
    path = os.path.join(G4_REPORTS, 'G40B1_RAW_EVIDENCE_MANIFEST.json')
    with open(path, 'r') as f:
        manifest = json.load(f)
    assert 'evidence_files' in manifest
    assert len(manifest['evidence_files']) > 0


def test_g50a_manifest_exists():
    path = os.path.join(G50A_REPORTS, 'G50A_RAW_EVIDENCE_MANIFEST.json')
    assert os.path.exists(path), 'G5.0A manifest missing'


def test_g50a_manifest_readable():
    path = os.path.join(G50A_REPORTS, 'G50A_RAW_EVIDENCE_MANIFEST.json')
    with open(path, 'r') as f:
        manifest = json.load(f)
    assert 'evidence_files' in manifest
    assert len(manifest['evidence_files']) == 16


def test_g50a_decision_record_exists():
    path = os.path.join(G50A_REPORTS, 'G50A_DECISION_RECORD.json')
    assert os.path.exists(path)


def test_g50a_decision_record_valid():
    path = os.path.join(G50A_REPORTS, 'G50A_DECISION_RECORD.json')
    with open(path, 'r') as f:
        dr = json.load(f)
    assert dr.get('upstream_gate') == 'G4.0B.1'
    assert 'decisions' in dr
    assert len(dr['decisions']) > 0


def test_g50a_schemas_exist():
    schema_dir = os.path.join(G50A_PACKAGE, 'schemas')
    schemas = [f for f in os.listdir(schema_dir) if f.endswith('.schema.json')]
    assert len(schemas) == 9


def test_upstream_seal_consumption_report():
    reports = os.path.join(BASE, 'reports', 'G5_0B_StructuralGroupProjectionCompiler')
    path = os.path.join(reports, 'G50B_UPSTREAM_SEAL_CONSUMPTION.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'g4_seal' in data
        assert 'g50a_seal' in data


def test_contract_revalidation_report():
    reports = os.path.join(BASE, 'reports', 'G5_0B_StructuralGroupProjectionCompiler')
    path = os.path.join(reports, 'G50B_CONTRACT_SOURCE_REVALIDATION.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
        assert 'schema_count' in data
        assert data['schema_count'] == 9

