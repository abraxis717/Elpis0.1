"""HACF R3 Python adapter — thin ctypes wrapper around libr1_hacf_wrapper.so.

Provides:
  - build_corpus_and_index() -> HacfHandle (opaque C pointer)
  - hybrid_retrieve() -> bundle JSON + metadata
  - bundle_from_json() -> RetrievalBundle dataclass
  - get_vector_index_manifest()

All operations are read-only after corpus/index creation.
"""

from __future__ import annotations

import ctypes
import json
import os
from typing import Any

from .contracts import RetrievalBundle, RetrievalItem, _digest
from .errors import R1HacfImportError, R1HacfRetrievalError

# C wrapper library path
WRAPPER_LIB_PATH = os.environ.get(
    "HACF_WRAPPER_LIB",
    "/mnt/primesauce/Elpis_Canon/Elpis/HACF_R3/build_fpic/libr1_hacf_wrapper.so",
)

ELPIS_EMBEDDING_DIM = 384
BUNDLE_JSON_CAP = 1 << 18  # 256KB buffer for bundle JSON


# ---------------------------------------------------------------------------
# ctypes setup
# ---------------------------------------------------------------------------

_lib: ctypes.CDLL | None = None


def _load() -> ctypes.CDLL:
    global _lib
    if _lib is not None:
        return _lib
    if not os.path.exists(WRAPPER_LIB_PATH):
        raise R1HacfImportError(
            "LIB_NOT_FOUND",
            f"HACF wrapper not found at {WRAPPER_LIB_PATH}",
        )
    try:
        lib = ctypes.CDLL(WRAPPER_LIB_PATH)
    except OSError as e:
        raise R1HacfImportError("LIB_LOAD_FAILED", str(e)) from e

    # r1_env_create
    lib.r1_env_create.restype = ctypes.c_void_p
    lib.r1_env_create.argtypes = [
        ctypes.c_char_p,       # state_root
        ctypes.POINTER(ctypes.c_char_p),  # labels
        ctypes.POINTER(ctypes.c_char_p),  # texts
        ctypes.POINTER(ctypes.c_char_p),  # namespaces
        ctypes.POINTER(ctypes.c_char_p),  # authorities
        ctypes.c_int,         # n_docs
        ctypes.c_char_p,      # error_buf[256]
    ]

    # r1_env_destroy
    lib.r1_env_destroy.restype = None
    lib.r1_env_destroy.argtypes = [ctypes.c_void_p]

    # r1_env_embed
    lib.r1_env_embed.restype = ctypes.c_int
    lib.r1_env_embed.argtypes = [
        ctypes.c_void_p,       # env
        ctypes.c_char_p,       # text
        ctypes.c_int,          # text_len
        ctypes.POINTER(ctypes.c_float),  # out
        ctypes.c_int,          # out_dim
    ]

    # r1_env_retrieve
    lib.r1_env_retrieve.restype = ctypes.c_int
    lib.r1_env_retrieve.argtypes = [
        ctypes.c_void_p,       # env
        ctypes.c_char_p,       # query_text
        ctypes.POINTER(ctypes.c_float),  # query_vector
        ctypes.c_int,          # query_dim
        ctypes.c_uint32,       # lexical_limit
        ctypes.c_uint32,       # dense_limit
        ctypes.c_uint32,       # primary_limit
        ctypes.c_uint32,       # total_limit
        ctypes.c_char_p,       # bundle_json_out
        ctypes.c_int,          # bundle_json_cap
        ctypes.c_char_p,       # bundle_digest_out[65]
        ctypes.c_char_p,       # query_digest_out[65]
        ctypes.c_char_p,       # corpus_manifest_digest_out[65]
        ctypes.c_char_p,       # vindex_manifest_digest_out[65]
        ctypes.c_char_p,       # fusion_policy_digest_out[65]
        ctypes.POINTER(ctypes.c_int),  # item_count_out
        ctypes.c_char_p,       # error_buf[256]
    ]

    # getters
    lib.r1_env_corpus_digest.restype = ctypes.c_char_p
    lib.r1_env_corpus_digest.argtypes = [ctypes.c_void_p]

    lib.r1_env_shard_digest.restype = ctypes.c_char_p
    lib.r1_env_shard_digest.argtypes = [ctypes.c_void_p]

    lib.r1_env_corpus_manifest.restype = ctypes.c_char_p
    lib.r1_env_corpus_manifest.argtypes = [ctypes.c_void_p]

    lib.r1_env_vindex_manifest.restype = ctypes.c_char_p
    lib.r1_env_vindex_manifest.argtypes = [ctypes.c_void_p]

    _lib = lib
    return lib


# ---------------------------------------------------------------------------
# Managed handle
# ---------------------------------------------------------------------------

class HacfHandle:
    """Owning handle to HACF C resources with deterministic cleanup."""

    def __init__(self) -> None:
        self._ptr: ctypes.c_void_p = ctypes.c_void_p(0)
        self.corpus_manifest_json = ""
        self.corpus_digest = ""
        self.shard_digest = ""
        self.vindex_manifest_json = ""
        self.doc_map: dict[str, str] = {}
        self.chunk_refs: dict[str, dict] = {}

    @property
    def _valid(self) -> bool:
        return self._ptr != ctypes.c_void_p(0)

    def destroy(self) -> None:
        if self._valid:
            lib = _load()
            lib.r1_env_destroy(self._ptr)
            self._ptr = ctypes.c_void_p(0)

    def __enter__(self) -> "HacfHandle":
        return self

    def __exit__(self, *args: Any) -> None:
        self.destroy()


# ---------------------------------------------------------------------------
# Build pipeline
# ---------------------------------------------------------------------------

def build_corpus_and_index(
    state_root: str,
    documents: list[tuple[str, str, str, str]],
) -> HacfHandle:
    """Build a complete HACF R3 environment from fixture documents.

    Args:
        state_root: Directory for corpus state and cold storage.
        documents: List of (label, text, namespace, authority) tuples.

    Returns:
        HacfHandle with corpus and index ready for retrieval.
    """
    lib = _load()

    # Sort documents by label for determinism
    sorted_docs = sorted(documents, key=lambda x: x[0])

    n = len(sorted_docs)
    labels = (ctypes.c_char_p * n)(*[l.encode("utf-8") for l, _, _, _ in sorted_docs])
    texts = (ctypes.c_char_p * n)(*[t.encode("utf-8") for _, t, _, _ in sorted_docs])
    namespaces = (ctypes.c_char_p * n)(*[ns.encode("utf-8") for _, _, ns, _ in sorted_docs])
    authorities = (ctypes.c_char_p * n)(*[a.encode("utf-8") for _, _, _, a in sorted_docs])

    err_buf = ctypes.create_string_buffer(256)
    ptr = lib.r1_env_create(
        state_root.encode("utf-8"),
        labels, texts, namespaces, authorities,
        n, err_buf,
    )
    if not ptr:
        err = err_buf.value.decode("utf-8") if err_buf.value else "unknown"
        raise R1HacfRetrievalError("ENV_CREATE_FAILED", err)

    err = err_buf.value.decode("utf-8") if err_buf.value else ""
    if err != "ok":
        lib.r1_env_destroy(ptr)
        raise R1HacfRetrievalError("ENV_CREATE_FAILED", err)

    handle = HacfHandle()
    handle._ptr = ptr
    handle.corpus_manifest_json = lib.r1_env_corpus_manifest(ptr).decode("utf-8") if lib.r1_env_corpus_manifest(ptr) else ""
    handle.corpus_digest = lib.r1_env_corpus_digest(ptr).decode("utf-8") if lib.r1_env_corpus_digest(ptr) else ""
    handle.shard_digest = lib.r1_env_shard_digest(ptr).decode("utf-8") if lib.r1_env_shard_digest(ptr) else ""
    handle.vindex_manifest_json = lib.r1_env_vindex_manifest(ptr).decode("utf-8") if lib.r1_env_vindex_manifest(ptr) else ""

    return handle


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def hybrid_retrieve(
    handle: HacfHandle,
    query_text: str,
    query_vector: list[float] | None = None,
    lexical_limit: int = 50,
    dense_limit: int = 50,
    primary_limit: int = 30,
    total_limit: int = 60,
) -> dict[str, Any]:
    """Execute hybrid retrieval against the prepared corpus/index.

    Returns dict with bundle_json, digests, item_count, and parsed data.
    """
    if not handle._valid:
        raise R1HacfRetrievalError("NO_ENVIRONMENT", "Handle has no valid corpus/index")

    lib = _load()

    # Embed query for dense retrieval
    if query_vector is None:
        vec = (ctypes.c_float * ELPIS_EMBEDDING_DIM)()
        rc = lib.r1_env_embed(
            handle._ptr,
            query_text.encode("utf-8"),
            len(query_text.encode("utf-8")),
            vec,
            ELPIS_EMBEDDING_DIM,
        )
        if rc != 0:
            raise R1HacfRetrievalError("EMBED_QUERY_FAILED", f"rc={rc}")
        query_vector = list(vec)

    vec_ptr = (ctypes.c_float * len(query_vector))(*query_vector)

    json_buf = ctypes.create_string_buffer(BUNDLE_JSON_CAP)
    bundle_digest_buf = ctypes.create_string_buffer(65)
    query_digest_buf = ctypes.create_string_buffer(65)
    corpus_manifest_digest_buf = ctypes.create_string_buffer(65)
    vindex_manifest_digest_buf = ctypes.create_string_buffer(65)
    fusion_policy_digest_buf = ctypes.create_string_buffer(65)
    item_count = ctypes.c_int(0)
    err_buf = ctypes.create_string_buffer(256)

    rc = lib.r1_env_retrieve(
        handle._ptr,
        query_text.encode("utf-8"),
        vec_ptr, len(query_vector),
        lexical_limit, dense_limit,
        primary_limit, total_limit,
        json_buf, BUNDLE_JSON_CAP,
        bundle_digest_buf,
        query_digest_buf,
        corpus_manifest_digest_buf,
        vindex_manifest_digest_buf,
        fusion_policy_digest_buf,
        ctypes.byref(item_count),
        err_buf,
    )

    if rc != 0:
        err = err_buf.value.decode("utf-8") if err_buf.value else "unknown"
        raise R1HacfRetrievalError(f"HACF_RETRIEVE_{rc}", err)

    json_str = json_buf.value.decode("utf-8") if json_buf.value else ""
    bundle_digest = bundle_digest_buf.value.decode("utf-8") if bundle_digest_buf.value else ""
    query_digest = query_digest_buf.value.decode("utf-8") if query_digest_buf.value else ""
    corpus_md = corpus_manifest_digest_buf.value.decode("utf-8") if corpus_manifest_digest_buf.value else ""
    vindex_md = vindex_manifest_digest_buf.value.decode("utf-8") if vindex_manifest_digest_buf.value else ""
    fusion_pd = fusion_policy_digest_buf.value.decode("utf-8") if fusion_policy_digest_buf.value else ""

    bundle_data = json.loads(json_str) if json_str else {}

    return {
        "bundle_json": json_str,
        "bundle_digest": bundle_digest,
        "item_count": item_count.value,
        "query_digest": query_digest,
        "corpus_manifest_digest": corpus_md,
        "vector_index_manifest_digest": vindex_md,
        "graph_snapshot_digest": "",  # no graph in qualification
        "fusion_policy_digest": fusion_pd,
        "hacf_package_digest": "",
        "data": bundle_data,
    }


def get_vector_index_manifest(handle: HacfHandle) -> tuple[str, str]:
    """Get vector index manifest JSON and its digest."""
    import hashlib
    lib = _load()
    j = lib.r1_env_vindex_manifest(handle._ptr).decode("utf-8") if lib.r1_env_vindex_manifest(handle._ptr) else ""
    d = hashlib.sha256(j.encode("utf-8")).hexdigest() if j else ""
    return j, d


# ---------------------------------------------------------------------------
# Bundle to Python object
# ---------------------------------------------------------------------------

def bundle_from_json(bundle_json_str: str, metadata: dict[str, str]) -> RetrievalBundle:
    """Parse a HACF bundle JSON string into a RetrievalBundle dataclass.

    The C library outputs text_hex/namespace_hex; we decode to plain text
    for the Python dataclass.
    """
    data = json.loads(bundle_json_str)

    items: list[RetrievalItem] = []
    for item in data.get("items", []):
        # C library may output text as hex-encoded
        raw_text = item.get("text") or ""
        if not raw_text and item.get("text_hex"):
            raw_text = bytes.fromhex(item["text_hex"]).decode("utf-8", errors="replace")

        raw_ns = item.get("namespace") or item.get("namespace_hex") or ""
        if raw_ns.startswith("0x"):
            raw_ns = raw_ns[2:]
        # namespace_hex is hex-encoded string of the namespace bytes
        if item.get("namespace_hex") and not item.get("namespace"):
            try:
                raw_ns = bytes.fromhex(item["namespace_hex"]).decode("utf-8", errors="replace")
            except ValueError:
                pass

        items.append(RetrievalItem(
            chunk_digest=item.get("chunk_digest", ""),
            doc_digest=item.get("doc_digest", ""),
            namespace=raw_ns,
            authority=item.get("authority", ""),
            graph_parent_digest=item.get("graph_parent_digest", "0" * 64),
            text_digest=item.get("text_digest", ""),
            fusion_score_key=int(item.get("fusion_score_key", 0)),
            dense_score_key=int(item.get("dense_score_key", 0)),
            lexical_rank=int(item.get("lexical_rank", 0)),
            dense_rank=int(item.get("dense_rank", 0)),
            final_rank=int(item.get("final_rank", 0)),
            source_mask=int(item.get("source_mask", 0)),
            item_kind=int(item.get("item_kind", 1)),
            graph_hop=int(item.get("graph_hop", 0)),
            edge_type=int(item.get("edge_type", 0)),
            edge_authority=int(item.get("edge_authority", 0)),
            text=raw_text,
            text_bytes=int(item.get("text_bytes", len(raw_text.encode("utf-8")))),
        ))

    bundle_digest = metadata.get("bundle_digest", "")
    if not bundle_digest:
        bundle_digest = _digest(data)

    return RetrievalBundle(
        schema=data.get("schema", "elpis.retrieval_bundle.v1"),
        query_digest=metadata.get("query_digest", ""),
        corpus_manifest_digest=metadata.get("corpus_manifest_digest", ""),
        vector_index_manifest_digest=metadata.get("vector_index_manifest_digest", ""),
        graph_snapshot_digest=metadata.get("graph_snapshot_digest", ""),
        fusion_policy_digest=metadata.get("fusion_policy_digest", ""),
        bundle_digest=bundle_digest,
        hacf_package_digest=metadata.get("hacf_package_digest", ""),
        corpus_epoch=int(metadata.get("corpus_epoch", 0)),
        vector_index_epoch=int(metadata.get("vector_index_epoch", 0)),
        items=tuple(items),
    )
