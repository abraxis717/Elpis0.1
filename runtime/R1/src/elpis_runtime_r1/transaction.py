"""R1 transaction orchestrator — bounded pre-refinement retrieval + R0 downstream.

RequestContext -> RetrievalQueryDeriver -> HACFRetrievalProvider
  -> RetrievalBundleValidator -> RetrievalBudgetGuard
  -> EvidenceBoundRequestAdapter -> qualified Runtime R0 transaction
  -> R1 composite receipt
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from typing import Any

from .budget import RetrievalBudget, check_budget
from .bundle_validation import validate_bundle
from .contracts import (
    RECEIPT_SCHEMA,
    R1TransactionReceipt,
    RETRIEVAL_CONTRACT_VERSION,
    _canonical_bytes,
    _digest,
    _sha256_hex,
    EvidenceEnvelope,
)
from .evidence_adapter import build_evidence_envelope, evidence_envelope_digest
from .errors import (
    R1CanonicalMutationError,
    R1DependencyEscapeError,
    R1DownstreamR0Error,
    R1Error,
)
from .hacf_adapter import (
    build_corpus_and_index,
    bundle_from_json,
    get_vector_index_manifest,
    hybrid_retrieve,
    ELPIS_EMBEDDING_DIM,
)
from .query_derivation import derive_query
from .receipt import receipt_bytes_hash

CANONICAL_ROOT = os.environ.get(
    "ELPIS_CANON_ROOT",
    "/mnt/primesauce/Elpis_Canon/Elpis",
)

R0_ROOT = os.environ.get(
    "ELPIS_R0_ROOT",
    "/mnt/primesauce/Elpis_Canon/Elpis_Runtime_Integration/R0",
)

BUILD_DIR = os.environ.get(
    "ELPIS_BUILD_DIR",
    "/mnt/primesauce/Elpis_Canon/Elpis_Runtime_Integration/R1_Build",
)

FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "/mnt/primesauce/Elpis_Canon/HashAdressedCascadeFabric",
    "/mnt/primesauce/Elpis_Companions/Elpis_Semantic_Fabric",
    "/mnt/primesauce/Elpis_Canon/Pipeline/P0ControlProtocol",
    "/mnt/primesauce/Elpis_Canon/TRMFractalSpine",
    "/mnt/primesauce/Elpis_Canon/DarwinianMatrix",
    "/mnt/primesauce/Elpis_Canon/Elpis_Parallel",
)

DEFAULT_REQUEST: dict[str, Any] = {
    "request_id": "r1_canonical_001",
    "prompt": "def solution(x): return x + 1",
    "domain": "python",
    "entrypoint": "solution",
    "parameters": ("x",),
    "decoder_hints": (("body", "return x + 1"),),
}

QUALIFICATION_DOCUMENTS: list[tuple[str, str, str, str]] = [
    ("alpha", "alpha engine exact retrieval anchor for deterministic qualification",
     "elpis.docs", "canonical"),
    ("beta", "beta companion context bridge for retrieval validation",
     "elpis.docs", "reference"),
    ("gamma", "gamma vector semantic neighbor for dense retrieval testing",
     "elpis.code", "canonical"),
    ("delta", "delta unrelated background note for negative filtering",
     "elpis.notes", "advisory"),
]


def _ensure_dirs() -> None:
    os.makedirs(BUILD_DIR, exist_ok=True)


def _dependency_escape_audit() -> str:
    errors: list[str] = []
    import importlib
    canonical_pkg = os.path.realpath(CANONICAL_ROOT)
    for module_name in [
        "elpis_fractal_spine", "elpis_p0",
        "elpis_grid81_adjudication", "DarwinianMatrix",
    ]:
        try:
            mod = importlib.import_module(module_name)
            mod_file = getattr(mod, "__file__", "")
            if mod_file:
                real = os.path.realpath(mod_file)
                for prefix in FORBIDDEN_PREFIXES:
                    if real.startswith(prefix):
                        errors.append(f"{module_name} -> {real}")
        except ImportError:
            pass
    audit = {
        "canonical_root": canonical_pkg,
        "forbidden_prefixes": list(FORBIDDEN_PREFIXES),
        "escapes_found": len(errors),
        "errors": errors,
        "status": "CLEAN" if not errors else "ESCAPE_DETECTED",
    }
    if errors:
        raise R1DependencyEscapeError("DEPENDENCY_ESCAPE",
                                      f"{len(errors)} escapes")
    return _digest(audit)


def _canonical_nonmutation_check() -> str:
    r0_report = os.path.join(os.path.dirname(R0_ROOT), "R0_Audit", "FINAL_REPORT.json")
    if os.path.exists(r0_report):
        with open(r0_report) as f:
            report = json.load(f)
        if report.get("disposition") != "ELPIS_RUNTIME_INTEGRATION_R0_DETERMINISTIC_TRANSACTION_QUALIFIED":
            raise R1CanonicalMutationError("R0_NOT_QUALIFIED",
                                           report.get("disposition", "?"))
        if report.get("canonical_assembly_modified", True):
            raise R1CanonicalMutationError("CANONICAL_MODIFIED", "changed")
    return _digest({"r0_qualified": True, "canonical_unmodified": True})


def _compute_component_manifest_digests() -> str:
    r1_src = os.path.join(R0_ROOT, "..", "R1", "src")
    manifests: dict[str, str] = {}
    for root, dirs, files in sorted(os.walk(r1_src)):
        dirs[:] = sorted(d for d in dirs if d not in ("__pycache__",))
        for f in sorted(files):
            if f.endswith(".py"):
                fp = os.path.join(root, f)
                with open(fp, "rb") as fh:
                    manifests[os.path.relpath(fp, r1_src)] = hashlib.sha256(fh.read()).hexdigest()
    return _digest(manifests)


def execute_r1_transaction(
    request: dict[str, Any] | None = None,
    documents: list[tuple[str, str, str, str]] | None = None,
) -> R1TransactionReceipt:
    """Execute full R1 deterministic retrieval + R0 transaction."""
    if request is None:
        request = DEFAULT_REQUEST
    if documents is None:
        documents = QUALIFICATION_DOCUMENTS

    _ensure_dirs()
    budget = RetrievalBudget()
    request_id = request.get("request_id", "r1_canonical_001")
    request_digest = _digest(request)

    # Phase 2: Query derivation
    query = derive_query(request, budget_params=budget.to_canonical_dict())
    query_derivation_digest = _digest(query.to_canonical_dict())

    # Phase 3: Build HACF corpus + index
    corpus_state = tempfile.mkdtemp(dir=BUILD_DIR, prefix="corpus_")
    handle = build_corpus_and_index(corpus_state, documents)

    try:
        corpus_digest = handle.corpus_digest
        corpus_identity = _digest(handle.corpus_manifest_json)
        vindex_json, vindex_digest = get_vector_index_manifest(handle)
        vindex_identity = _digest(vindex_json)

        # Phase 4: Hybrid retrieval
        result = hybrid_retrieve(
            handle,
            query_text=query.query_text,
            lexical_limit=budget.max_lexical_candidates,
            dense_limit=budget.max_dense_candidates,
            primary_limit=budget.max_fused_results,
            total_limit=budget.max_total_chunks,
        )

        # Phase 5: Bundle construction
        bundle_metadata = {
            "query_digest": result["query_digest"],
            "corpus_manifest_digest": result["corpus_manifest_digest"],
            "vector_index_manifest_digest": result["vector_index_manifest_digest"],
            "graph_snapshot_digest": result["graph_snapshot_digest"],
            "fusion_policy_digest": result["fusion_policy_digest"],
            "hacf_package_digest": result["hacf_package_digest"],
            "corpus_epoch": 1,
            "vector_index_epoch": 1,
        }
        bundle = bundle_from_json(result["bundle_json"], bundle_metadata)

        # Phase 6: Bundle validation + budget
        # Use the C library's query digest (the one actually bound into the bundle)
        hacf_query_digest = result["query_digest"]
        total_text_bytes = sum(i.text_bytes for i in bundle.items)
        budget_decision = validate_bundle(
            bundle,
            expected_query_digest=hacf_query_digest,
            corpus_manifest_digest=result["corpus_manifest_digest"],
            budget=budget,
        )
        if budget_decision is None:
            budget_decision = check_budget(
                budget,
                {"lexical": 0, "dense": 0, "fused": len(bundle.items),
                 "context": 0, "total": len(bundle.items)},
                total_text_bytes,
            )
        budget_decision_digest = _digest(budget_decision.to_canonical_dict())

        # Phase 7: Evidence envelope
        envelope = build_evidence_envelope(
            original_request_digest=request_digest,
            retrieval_query_digest=query.query_digest,
            bundle=bundle,
            budget_decision_digest=budget_decision_digest,
        )
        envelope_digest = evidence_envelope_digest(envelope)

        # Phase 8: Chunk identities
        chunk_identities = _digest([i.chunk_digest for i in bundle.items])

        # Phase 9: Context expansion digest
        context_expansion_digest = _digest({
            "graph_seed_limit": 0,
            "graph_neighbors_per_seed": 0,
            "context_items": sum(1 for i in bundle.items if i.item_kind == 2),
        })

        # Phase 10: R0 downstream
        r0_receipt_digest = _run_r0_downstream(request)

        # Phase 11-13: Audits
        component_manifests = _compute_component_manifest_digests()
        dep_audit_digest = _dependency_escape_audit()
        _canonical_nonmutation_check()

        # Phase 14: R1 composite receipt
        receipt = R1TransactionReceipt(
            transaction_id=request_id,
            request_digest=request_digest,
            retrieval_contract_version=RETRIEVAL_CONTRACT_VERSION,
            query_derivation_digest=query_derivation_digest,
            retrieval_query_digest=query.query_digest,
            retrieval_budget_digest=budget.digest(),
            corpus_identity=corpus_identity,
            corpus_epoch=bundle.corpus_epoch,
            vector_index_identity=vindex_identity,
            vector_index_epoch=bundle.vector_index_epoch,
            retrieval_bundle_schema=bundle.schema,
            retrieval_bundle_digest=bundle.bundle_digest,
            retrieved_chunk_identities=chunk_identities,
            context_expansion_digest=context_expansion_digest,
            evidence_envelope_digest=envelope_digest,
            r0_receipt_digest=r0_receipt_digest,
            final_artifact_digest=r0_receipt_digest,
            termination_disposition="DETERMINISTIC_TRANSACTION_COMPLETE",
            component_manifest_digests=component_manifests,
            dependency_resolution_audit_digest=dep_audit_digest,
            runtime_admission_receipt=False,
        )

        with open(os.path.join(BUILD_DIR, "r1_receipt.json"), "w") as f:
            f.write(receipt.to_canonical_json())

        return receipt

    finally:
        handle.destroy()
        import shutil
        shutil.rmtree(corpus_state, ignore_errors=True)


def _run_r0_downstream(request: dict[str, Any]) -> str:
    """Execute downstream R0 transaction. Returns R0 receipt digest."""
    r0_src = os.path.join(R0_ROOT, "src")
    if r0_src not in sys.path:
        sys.path.insert(0, r0_src)
    for p in [
        os.path.join(CANONICAL_ROOT, "TRMFractalSpine", "src"),
        os.path.join(CANONICAL_ROOT, "Pipeline", "P0ControlProtocol", "src"),
        os.path.join(CANONICAL_ROOT, "Grid81DeterministicStructuralAdjudicator", "src"),
        os.path.join(CANONICAL_ROOT, "Grid81StructuralSemantics", "src"),
        CANONICAL_ROOT,
    ]:
        if p not in sys.path:
            sys.path.insert(0, p)

    try:
        from elpis_runtime_r0.transaction import execute_r0_transaction
    except ImportError as e:
        raise R1DownstreamR0Error("R0_IMPORT_FAILED", str(e)) from e

    try:
        r0_receipt = execute_r0_transaction(request=request)
        if hasattr(r0_receipt, "receipt_bytes"):
            return hashlib.sha256(r0_receipt.receipt_bytes()).hexdigest()
        elif hasattr(r0_receipt, "to_canonical_json"):
            return hashlib.sha256(r0_receipt.to_canonical_json().encode("utf-8")).hexdigest()
        else:
            return hashlib.sha256(json.dumps(r0_receipt, sort_keys=True).encode("utf-8")).hexdigest()
    except Exception as e:
        raise R1DownstreamR0Error("R0_TRANSACTION_FAILED", str(e)) from e
