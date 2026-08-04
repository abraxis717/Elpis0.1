"""Tests for canonical data structures and utilities."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from elpis_grid81_promotion_planner.canonical import (
    PhaseEvidence,
    SourceChain,
    GateResult,
    PromotionDecision,
    CanonicalPromotionPlan,
    AuthorityAudit,
    REJECTION_PRECEDENCE,
    _sha256_str,
    _canonical_json,
    _digest_of,
)


def test_sha256_str_deterministic():
    assert _sha256_str("hello") == _sha256_str("hello")
    assert _sha256_str("hello") != _sha256_str("world")


def test_canonical_json_deterministic():
    obj = {"b": 2, "a": 1}
    assert _canonical_json(obj) == '{"a":1,"b":2}'


def test_digest_of_frozen_dataclass():
    pe = PhaseEvidence(
        phase_id="test",
        source_directory="/tmp",
        manifest_path="/tmp/m.json",
        manifest_digest="abc",
        disposition="SEALED",
        evidence_files=(),
    )
    assert pe.digest == pe.digest


def test_phase_evidence_immutable():
    pe = PhaseEvidence(
        phase_id="test",
        source_directory="/tmp",
        manifest_path="/tmp/m.json",
        manifest_digest="abc",
        disposition="SEALED",
        evidence_files=(),
    )
    try:
        pe.phase_id = "other"
        assert False, "Should not be able to modify frozen dataclass"
    except Exception:
        pass


def test_gate_result_immutable():
    gr = GateResult(
        gate_id="TEST",
        gate_ordinal=1,
        gate_version="1.0.0",
        passed=True,
        rejection_code=None,
        evidence_bindings=(),
    )
    assert gr.digest == gr.digest


def test_source_chain_digest():
    pe1 = PhaseEvidence(
        phase_id="G5.3B.1",
        source_directory="/a",
        manifest_path="/a/m.json",
        manifest_digest="aaa",
        disposition="SEALED",
        evidence_files=(),
    )
    pe2 = PhaseEvidence(
        phase_id="G5.3C",
        source_directory="/b",
        manifest_path="/b/m.json",
        manifest_digest="bbb",
        disposition="SEALED",
        evidence_files=(),
    )
    pe3 = PhaseEvidence(
        phase_id="G5.3D",
        source_directory="/c",
        manifest_path="/c/m.json",
        manifest_digest="ccc",
        disposition="SEALED",
        evidence_files=(),
    )
    chain = SourceChain(g53b1=pe1, g53c=pe2, g53d=pe3)
    assert chain.chain_digest == chain.chain_digest


def test_authority_audit_defaults():
    audit = AuthorityAudit()
    assert audit.planner_authoritative_for_application is False
    assert audit.canonical_capabilities_consumed == 0
    assert audit.qubo_touched is False
    assert audit.network_used is False


def test_rejection_precedence_length():
    assert len(REJECTION_PRECEDENCE) == 20


def test_rejection_precedence_deterministic():
    assert REJECTION_PRECEDENCE[0] == "SOURCE_MANIFEST_INVALID"
    assert REJECTION_PRECEDENCE[-1] == "PLANNER_AUTHORITY_VIOLATION"


def test_promotion_plan_immutable():
    plan = CanonicalPromotionPlan(
        intentions=(),
        decision_digest="abc",
        source_chain_digest="def",
    )
    assert plan.executable is False
    assert plan.self_applying is False
    assert plan.authoritative is False
    assert plan.canonical_write_permitted is False
