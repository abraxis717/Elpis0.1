"""Test source inventory join."""

import os
import sys

BASE = '/mnt/primesauce/Elpis_Canon'
G4_REPORTS = os.path.join(BASE, 'reports', 'G4_0B_1_TypedProjectionCompiler')
PACKAGE = os.path.join(BASE, 'Grid81StructuralGroupProjectionCompiler')

sys.path.insert(0, os.path.join(PACKAGE, 'src'))

from elpis_grid81_groups.source_join import join_inventories


def test_source_join_row_count():
    identity_path = os.path.join(G4_REPORTS, 'G40B1_SOURCE_IDENTITY_INVENTORY.jsonl')
    transition_path = os.path.join(G4_REPORTS, 'G40B1_TRANSITION_INVENTORY.jsonl')
    expansion_path = os.path.join(G4_REPORTS, 'G40B1_EXPANSION_INVENTORY.jsonl')
    quiescence_path = os.path.join(G4_REPORTS, 'G40B1_QUIESCENCE_INVENTORY.jsonl')
    rationale_path = os.path.join(G4_REPORTS, 'G40B1_RATIONALE_INVENTORY.jsonl')

    joined_rows, audit = join_inventories(
        identity_path, transition_path, expansion_path,
        quiescence_path, rationale_path
    )
    assert len(joined_rows) == 8192
    assert audit['status'] == 'SOURCE_JOIN_VERIFIED'


def test_source_join_no_duplicates():
    identity_path = os.path.join(G4_REPORTS, 'G40B1_SOURCE_IDENTITY_INVENTORY.jsonl')
    transition_path = os.path.join(G4_REPORTS, 'G40B1_TRANSITION_INVENTORY.jsonl')
    expansion_path = os.path.join(G4_REPORTS, 'G40B1_EXPANSION_INVENTORY.jsonl')
    quiescence_path = os.path.join(G4_REPORTS, 'G40B1_QUIESCENCE_INVENTORY.jsonl')
    rationale_path = os.path.join(G4_REPORTS, 'G40B1_RATIONALE_INVENTORY.jsonl')

    joined_rows, audit = join_inventories(
        identity_path, transition_path, expansion_path,
        quiescence_path, rationale_path
    )
    assert audit['no_duplicates']


def test_source_join_digest_set_equality():
    identity_path = os.path.join(G4_REPORTS, 'G40B1_SOURCE_IDENTITY_INVENTORY.jsonl')
    transition_path = os.path.join(G4_REPORTS, 'G40B1_TRANSITION_INVENTORY.jsonl')
    expansion_path = os.path.join(G4_REPORTS, 'G40B1_EXPANSION_INVENTORY.jsonl')
    quiescence_path = os.path.join(G4_REPORTS, 'G40B1_QUIESCENCE_INVENTORY.jsonl')
    rationale_path = os.path.join(G4_REPORTS, 'G40B1_RATIONALE_INVENTORY.jsonl')

    joined_rows, audit = join_inventories(
        identity_path, transition_path, expansion_path,
        quiescence_path, rationale_path
    )
    assert audit['digest_set_equality']


def test_source_join_audit_report():
    reports = os.path.join(BASE, 'reports', 'G5_0B_StructuralGroupProjectionCompiler')
    path = os.path.join(reports, 'G50B_SOURCE_JOIN_AUDIT.json')
    if os.path.exists(path):
        import json
        with open(path, 'r') as f:
            data = json.load(f)
        assert data['status'] == 'SOURCE_JOIN_VERIFIED'
        assert data['joined_row_count'] == 8192

