"""R1 transaction orchestrator — bounded pre-refinement retrieval + R0 downstream.

RequestContext -> RetrievalQueryDeriver -> HACFRetrievalProvider
  -> RetrievalBundleValidator -> RetrievalBudgetGuard
  -> EvidenceBoundRequestAdapter -> qualified Runtime R0 transaction
  -> R1 composite receipt
"""

from __future__ import annotations

from contextlib import ExitStack
import errno
import hashlib
import json
import os
import sys
import tempfile
import stat
from types import MappingProxyType
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

# External authority: candidate roots never supply or override these release pins.
# Keep the R0/R1 copies identical; neither package depends on the other at import.
EXPECTED_CANONICAL_MANIFESTS = MappingProxyType({
    "Grid81/COMPONENT_MANIFEST.json": MappingProxyType({
        "sha256": "b3d79b251f4ef162d8b959de0c4adb06c5a82e83b40bfe5d2609e0ad75560256",
        "component_id": "Grid81_Canonical_Substrate",
        "canonical_destination": "Grid81",
        "manifest_self_hash": "5f0f3c220b6454f5157ebaeae92898b6eff2c252a08443d8fc5e9ece5f2da021",
    }),
    "DarwinianMatrix/COMPONENT_MANIFEST.json": MappingProxyType({
        "sha256": "af86c3eaf908124edc26a63c79f83dde350947a63d854689f5295e44e99abd0e",
        "component_id": "DarwinianMatrix",
        "canonical_destination": "DarwinianMatrix",
        "manifest_self_hash": "e26091a7cf232db0c88e3833d16ebff1da7a8898b27905e436dea90c370512d1",
    }),
    "Pipeline/P0ControlProtocol/COMPONENT_MANIFEST.json": MappingProxyType({
        "sha256": "704186993a52f7504a3d4abdf33cf4f24b22cfbbee8a1ba85992614677c2a4fd",
        "component_id": "P0ControlProtocol",
        "canonical_destination": "Pipeline/P0ControlProtocol",
        "manifest_self_hash": "1f29d1d3e0aad16581f0ef3b2bf6f4336b9a80e7a79c119b56c68b410d96f825",
    }),
})


def _validate_canonical_root(root: str) -> str:
    """Authenticate the three required manifests against runtime-owned byte pins.

    Directory descriptors and O_NOFOLLOW prevent symlink traversal between the
    root and each manifest, including replacement between metadata and open.
    Authentication covers these manifests only, not all component contents.
    """
    if not isinstance(root, str) or not root:
        raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "empty/non-string root")
    if "\x00" in root:
        raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "root_malformed")
    try:
        absolute = os.path.abspath(root)
        real = os.path.realpath(absolute)
        if real == os.path.sep:
            raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "filesystem root")
        if os.path.islink(absolute):
            raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "symlink root")
        # Keep module import portable; unsupported platforms fail only on use.
        if not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")):
            raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "manifest_io_unsupported")
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        with ExitStack() as root_handles:
            root_fd = os.open(absolute, directory_flags)
            root_handles.callback(os.close, root_fd)
            for relative, expected in EXPECTED_CANONICAL_MANIFESTS.items():
                with ExitStack() as handles:
                    parent_fd = root_fd
                    parts = relative.split("/")
                    for index, part in enumerate(parts):
                        metadata = os.stat(part, dir_fd=parent_fd, follow_symlinks=False)
                        if stat.S_ISLNK(metadata.st_mode):
                            raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "manifest_symlink")
                        if index < len(parts) - 1:
                            if not stat.S_ISDIR(metadata.st_mode):
                                raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "manifest_missing")
                            parent_fd = os.open(part, directory_flags, dir_fd=parent_fd)
                            handles.callback(os.close, parent_fd)
                        else:
                            if not stat.S_ISREG(metadata.st_mode):
                                raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "manifest_not_regular")
                            # O_NONBLOCK avoids blocking on a raced-in FIFO.
                            fd = os.open(part, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                         dir_fd=parent_fd)
                            handles.callback(os.close, fd)
                            if not stat.S_ISREG(os.fstat(fd).st_mode):
                                raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "manifest_not_regular")
                            with os.fdopen(fd, "rb", closefd=False) as manifest_file:
                                raw = manifest_file.read()
                if hashlib.sha256(raw).hexdigest() != expected["sha256"]:
                    raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "manifest_digest_mismatch")
                try:
                    manifest = json.loads(raw)
                except (ValueError, UnicodeError, RecursionError):
                    raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "manifest_malformed") from None
                if not isinstance(manifest, dict):
                    raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "manifest_malformed")
                if any(manifest.get(field) != expected[field] for field in (
                    "component_id", "canonical_destination", "manifest_self_hash",
                )):
                    raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "manifest_identity_mismatch")
    except (FileNotFoundError, NotADirectoryError):
        raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "manifest_missing") from None
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "manifest_symlink") from None
        raise R1DependencyEscapeError("CANONICAL_ROOT_INVALID", "manifest_unreadable") from None
    return real


def _resolve_canonical_root() -> str:
    """Resolve source-layout root; validate every explicit environment override."""
    env_root = os.environ.get("ELPIS_CANON_ROOT")
    if env_root:
        return _validate_canonical_root(env_root)
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    )
    return os.path.join(repo_root, "components")


CANONICAL_ROOT = _resolve_canonical_root()


def _resolve_r0_root() -> str:
    """Resolve R0 root portably."""
    env_r0 = os.environ.get("ELPIS_R0_ROOT")
    if env_r0:
        return env_r0
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    )
    return os.path.join(repo_root, "runtime", "R0")


R0_ROOT = _resolve_r0_root()


def _resolve_build_dir() -> str:
    """Resolve build directory portably."""
    env_build = os.environ.get("ELPIS_BUILD_DIR")
    if env_build:
        return env_build
    return tempfile.mkdtemp(prefix="elpis_r1_build_")


BUILD_DIR: str = ""  # resolved lazily per-transaction

_PRIVATE_MOUNT = os.path.join(os.path.sep, "mnt", "primesauce")
FORBIDDEN_PREFIXES: tuple[str, ...] = (
    # Secondary legacy-root veto; canonical containment is the primary control.
    os.path.join(_PRIVATE_MOUNT, "Elpis_Canon", "Pipeline", "P0ControlProtocol"),
    os.path.join(_PRIVATE_MOUNT, "Elpis_Canon", "TRMFractalSpine"),
    os.path.join(_PRIVATE_MOUNT, "Elpis_Canon", "DarwinianMatrix"),
    os.path.join(_PRIVATE_MOUNT, "Elpis_Canon", "Grid81"),
    os.path.join(_PRIVATE_MOUNT, "Elpis_Companions", "Elpis_Semantic_Fabric"),
    os.path.join(_PRIVATE_MOUNT, "Elpis_Canon", "HashAdressedCascadeFabric"),
    os.path.join(_PRIVATE_MOUNT, "Elpis_Canon", "Elpis_Parallel"),
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
    global BUILD_DIR
    if not BUILD_DIR:
        BUILD_DIR = _resolve_build_dir()
    os.makedirs(BUILD_DIR, exist_ok=True)


AUDITED_MODULES: tuple[str, ...] = ('elpis_fractal_spine', 'elpis_p0', 'elpis_grid81_adjudication', 'elpis_grid81_semantics', 'DarwinianMatrix')


def _dependency_escape_audit(canon_root: str | None = None) -> str:
    """Veto unresolved imports and imports outside the canonical assembly."""
    import importlib

    canonical_root = _validate_canonical_root(
        CANONICAL_ROOT if canon_root is None else canon_root
    )
    canonical_pkg = canonical_root.rstrip(os.sep) + os.sep
    extensions = os.environ.get("ELPIS_FORBIDDEN_ROOTS", "").split(os.pathsep)
    forbidden = tuple(sorted({
        os.path.realpath(root).rstrip(os.sep) + os.sep
        for root in (*FORBIDDEN_PREFIXES, *extensions) if root
    }))
    errors = []
    resolved = []
    for module_name in AUDITED_MODULES:
        try:
            mod = importlib.import_module(module_name)
        except ImportError as exc:
            errors.append(f"UNRESOLVED_IMPORT: {module_name}: {exc}")
            continue
        mod_file = getattr(mod, "__file__", None)
        if not mod_file:
            errors.append(f"NO_MODULE_FILE: {module_name}")
            continue
        real = os.path.realpath(mod_file)
        resolved.append((module_name, real))
        if os.path.commonpath((real, canonical_root)) != canonical_root:
            errors.append(f"OUTSIDE_CANONICAL: {module_name}: {real}")
        if any(real.startswith(root) for root in forbidden):
            errors.append(f"FORBIDDEN_ROOT: {module_name}: {real}")
    audit = {
        "canonical_root": canonical_pkg,
        "forbidden_prefixes": list(forbidden),
        "modules_checked": len(resolved),
        "resolved_modules": resolved,
        "escapes_found": len(errors),
        "errors": errors,
        "status": "CLEAN" if not errors else "ESCAPE_DETECTED",
    }
    if errors:
        raise R1DependencyEscapeError("DEPENDENCY_ESCAPE", "; ".join(errors))
    return _digest(audit)


def _canonical_nonmutation_check() -> str:
    r0_report = os.path.join(os.path.dirname(R0_ROOT), "R0_Audit", "FINAL_REPORT.json")
    if not os.path.isfile(r0_report):
        raise R1CanonicalMutationError("R0_AUDIT_REPORT_MISSING", r0_report)
    with open(r0_report, encoding="utf-8") as f:
        report = json.load(f)
    if report.get("disposition") != "ELPIS_RUNTIME_INTEGRATION_R0_DETERMINISTIC_TRANSACTION_QUALIFIED":
        raise R1CanonicalMutationError("R0_NOT_QUALIFIED", report.get("disposition", "?"))
    if "canonical_assembly_modified" not in report:
        raise R1CanonicalMutationError("CANONICAL_FIELD_ABSENT", r0_report)
    if report["canonical_assembly_modified"] is not False:
        raise R1CanonicalMutationError("CANONICAL_MODIFIED", "explicit false required")
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
        r0_receipt_digest = _run_r0_downstream(request, _validate_canonical_root(CANONICAL_ROOT))

        # Phase 11-13: Audits
        component_manifests = _compute_component_manifest_digests()
        dep_audit_digest = _dependency_escape_audit(_validate_canonical_root(CANONICAL_ROOT))
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


def _run_r0_downstream(request: dict[str, Any], canonical_root: str) -> str:
    """Execute downstream R0 transaction. Returns R0 receipt digest."""
    canonical_root = _validate_canonical_root(canonical_root)
    r0_src = os.path.join(R0_ROOT, "src")
    if r0_src not in sys.path:
        sys.path.insert(0, r0_src)
    for p in [
        os.path.join(canonical_root, "TRMFractalSpine", "src"),
        os.path.join(canonical_root, "Pipeline", "P0ControlProtocol", "src"),
        os.path.join(canonical_root, "Grid81DeterministicStructuralAdjudicator", "src"),
        os.path.join(canonical_root, "Grid81StructuralSemantics", "src"),
        canonical_root,
    ]:
        if p not in sys.path:
            sys.path.insert(0, p)

    try:
        from elpis_runtime_r0.transaction import execute_r0_transaction
    except ImportError as e:
        raise R1DownstreamR0Error("R0_IMPORT_FAILED", str(e)) from e

    try:
        r0_receipt = execute_r0_transaction(request=request, project_root=canonical_root)
        if hasattr(r0_receipt, "receipt_bytes"):
            return hashlib.sha256(r0_receipt.receipt_bytes()).hexdigest()
        elif hasattr(r0_receipt, "to_canonical_json"):
            return hashlib.sha256(r0_receipt.to_canonical_json().encode("utf-8")).hexdigest()
        else:
            return hashlib.sha256(json.dumps(r0_receipt, sort_keys=True).encode("utf-8")).hexdigest()
    except Exception as e:
        raise R1DownstreamR0Error("R0_TRANSACTION_FAILED", str(e)) from e
