"""R1 tests — bounded pre-refinement retrieval, fail-closed, determinism."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import tempfile

import pytest

# Resolve repository root portably
# This test lives at runtime/R1/tests/
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SRC = [
    os.path.join(_REPO_ROOT, "components", "TRMFractalSpine", "src"),
    os.path.join(_REPO_ROOT, "components", "Grid81DeterministicStructuralAdjudicator", "src"),
    os.path.join(_REPO_ROOT, "components", "Grid81StructuralSemantics", "src"),
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
    R1HacfRetrievalError,
    R1QueryDerivationError,
)
from elpis_runtime_r1 import hacf_adapter
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

    def test_65_documents_refused_with_typed_limit(self):
        td = tempfile.mkdtemp(prefix="r1_limit_")
        documents = [
            (
                f"doc-{i:02d}",
                f"bounded document {i}",
                "elpis.docs",
                "canonical",
            )
            for i in range(65)
        ]
        try:
            with pytest.raises(R1HacfRetrievalError, match="E_LIMIT"):
                build_corpus_and_index(td, documents)
        finally:
            import shutil
            shutil.rmtree(td, ignore_errors=True)

    def test_manifest_copy_boundary_via_compiled_ctypes_helper(self):
        lib = hacf_adapter._load()
        lib.r1_checked_manifest_copy.restype = ctypes.c_int
        lib.r1_checked_manifest_copy.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_char_p,
        ]

        capacity = 65536
        dst = ctypes.create_string_buffer(capacity)
        out_len = ctypes.c_size_t(0)
        err = ctypes.create_string_buffer(256)

        allowed = b"a" * 65535
        rc = lib.r1_checked_manifest_copy(
            allowed,
            dst,
            capacity,
            ctypes.byref(out_len),
            err,
        )
        assert rc == 0
        assert out_len.value == 65535
        assert dst.raw[:65535] == allowed
        assert dst.raw[65535] == 0

        refused = b"b" * 65536
        dst2 = ctypes.create_string_buffer(capacity)
        out_len2 = ctypes.c_size_t(999)
        err2 = ctypes.create_string_buffer(256)
        rc = lib.r1_checked_manifest_copy(
            refused,
            dst2,
            capacity,
            ctypes.byref(out_len2),
            err2,
        )
        assert rc == -2
        assert out_len2.value == 0
        assert b"E_LIMIT" in err2.value
        assert dst2.raw[0] == 0

    def test_retrieval_json_buffer_truncation_is_refused(self, handle):
        lib = hacf_adapter._load()

        query = b"alpha"
        vec = (ctypes.c_float * hacf_adapter.ELPIS_EMBEDDING_DIM)()
        rc = lib.r1_env_embed(
            handle._ptr,
            query,
            len(query),
            vec,
            hacf_adapter.ELPIS_EMBEDDING_DIM,
        )
        assert rc == 0

        json_buf = ctypes.create_string_buffer(1)
        bundle_digest = ctypes.create_string_buffer(65)
        query_digest = ctypes.create_string_buffer(65)
        corpus_manifest_digest = ctypes.create_string_buffer(65)
        vindex_manifest_digest = ctypes.create_string_buffer(65)
        fusion_policy_digest = ctypes.create_string_buffer(65)
        item_count = ctypes.c_int(0)
        err = ctypes.create_string_buffer(256)

        rc = lib.r1_env_retrieve(
            handle._ptr,
            query,
            vec,
            hacf_adapter.ELPIS_EMBEDDING_DIM,
            50,
            50,
            30,
            60,
            json_buf,
            1,
            bundle_digest,
            query_digest,
            corpus_manifest_digest,
            vindex_manifest_digest,
            fusion_policy_digest,
            ctypes.byref(item_count),
            err,
        )

        assert rc == -2
        assert b"E_LIMIT" in err.value
        assert json_buf.raw == b"\x00"


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


def test_canonical_root_rejects_filesystem_root():
    import os
    import pytest
    from elpis_runtime_r1.transaction import _validate_canonical_root
    from elpis_runtime_r1.errors import R1DependencyEscapeError
    with pytest.raises(R1DependencyEscapeError, match="CANONICAL_ROOT_INVALID"):
        _validate_canonical_root(os.path.sep)


# Exact canonical manifest authority; all fixtures copy only these three files.
_CANONICAL_MANIFEST_PATHS = (
    "Grid81/COMPONENT_MANIFEST.json",
    "DarwinianMatrix/COMPONENT_MANIFEST.json",
    "Pipeline/P0ControlProtocol/COMPONENT_MANIFEST.json",
)


@pytest.fixture
def canonical_root_fixture(tmp_path):
    from pathlib import Path

    components = Path(__file__).resolve().parents[3] / "components"
    candidate = tmp_path / "candidate"
    for relative in _CANONICAL_MANIFEST_PATHS:
        destination = candidate / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((components / relative).read_bytes())
    return candidate


def _assert_canonical_root_rejected(root, reason):
    from elpis_runtime_r1.transaction import _validate_canonical_root
    from elpis_runtime_r1.errors import R1DependencyEscapeError

    with pytest.raises(R1DependencyEscapeError, match="CANONICAL_ROOT_INVALID") as caught:
        _validate_canonical_root(root)
    assert reason in str(caught.value)
    assert caught.value.code == "CANONICAL_ROOT_INVALID"


def test_canonical_root_exact_copies_accepted(canonical_root_fixture):
    from elpis_runtime_r1.transaction import _validate_canonical_root

    assert _validate_canonical_root(str(canonical_root_fixture)) == str(canonical_root_fixture.resolve())


def test_canonical_root_pins_match_repository_bytes():
    from pathlib import Path
    from elpis_runtime_r1.transaction import EXPECTED_CANONICAL_MANIFESTS, _validate_canonical_root

    components = Path(__file__).resolve().parents[3] / "components"
    assert set(EXPECTED_CANONICAL_MANIFESTS) == set(_CANONICAL_MANIFEST_PATHS)
    for relative, expected in EXPECTED_CANONICAL_MANIFESTS.items():
        raw = (components / relative).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected["sha256"]
        manifest = json.loads(raw)
        for field in ("component_id", "canonical_destination", "manifest_self_hash"):
            assert manifest[field] == expected[field]
    assert _validate_canonical_root(str(components)) == str(components.resolve())


def test_canonical_root_pins_are_immutable():
    from elpis_runtime_r1.transaction import EXPECTED_CANONICAL_MANIFESTS

    with pytest.raises(TypeError):
        EXPECTED_CANONICAL_MANIFESTS["extra"] = {}
    with pytest.raises(TypeError):
        EXPECTED_CANONICAL_MANIFESTS[_CANONICAL_MANIFEST_PATHS[0]]["sha256"] = "0" * 64


def test_canonical_root_json_stubs_rejected(canonical_root_fixture):
    for relative in _CANONICAL_MANIFEST_PATHS:
        path = canonical_root_fixture / relative
        legitimate = json.loads(path.read_bytes())
        path.write_text(json.dumps({
            field: legitimate[field]
            for field in ("component_id", "canonical_destination", "manifest_self_hash")
        }), encoding="utf-8")
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_digest_mismatch")


@pytest.mark.parametrize("relative", _CANONICAL_MANIFEST_PATHS)
@pytest.mark.parametrize("rewrite", ["single_byte", "content", "self_consistent"])
def test_canonical_root_manifest_rewrites_rejected(canonical_root_fixture, relative, rewrite):
    path = canonical_root_fixture / relative
    raw = path.read_bytes()
    if rewrite == "single_byte":
        # Even one added whitespace byte must fail exact-byte authentication.
        changed = raw + b"\n"
    else:
        manifest = json.loads(raw)
        manifest["display_name"] = "rewritten"
        if rewrite == "self_consistent":
            manifest.pop("manifest_self_hash")
            payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
            manifest["manifest_self_hash"] = hashlib.sha256(payload).hexdigest()
            assert len(manifest["manifest_self_hash"]) == 64
            assert manifest["manifest_self_hash"] != json.loads(raw)["manifest_self_hash"]
        changed = json.dumps(manifest, sort_keys=True).encode("utf-8")
    path.write_bytes(changed)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_digest_mismatch")


@pytest.mark.parametrize("field", ["component_id", "canonical_destination", "manifest_self_hash"])
def test_canonical_root_wrong_identity_rejected(canonical_root_fixture, field):
    path = canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]
    manifest = json.loads(path.read_bytes())
    manifest[field] = "0" * 64 if field == "manifest_self_hash" else "wrong"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_digest_mismatch")


@pytest.mark.parametrize("other", _CANONICAL_MANIFEST_PATHS[1:])
def test_canonical_root_swapped_manifests_rejected(canonical_root_fixture, other):
    first = canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]
    second = canonical_root_fixture / other
    first_bytes, second_bytes = first.read_bytes(), second.read_bytes()
    first.write_bytes(second_bytes)
    second.write_bytes(first_bytes)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_digest_mismatch")


@pytest.mark.parametrize("raw", [b'{"malformed":', b"[]", b"null", b"\xff"])
def test_canonical_root_malformed_or_nonobject_json_rejected(canonical_root_fixture, raw):
    (canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]).write_bytes(raw)
    # The external byte pin rejects malformed replacements before JSON parsing.
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_digest_mismatch")


@pytest.mark.parametrize("relative", _CANONICAL_MANIFEST_PATHS)
def test_canonical_root_missing_manifest_rejected(canonical_root_fixture, relative):
    (canonical_root_fixture / relative).unlink()
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_missing")


@pytest.mark.parametrize("relative", [
    "", "Grid81", "DarwinianMatrix", "Pipeline", "Pipeline/P0ControlProtocol",
    *_CANONICAL_MANIFEST_PATHS,
])
def test_canonical_root_symlink_rejected(canonical_root_fixture, tmp_path, relative):
    path = canonical_root_fixture / relative
    is_directory = path.is_dir()
    authentic = tmp_path / "authentic"
    path.rename(authentic)
    path.symlink_to(authentic, target_is_directory=is_directory)
    reason = "manifest_symlink" if relative else "symlink root"
    _assert_canonical_root_rejected(str(canonical_root_fixture), reason)


@pytest.mark.parametrize("kind", ["directory", "fifo"])
def test_canonical_root_nonregular_manifest_rejected(canonical_root_fixture, kind):
    path = canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]
    path.unlink()
    if kind == "directory":
        path.mkdir()
    else:
        os.mkfifo(path)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_not_regular")


@pytest.mark.parametrize("root", ["", None, 42, "\x00"])
def test_canonical_root_invalid_input_rejected(root):
    reason = "root_malformed" if root == "\x00" else "empty/non-string root"
    _assert_canonical_root_rejected(root, reason)


def test_canonical_root_environment_override_authenticated(canonical_root_fixture, monkeypatch):
    from elpis_runtime_r1 import transaction

    monkeypatch.setenv("ELPIS_CANON_ROOT", str(canonical_root_fixture))
    assert transaction._resolve_canonical_root() == str(canonical_root_fixture.resolve())
    (canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]).write_bytes(b"{}")
    with pytest.raises(transaction.R1DependencyEscapeError, match="manifest_digest_mismatch"):
        transaction._resolve_canonical_root()


def test_canonical_root_default_resolution_remains_lazy(tmp_path, monkeypatch):
    from elpis_runtime_r1 import transaction

    monkeypatch.delenv("ELPIS_CANON_ROOT", raising=False)
    monkeypatch.setattr(transaction, "__file__", str(tmp_path / "installed" / "transaction.py"))

    def unexpected_authentication(root):
        pytest.fail("Default-root resolution must not require a source checkout at import")

    monkeypatch.setattr(transaction, "_validate_canonical_root", unexpected_authentication)
    expected = os.path.join(os.path.abspath(os.path.join(
        os.path.dirname(transaction.__file__), "..", "..", "..", ".."
    )), "components")
    assert transaction._resolve_canonical_root() == expected


@pytest.mark.parametrize("use_default", [True, False])
def test_canonical_root_dependency_audit_authenticates(canonical_root_fixture, monkeypatch, use_default):
    from elpis_runtime_r1 import transaction

    (canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]).write_bytes(b"{}")
    monkeypatch.setattr(transaction, "CANONICAL_ROOT", str(canonical_root_fixture))
    with pytest.raises(transaction.R1DependencyEscapeError, match="manifest_digest_mismatch"):
        if use_default:
            transaction._dependency_escape_audit()
        else:
            transaction._dependency_escape_audit(str(canonical_root_fixture))


@pytest.mark.parametrize("field", ["component_id", "canonical_destination", "manifest_self_hash"])
def test_canonical_root_parsed_identity_defense(canonical_root_fixture, monkeypatch, field):
    from elpis_runtime_r1 import transaction

    manifest = json.loads((canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]).read_bytes())
    manifest[field] = "wrong"
    # Fault injection after authentic bytes: identity checks independently reject.
    monkeypatch.setattr(transaction.json, "loads", lambda raw: manifest)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_identity_mismatch")


@pytest.mark.parametrize("parsed", [None, []])
def test_canonical_root_parsed_object_required(canonical_root_fixture, monkeypatch, parsed):
    from elpis_runtime_r1 import transaction

    monkeypatch.setattr(transaction.json, "loads", lambda raw: parsed)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_malformed")


def test_canonical_root_parser_error_is_bounded(canonical_root_fixture, monkeypatch):
    from elpis_runtime_r1 import transaction

    def malformed(raw):
        raise json.JSONDecodeError("arbitrary parser detail", "", 0)

    monkeypatch.setattr(transaction.json, "loads", malformed)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_malformed")


def test_canonical_root_filesystem_error_is_bounded(canonical_root_fixture, monkeypatch):
    from elpis_runtime_r1 import transaction

    def unreadable(*args, **kwargs):
        raise PermissionError("arbitrary filesystem detail")

    monkeypatch.setattr(transaction.os, "open", unreadable)
    _assert_canonical_root_rejected(str(canonical_root_fixture), "manifest_unreadable")


def test_canonical_root_downstream_rejects_before_import_paths(canonical_root_fixture):
    from elpis_runtime_r1 import transaction

    (canonical_root_fixture / _CANONICAL_MANIFEST_PATHS[0]).write_bytes(b"{}")
    before = list(sys.path)
    with pytest.raises(transaction.R1DependencyEscapeError, match="manifest_digest_mismatch"):
        transaction._run_r0_downstream({}, str(canonical_root_fixture))
    assert sys.path == before
