"""Tests for source-domain join."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_capability_authority.source_join import load_jsonl, perform_source_join

BASE = os.path.join(os.path.dirname(__file__), "..", "..")
G51B = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator")


def test_source_join_cardinalities():
    result = perform_source_join(
        os.path.join(G51B, "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl"),
        os.path.join(G51B, "G51B_ADJUDICATION_RECORD_INVENTORY.jsonl"),
        os.path.join(G51B, "G51B_PROPOSAL_DISPOSITION_INVENTORY.jsonl"),
        os.path.join(G51B, "G51B_ROW_ADJUDICATION_INDEX.jsonl"),
    )
    assert result["source_rows"] == 8192
    assert result["capability_review_requests"] == 8192
    assert result["adjudication_records"] == 8192
    assert result["proposal_dispositions"] == 40960
    assert result["row_index_records"] == 8192


def test_review_requested_count():
    requests = load_jsonl(os.path.join(G51B, "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl"))
    count = sum(1 for r in requests if r.get("request_state") == "REVIEW_REQUESTED")
    assert count == 8192


def test_capability_class():
    requests = load_jsonl(os.path.join(G51B, "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl"))
    for r in requests:
        assert r.get("required_capability_class") == "STRUCTURAL_INFLUENCE_CAPABILITY_V1"


def test_scope_distribution():
    requests = load_jsonl(os.path.join(G51B, "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl"))
    scope_1 = sum(1 for r in requests if len(r.get("referred_proposal_digests", [])) == 1)
    scope_2 = sum(1 for r in requests if len(r.get("referred_proposal_digests", [])) == 2)
    assert scope_1 == 1945
    assert scope_2 == 6247


def test_referred_proposal_count():
    dispositions = load_jsonl(os.path.join(G51B, "G51B_PROPOSAL_DISPOSITION_INVENTORY.jsonl"))
    referred = sum(1 for d in dispositions if d.get("disposition") == "REFERRED_FOR_CAPABILITY_REVIEW")
    negative = sum(1 for d in dispositions if d.get("disposition") == "NOT_REFERRED_NEGATIVE_EVIDENCE")
    preserved = sum(1 for d in dispositions if d.get("disposition") == "PRESERVED_ALTERNATIVE")
    assert referred == 14439
    assert negative == 18329
    assert preserved == 8192


def test_join_status():
    result = perform_source_join(
        os.path.join(G51B, "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl"),
        os.path.join(G51B, "G51B_ADJUDICATION_RECORD_INVENTORY.jsonl"),
        os.path.join(G51B, "G51B_PROPOSAL_DISPOSITION_INVENTORY.jsonl"),
        os.path.join(G51B, "G51B_ROW_ADJUDICATION_INDEX.jsonl"),
    )
    assert result["status"] == "CAPABILITY_AUTHORITY_SOURCE_JOIN_VERIFIED"
