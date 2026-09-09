"""Exact Elpis2.1.9 wire identities pinned before P1.2 authority edits.

These fixed records test historical canonicalization and validation. They are
compatibility evidence, not proof that a digest confers live authority.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


HISTORICAL = json.loads(
    (Path(__file__).parent / 'fixtures/authority_digest_elpis_2_1_9.json').read_text()
)
SUCCESSOR = json.loads(
    (Path(__file__).parent / 'fixtures/authority_digest_successor_v2.json').read_text()
)


@pytest.mark.parametrize(
    'fixture', HISTORICAL['fixtures'],
    ids=[f["stage"] + '.' + f["digest_field"] for f in HISTORICAL['fixtures']],
)
def test_elpis_2_1_9_authority_digest_golden(fixture):
    _verify_fixture(fixture)


@pytest.mark.parametrize(
    'fixture', SUCCESSOR['fixtures'],
    ids=[f["stage"] + '.' + f["digest_field"] for f in SUCCESSOR['fixtures']],
)
def test_successor_authority_digest_golden(fixture):
    _verify_fixture(fixture)


def _verify_fixture(fixture):
    module = importlib.import_module(
        'elpis_reference.structural_guidance.' + fixture['module']
    )
    record = getattr(module, fixture['type'])(
        **fixture['payload'], **{fixture['digest_field']: fixture['expected']}
    )
    assert record.payload() == fixture['payload']
    assert module._domain_digest(fixture['domain'], record.payload()) == fixture['expected']
    record.validate()
