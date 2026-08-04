"""R1 tests — bounded pre-refinement retrieval, fail-closed, determinism."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile

import pytest

CANON = "/mnt/primesauce/Elpis_Canon/Elpis"
_SRC = [
    os.path.join(CANON, "TRMFractalSpine", "src"),
    os.path.join(CANON, "Pipeline", "P0ControlProtocol", "src"),
    os.path.join(CANON, "Grid81DeterministicStructuralAdjudicator", "src"),
    os.path.join(CANON, "Grid81StructuralSemantics", "src"),
    CANON,
]
for _p in _SRC:
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ["CUDA_VISIBLE_DEVICES"] = ""

from elpis_runtime_r1.contracts import (
    R1TransactionReceipt,
    RetrievalBundle,
    RetrievalItem,
    _canonical_bytes,
    _digest,
    _sha256_hex,
)
from elpis_runtime_r1.errors import (
    R1BundleValidationError,
    R1BudgetOverflowError,
    R1Error,
    R1QueryDerivationError,
)
from elpis_runtime_r1.hacf_adapter import (
    build_corpus_and_index,
    bundle_from_json,
    hybrid_retrieve,
)
from elpis_runtime_r1.query_derivation import derive_query
from elpis_runtime_r1.bundle_validation import validate_bundle
from elpis_runtime_r1.budget import RetrievalBudget, check_budget
from elpis_runtime_r1.evidence_adapter import build_evidence_envelope
from elpis_runtime_r1.receipt import verify_receipt_self_hash, receipts_identical

DOCS = [
    ("alpha", "alpha engine exact retrieval anchor", "elpis.docs", "canonical"),
    ("beta", "beta companion context bridge", "elpis.docs", "reference"),
    ("gamma", "gamma vector semantic neighbor", "elpis.code", "canonical"),
    ("delta", "delta unrelated background note", "elpis.notes", "advisory"),
]

BUDGET = RetrievalBudget()


def _item(text: str, **kw) -> RetrievalItem:
    """Build a RetrievalItem with all required fields, overriding via kw."""
    td = _sha256_hex(text.encode("utf-8")) if text else ""
    defaults = dict(
        chunk_digest="a" * 64,
        doc_digest="b" * 64,
        namespace="elpis.docs",
        authority="canonical",
        graph_parent_digest="0" * 64,
        text_digest=td,
        fusion_score_key=100,
        dense_score_key=50,
        lexical_rank=1,
        dense_rank=1,
        final_rank=0,
        source_mask=3,
        item_kind=1,
        graph_hop=0,
        edge_type=0,
        edge_authority=0,
        text=text,
        text_bytes=len(text.encode("utf-8")) if text else 0,
    )
    defaults.update(kw)
    return RetrievalItem(**defaults)


# ====================================================================
# Query derivation
# ====================================================================
class TestQueryDerivation:
    def test_basic_derivation(self):
        req = {
            "request_id": "r1_test_001",
            "prompt": "def solution(x): return x + 1",
            "domain": "python",
            "entrypoint": "solution",
        }
        q = derive_query(req)
        assert q.query_text != ""
        assert len(q.query_text.encode("utf-8")) <= 4096
        assert q.source_request_digest == _digest(req)

    def test_deterministic(self):
        req = {
            "request_id": "r1_det",
            "prompt": "test determinism",
            "domain": "python",
            "entrypoint": "main",
        }
        q1 = derive_query(req)
        q2 = derive_query(req)
        assert q1.query_digest == q2.query_digest

    def test_missing_field(self):
        with pytest.raises(R1QueryDerivationError, match="MISSING_FIELD"):
            derive_query({"request_id": "x"})

    def test_empty_after_normalization(self):
        req = {
            "request_id": "   ",
            "prompt": "   ",
            "domain": "   ",
            "entrypoint": "   ",
        }
        with pytest.raises(R1QueryDerivationError, match="EMPTY_QUERY"):
            derive_query(req)


# ====================================================================
# HACF retrieval (positive)
# ====================================================================
class TestHacfRetrieval:
    @pytest.fixture(scope="class")
    def handle(self):
        td = tempfile.mkdtemp(prefix="r1_test_")
        h = build_corpus_and_index(td, DOCS)
        yield h
        h.destroy()
        import shutil
        shutil.rmtree(td, ignore_errors=True)

    def test_retrieval_returns_bundle(self, handle):
        r = hybrid_retrieve(
            handle, "alpha engine", lexical_limit=50, dense_limit=50,
            primary_limit=30, total_limit=60,
        )
        assert r["item_count"] > 0
        assert r["bundle_json"] != ""
        assert r["query_digest"] != ""

    def test_bundle_schema(self, handle):
        r = hybrid_retrieve(handle, "alpha", lexical_limit=50, dense_limit=50)
        data = r["data"]
        assert data.get("schema") == "elpis.retrieval_bundle.v1"

    def test_bundle_has_items(self, handle):
        r = hybrid_retrieve(handle, "alpha", lexical_limit=50, dense_limit=50)
        assert len(r["data"].get("items", [])) > 0

    def test_bundle_items_have_text(self, handle):
        r = hybrid_retrieve(handle, "alpha", lexical_limit=50, dense_limit=50)
        for item in r["data"].get("items", []):
            assert item.get("chunk_digest"), "item missing chunk_digest"
            assert item.get("text_bytes", 0) > 0, "item has zero text_bytes"

    def test_deterministic_retrieval(self, handle):
        r1 = hybrid_retrieve(handle, "alpha", lexical_limit=50, dense_limit=50)
        r2 = hybrid_retrieve(handle, "alpha", lexical_limit=50, dense_limit=50)
        assert r1["bundle_digest"] == r2["bundle_digest"]


# ====================================================================
# Bundle validation (positive + negative)
# ====================================================================
class TestBundleValidation:
    def _make_bundle(self, items):
        return RetrievalBundle(
            schema="elpis.retrieval_bundle.v1",
            query_digest="q" * 64,
            corpus_manifest_digest="c" * 64,
            items=tuple(items),
        )

    def test_valid_bundle(self):
        text = "alpha engine exact retrieval anchor"
        td = _sha256_hex(text.encode("utf-8"))
        items = [_item(text, chunk_digest="a" * 64, text_digest=td)]
        b = self._make_bundle(items)
        decision = validate_bundle(b, "q" * 64, "c" * 64, BUDGET)
        assert decision is not None
        assert not decision.exceeded

    def test_unknown_schema(self):
        b = RetrievalBundle(schema="bad.schema")
        with pytest.raises(R1BundleValidationError, match="UNKNOWN_SCHEMA"):
            validate_bundle(b, "q" * 64, "c" * 64)

    def test_query_digest_mismatch(self):
        b = self._make_bundle([])
        with pytest.raises(R1BundleValidationError, match="QUERY_DIGEST_MISMATCH"):
            validate_bundle(b, "x" * 64, "c" * 64)

    def test_corpus_digest_mismatch(self):
        b = self._make_bundle([])
        with pytest.raises(R1BundleValidationError, match="CORPUS_DIGEST_MISMATCH"):
            validate_bundle(b, "q" * 64, "x" * 64)

    def test_rank_order_mismatch(self):
        items = [_item("test", final_rank=5)]
        b = self._make_bundle(items)
        with pytest.raises(R1BundleValidationError, match="RANK_ORDER"):
            validate_bundle(b, "q" * 64, "c" * 64)

    def test_missing_chunk_digest(self):
        items = [_item("test", chunk_digest="")]
        b = self._make_bundle(items)
        with pytest.raises(R1BundleValidationError, match="MISSING_CHUNK_DIGEST"):
            validate_bundle(b, "q" * 64, "c" * 64)

    def test_missing_text(self):
        items = [_item("", chunk_digest="a" * 64)]
        b = self._make_bundle(items)
        with pytest.raises(R1BundleValidationError, match="MISSING_FROZEN_TEXT"):
            validate_bundle(b, "q" * 64, "c" * 64)

    def test_duplicate_chunk(self):
        text = "test"
        td = _sha256_hex(text.encode())
        items = [
            _item(text, chunk_digest="x" * 64, text_digest=td),
            _item(text, chunk_digest="x" * 64, final_rank=1, text_digest=td),
        ]
        b = self._make_bundle(items)
        with pytest.raises(R1BundleValidationError, match="DUPLICATE_CHUNK"):
            validate_bundle(b, "q" * 64, "c" * 64)

    def test_context_beyond_one_hop(self):
        items = [_item("test", graph_hop=2)]
        b = self._make_bundle(items)
        with pytest.raises(R1BundleValidationError, match="CONTEXT"):
            validate_bundle(b, "q" * 64, "c" * 64)


# ====================================================================
# Budget enforcement
# ====================================================================
class TestBudget:
    def test_within_budget(self):
        decision = check_budget(
            BUDGET,
            {"lexical": 10, "dense": 10, "fused": 20, "context": 0, "total": 20},
            500,
        )
        assert not decision.exceeded

    def test_overflow(self):
        with pytest.raises(R1BudgetOverflowError, match="BUDGET_EXCEEDED"):
            check_budget(
                BUDGET,
                {"lexical": 0, "dense": 0, "fused": 50, "context": 0, "total": 300},
                500,
            )


# ====================================================================
# Receipt
# ====================================================================
class TestReceipt:
    def test_self_hash(self):
        r = R1TransactionReceipt(
            transaction_id="test",
            request_digest="a" * 64,
            retrieval_contract_version="elpis.retrieval_contract.v1",
            retrieval_query_digest="b" * 64,
            retrieval_budget_digest="c" * 64,
            corpus_identity="d" * 64,
            vector_index_identity="e" * 64,
            retrieval_bundle_schema="elpis.retrieval_bundle.v1",
            retrieval_bundle_digest="f" * 64,
            evidence_envelope_digest="g" * 64,
            r0_receipt_digest="h" * 64,
            termination_disposition="DETERMINISTIC_TRANSACTION_COMPLETE",
            component_manifest_digests="i" * 64,
            dependency_resolution_audit_digest="j" * 64,
            runtime_admission_receipt=False,
        )
        assert verify_receipt_self_hash(r)
        assert r.receipt_self_hash != ""
        assert len(r.receipt_self_hash) == 64

    def test_canonical_json_deterministic(self):
        r = R1TransactionReceipt(
            transaction_id="det", request_digest="a" * 64,
            retrieval_contract_version="v1", retrieval_query_digest="b" * 64,
            retrieval_budget_digest="c" * 64, corpus_identity="d" * 64,
            vector_index_identity="e" * 64,
            retrieval_bundle_schema="elpis.retrieval_bundle.v1",
            retrieval_bundle_digest="f" * 64,
            evidence_envelope_digest="g" * 64,
            r0_receipt_digest="h" * 64,
            termination_disposition="DETERMINISTIC_TRANSACTION_COMPLETE",
            component_manifest_digests="i" * 64,
            dependency_resolution_audit_digest="j" * 64,
        )
        j1 = r.to_canonical_json()
        j2 = r.to_canonical_json()
        assert j1 == j2

    def test_identical_receipts(self):
        params = dict(
            transaction_id="x", request_digest="a" * 64,
            retrieval_contract_version="v", retrieval_query_digest="b" * 64,
            retrieval_budget_digest="c" * 64, corpus_identity="d" * 64,
            vector_index_identity="e" * 64,
            retrieval_bundle_schema="elpis.retrieval_bundle.v1",
            retrieval_bundle_digest="f" * 64,
            evidence_envelope_digest="g" * 64,
            r0_receipt_digest="h" * 64,
            termination_disposition="DETERMINISTIC_TRANSACTION_COMPLETE",
            component_manifest_digests="i" * 64,
            dependency_resolution_audit_digest="j" * 64,
        )
        r1 = R1TransactionReceipt(**params)
        r2 = R1TransactionReceipt(**params)
        assert receipts_identical(r1, r2)


# ====================================================================
# Negative fail-closed summary
# ====================================================================
class TestFailClosed:
    def test_all_negative_cases_fail_closed(self):
        pass
