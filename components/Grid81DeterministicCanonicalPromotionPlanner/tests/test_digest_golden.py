"""Elpis2.1.9 values recorded before verifier/CLI edits; historical claims only."""
from elpis_grid81_promotion_planner.canonical import AuthorityAudit, CanonicalPromotionPlan
from elpis_grid81_promotion_planner.verifier import _file_sha256


def test_historical_constant_audit_identity():
    assert AuthorityAudit().digest == '808b291b61ee2e02740602813a0cc25a5c9c8a1818f46ae294c5e878238d6c44'


def test_historical_plan_identity():
    plan = CanonicalPromotionPlan(intentions=('VERIFY_CANONICAL_LEDGER_HEAD',),
                                  decision_digest='1'*64, source_chain_digest='2'*64)
    assert plan.digest == 'd8b111e83b470f88c26667c3869e1c342abc9bcb8f9837c044ebbdc36ca9cd16'


def test_historical_file_hash(tmp_path):
    path = tmp_path / 'fixed'
    path.write_bytes(b'abc')
    assert _file_sha256(str(path)) == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
