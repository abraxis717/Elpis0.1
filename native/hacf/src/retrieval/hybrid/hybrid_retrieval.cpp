#include "elpis/hybrid_retrieval.h"
#include "elpis/embedding_provider.h"
#include "elpis/sha256.h"
#include "hybrid_internal.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <utility>
#include <vector>

struct elpis_hybrid_retriever {
    elpis_corpus *corpus = nullptr;
    elpis_vector_index *index = nullptr;
    const elpis_context_graph *graph = nullptr;
    elpis_hybrid_policy policy{};
    char policy_digest[65]{};
    char corpus_digest[65]{};
    char index_digest[65]{};
    char profile_digest[65]{};
    char graph_digest[65]{};
};

namespace {

static const char kZeroDigest[] =
    "0000000000000000000000000000000000000000000000000000000000000000";

struct Candidate {
    std::string chunk;
    std::string doc;
    std::string ns;
    std::string authority;
    uint32_t lexical_rank = 0;
    uint32_t dense_rank = 0;
    int64_t dense_score_key = 0;
    uint32_t source_mask = 0;
    uint64_t fusion_key = 0;
};

static thread_local const elpis_hybrid_retriever *tls_owner = nullptr;
static thread_local elpis_hybrid_error tls_error{};

static bool valid_token(const char *s, size_t max_len) {
    if (!s || !*s) return false;
    size_t n = strnlen(s, max_len + 1);
    if (n == 0 || n > max_len) return false;
    for (size_t i = 0; i < n; ++i) {
        unsigned char c = (unsigned char)s[i];
        if (c < 0x20 || c == 0x7f) return false;
    }
    return true;
}
static bool valid_authority(const char *s) {
    return s && (!std::strcmp(s, "canonical") || !std::strcmp(s, "reference") ||
                 !std::strcmp(s, "advisory") || !std::strcmp(s, "provisional"));
}

static void put_le32(elpis_sha256_ctx *h, uint32_t v) {
    uint8_t b[4] = {(uint8_t)v, (uint8_t)(v >> 8), (uint8_t)(v >> 16), (uint8_t)(v >> 24)};
    elpis_sha256_update(h, b, sizeof b);
}
static void put_le64(elpis_sha256_ctx *h, uint64_t v) {
    uint8_t b[8];
    for (unsigned i = 0; i < 8; ++i) b[i] = (uint8_t)(v >> (8u * i));
    elpis_sha256_update(h, b, sizeof b);
}
static void put_string(elpis_sha256_ctx *h, const char *s) {
    uint64_t n = s ? std::strlen(s) : 0;
    put_le64(h, n);
    if (n) elpis_sha256_update(h, s, (size_t)n);
}

static int set_error(elpis_hybrid_retriever *r, int status, int cause, const char *detail);

static uint64_t source_score(uint32_t weight, uint32_t k, uint32_t rank) {
    if (!rank) return 0;
    return ((uint64_t)weight * ELPIS_HYBRID_SCORE_SCALE) / ((uint64_t)k + rank);
}

static int query_digest(const elpis_hybrid_query *q, const char profile_digest[65], char out[65]) {
    if (!q || !q->text || !q->vector || q->dimensions != ELPIS_EMBEDDING_DIM) return -1;
    size_t n = strnlen(q->text, 65536);
    if (n == 0 || n > 65535 || !elpis_vector_all_finite(q->vector, q->dimensions)) return -1;
    static const char domain[] = "elpis.hybrid.query.v1";
    elpis_sha256_ctx h;
    elpis_sha256_init(&h);
    elpis_sha256_update(&h, domain, sizeof domain);
    put_le64(&h, n);
    elpis_sha256_update(&h, q->text, n);
    put_string(&h, q->namespace_filter);
    put_string(&h, q->authority_filter);
    elpis_sha256_update(&h, profile_digest, 64);
    put_le32(&h, q->dimensions);
    for (uint32_t i = 0; i < q->dimensions; ++i) {
        uint32_t bits;
        std::memcpy(&bits, &q->vector[i], sizeof bits);
        put_le32(&h, bits);
    }
    uint8_t d[32];
    elpis_sha256_final(&h, d);
    elpis_hex32(d, out);
    return 0;
}

static int manifest_corpus(elpis_corpus *c, char out[65]) {
    char *j = nullptr;
    int rc = elpis_corpus_manifest_json(c, &j, out);
    if (j) elpis_free(j);
    return rc;
}
static int manifest_index(elpis_vector_index *ix, char out[65]) {
    char *j = nullptr;
    int rc = elpis_vector_index_manifest_json(ix, &j, out);
    if (j) elpis_free(j);
    return rc;
}

static bool metadata_equal(const Candidate &c, const char *doc, const char *ns, const char *auth) {
    return c.doc == doc && c.ns == ns && c.authority == auth;
}

static int load_item_text(elpis_hybrid_retriever *r, const elpis_chunk_ref &ref,
                          R3OwnedItem &item) {
    char *text = nullptr;
    if (elpis_corpus_chunk_text(r->corpus, ref.chunk_digest, &text) != 0)
        return set_error(r, ELPIS_HYBRID_E_CORPUS, 0, elpis_corpus_error(r->corpus));
    try {
        item.text.assign(text ? text : "");
    } catch (...) {
        if (text) elpis_free(text);
        return set_error(r, ELPIS_HYBRID_E_INTERNAL, 0, "allocation failure while freezing text");
    }
    if (text) elpis_free(text);
    uint8_t d[32];
    char hex[65];
    elpis_sha256(item.text.data(), item.text.size(), d);
    elpis_hex32(d, hex);
    item.text_digest = hex;
    return ELPIS_HYBRID_OK;
}

} // namespace

namespace {

static int set_error(elpis_hybrid_retriever *r, int status, int cause, const char *detail) {
    tls_owner = r;
    std::memset(&tls_error, 0, sizeof tls_error);
    tls_error.status = status;
    tls_error.cause = cause;
    std::snprintf(tls_error.detail, sizeof tls_error.detail, "%s", detail ? detail : "");
    return status;
}

static int retrieve_impl(elpis_hybrid_retriever *r, const elpis_hybrid_query *q,
                         elpis_retrieval_bundle **out) {
    if (!q || !out || !q->text || !q->vector || q->dimensions != ELPIS_EMBEDDING_DIM)
        return set_error(r, ELPIS_HYBRID_E_INVAL, 0, "invalid query");
    *out = nullptr;
    size_t qlen = strnlen(q->text, 65536);
    if (qlen == 0 || qlen > 65535 || !elpis_vector_all_finite(q->vector, q->dimensions))
        return set_error(r, ELPIS_HYBRID_E_INVAL, 0, "query text or vector rejected");
    if (q->namespace_filter && !valid_token(q->namespace_filter, 95))
        return set_error(r, ELPIS_HYBRID_E_INVAL, 0, "invalid namespace filter");
    if (q->authority_filter && !valid_authority(q->authority_filter))
        return set_error(r, ELPIS_HYBRID_E_INVAL, 0, "invalid authority filter");

    char current_corpus[65], current_index[65];
    if (manifest_corpus(r->corpus, current_corpus) != 0)
        return set_error(r, ELPIS_HYBRID_E_CORPUS, 0, "corpus manifest failed");
    if (manifest_index(r->index, current_index) != 0)
        return set_error(r, ELPIS_HYBRID_E_VECTOR, 0, "vector index manifest failed");
    if (std::strcmp(current_corpus, r->corpus_digest) != 0 ||
        std::strcmp(current_index, r->index_digest) != 0)
        return set_error(r, ELPIS_HYBRID_E_DRIFT, 0, "retrieval epoch dependency changed");

    std::vector<elpis_hit> lexical(r->policy.lexical_limit);
    uint32_t ln = 0;
    if (elpis_corpus_search_lexical(r->corpus, q->text, q->namespace_filter,
                                    q->authority_filter, r->policy.lexical_limit,
                                    lexical.data(), &ln) != 0)
        return set_error(r, ELPIS_HYBRID_E_CORPUS, 0, elpis_corpus_error(r->corpus));

    std::vector<elpis_vector_hit> dense(r->policy.dense_limit);
    elpis_vector_query vq{};
    vq.vector = q->vector;
    vq.dimensions = q->dimensions;
    vq.k = r->policy.dense_limit;
    vq.ns_filter = q->namespace_filter;
    vq.authority_filter = q->authority_filter;
    uint32_t dn = 0;
    int vrc = elpis_vector_index_search(r->index, &vq, dense.data(), &dn);
    if (vrc != ELPIS_VEC_OK) {
        const elpis_vec_error *e = elpis_vector_index_last_error(r->index);
        return set_error(r, ELPIS_HYBRID_E_VECTOR, e ? e->status : vrc,
                         e ? e->detail : elpis_vector_index_error(r->index));
    }

    std::map<std::string, Candidate> pool;
    for (uint32_t i = 0; i < ln; ++i) {
        Candidate &c = pool[lexical[i].chunk_digest];
        if (c.chunk.empty()) {
            c.chunk = lexical[i].chunk_digest;
            c.doc = lexical[i].doc_digest;
            c.ns = lexical[i].ns;
            c.authority = lexical[i].authority;
        } else if (!metadata_equal(c, lexical[i].doc_digest, lexical[i].ns, lexical[i].authority)) {
            return set_error(r, ELPIS_HYBRID_E_INTEGRITY, 0, "lexical metadata conflict");
        }
        c.lexical_rank = i + 1;
        c.source_mask |= ELPIS_RSRC_LEXICAL;
    }
    for (uint32_t i = 0; i < dn; ++i) {
        Candidate &c = pool[dense[i].chunk_digest];
        if (c.chunk.empty()) {
            c.chunk = dense[i].chunk_digest;
            c.doc = dense[i].doc_digest;
            c.ns = dense[i].ns;
            c.authority = dense[i].authority;
        } else if (!metadata_equal(c, dense[i].doc_digest, dense[i].ns, dense[i].authority)) {
            return set_error(r, ELPIS_HYBRID_E_INTEGRITY, 0, "dense metadata conflict");
        }
        c.dense_rank = i + 1;
        c.dense_score_key = dense[i].score_key;
        c.source_mask |= ELPIS_RSRC_DENSE;
    }
    if (pool.size() > ELPIS_HYBRID_MAX_CANDIDATES)
        return set_error(r, ELPIS_HYBRID_E_LIMIT, 0, "candidate limit exceeded");

    std::vector<Candidate *> ordered;
    ordered.reserve(pool.size());
    for (auto &kv : pool) {
        Candidate &c = kv.second;
        c.fusion_key = source_score(r->policy.lexical_weight, r->policy.rrf_k, c.lexical_rank) +
                       source_score(r->policy.dense_weight, r->policy.rrf_k, c.dense_rank);
        ordered.push_back(&c);
    }
    std::sort(ordered.begin(), ordered.end(), [](const Candidate *a, const Candidate *b) {
        if (a->fusion_key != b->fusion_key) return a->fusion_key > b->fusion_key;
        return a->chunk < b->chunk;
    });

    std::vector<R3OwnedItem> items;
    items.reserve(r->policy.total_limit);
    std::set<std::string> selected;
    uint32_t primaries = std::min<uint32_t>(r->policy.primary_limit, (uint32_t)ordered.size());
    for (uint32_t i = 0; i < primaries; ++i) {
        Candidate &c = *ordered[i];
        elpis_chunk_ref ref{};
        if (elpis_corpus_chunk_lookup(r->corpus, c.chunk.c_str(), &ref) != 0)
            return set_error(r, ELPIS_HYBRID_E_INTEGRITY, 0, "primary chunk absent from corpus");
        if (!metadata_equal(c, ref.doc_digest, ref.ns, ref.authority))
            return set_error(r, ELPIS_HYBRID_E_INTEGRITY, 0, "primary metadata drift");
        R3OwnedItem x;
        x.chunk_digest = c.chunk;
        x.doc_digest = c.doc;
        x.ns = c.ns;
        x.authority = c.authority;
        x.graph_parent_digest = kZeroDigest;
        x.fusion_score_key = c.fusion_key;
        x.dense_score_key = c.dense_score_key;
        x.lexical_rank = c.lexical_rank;
        x.dense_rank = c.dense_rank;
        x.source_mask = c.source_mask;
        x.item_kind = ELPIS_RITEM_PRIMARY;
        if (load_item_text(r, ref, x) != ELPIS_HYBRID_OK) return tls_error.status;
        items.push_back(std::move(x));
        selected.insert(c.chunk);
    }

    if (r->graph && items.size() < r->policy.total_limit) {
        uint32_t seed_count = std::min<uint32_t>(r->policy.graph_seed_limit, primaries);
        const uint32_t page = 64;
        std::vector<elpis_context_neighbor> neigh(page);
        for (uint32_t seed = 0; seed < seed_count && items.size() < r->policy.total_limit; ++seed) {
            uint32_t accepted = 0, offset = 0;
            while (accepted < r->policy.graph_neighbors_per_seed &&
                   items.size() < r->policy.total_limit) {
                uint32_t got = 0;
                if (elpis_context_graph_neighbors(r->graph, items[seed].chunk_digest.c_str(),
                                                  r->policy.min_graph_authority, offset, page,
                                                  neigh.data(), &got) != 0)
                    return set_error(r, ELPIS_HYBRID_E_GRAPH, 0, "graph neighbor lookup failed");
                for (uint32_t j = 0; j < got && accepted < r->policy.graph_neighbors_per_seed &&
                                     items.size() < r->policy.total_limit; ++j) {
                    if (selected.count(neigh[j].chunk_digest)) continue;
                    elpis_chunk_ref ref{};
                    if (elpis_corpus_chunk_lookup(r->corpus, neigh[j].chunk_digest, &ref) != 0)
                        return set_error(r, ELPIS_HYBRID_E_INTEGRITY, 0,
                                         "graph neighbor absent from corpus");
                    if (q->namespace_filter && std::strcmp(q->namespace_filter, ref.ns) != 0) continue;
                    if (q->authority_filter && std::strcmp(q->authority_filter, ref.authority) != 0) continue;
                    R3OwnedItem x;
                    x.chunk_digest = ref.chunk_digest;
                    x.doc_digest = ref.doc_digest;
                    x.ns = ref.ns;
                    x.authority = ref.authority;
                    x.graph_parent_digest = items[seed].chunk_digest;
                    x.source_mask = ELPIS_RSRC_GRAPH;
                    auto ci = pool.find(x.chunk_digest);
                    if (ci != pool.end()) {
                        x.source_mask |= ci->second.source_mask;
                        x.lexical_rank = ci->second.lexical_rank;
                        x.dense_rank = ci->second.dense_rank;
                        x.dense_score_key = ci->second.dense_score_key;
                        x.fusion_score_key = ci->second.fusion_key;
                    }
                    x.item_kind = ELPIS_RITEM_CONTEXT;
                    x.graph_hop = 1;
                    x.edge_type = neigh[j].edge_type;
                    x.edge_authority = neigh[j].authority;
                    if (load_item_text(r, ref, x) != ELPIS_HYBRID_OK) return tls_error.status;
                    selected.insert(x.chunk_digest);
                    items.push_back(std::move(x));
                    ++accepted;
                }
                offset += got;
                if (got < page) break;
            }
        }
    }

    /* Freeze the epoch across the whole operation, not just at entry. A corpus
     * ingest or shard admission racing the query invalidates the handoff. */
    char final_corpus[65], final_index[65];
    if (manifest_corpus(r->corpus, final_corpus) != 0 ||
        manifest_index(r->index, final_index) != 0)
        return set_error(r, ELPIS_HYBRID_E_INTERNAL, 0, "post-search manifest failed");
    if (std::strcmp(final_corpus, r->corpus_digest) != 0 ||
        std::strcmp(final_index, r->index_digest) != 0)
        return set_error(r, ELPIS_HYBRID_E_DRIFT, 0, "retrieval epoch changed during search");

    for (uint32_t i = 0; i < items.size(); ++i) items[i].final_rank = i;
    char qdigest[65];
    if (query_digest(q, r->profile_digest, qdigest) != 0)
        return set_error(r, ELPIS_HYBRID_E_INVAL, 0, "query identity failed");
    elpis_retrieval_bundle *b = r3_bundle_create(
        std::string(q->text, qlen), qdigest, r->corpus_digest, r->index_digest,
        r->graph_digest, r->policy_digest, q->namespace_filter, q->authority_filter,
        std::move(items));
    if (!b) return set_error(r, ELPIS_HYBRID_E_INTERNAL, 0, "bundle construction failed");
    *out = b;
    set_error(r, ELPIS_HYBRID_OK, 0, "ok");
    return ELPIS_HYBRID_OK;
}

} // namespace

extern "C" {

const char *elpis_hybrid_strerror(int status) {
    switch (status) {
    case ELPIS_HYBRID_OK: return "ok";
    case ELPIS_HYBRID_E_INVAL: return "invalid argument";
    case ELPIS_HYBRID_E_CORPUS: return "corpus failure";
    case ELPIS_HYBRID_E_VECTOR: return "vector failure";
    case ELPIS_HYBRID_E_GRAPH: return "graph failure";
    case ELPIS_HYBRID_E_DRIFT: return "retrieval epoch drift";
    case ELPIS_HYBRID_E_INTEGRITY: return "integrity failure";
    case ELPIS_HYBRID_E_LIMIT: return "limit exceeded";
    default: return "internal failure";
    }
}

int elpis_hybrid_policy_default(elpis_hybrid_policy *p) {
    if (!p) return -1;
    std::memset(p, 0, sizeof *p);
    p->abi_version = ELPIS_HYBRID_ABI_VERSION;
    p->lexical_limit = 32;
    p->dense_limit = 32;
    p->primary_limit = 12;
    p->graph_seed_limit = 4;
    p->graph_neighbors_per_seed = 2;
    p->total_limit = 20;
    p->rrf_k = 60;
    p->lexical_weight = 100;
    p->dense_weight = 100;
    p->min_graph_authority = 0;
    return 0;
}

int elpis_hybrid_policy_validate(const elpis_hybrid_policy *p) {
    if (!p || p->abi_version != ELPIS_HYBRID_ABI_VERSION ||
        p->lexical_limit == 0 || p->dense_limit == 0 ||
        p->lexical_limit > ELPIS_HYBRID_MAX_CANDIDATES ||
        p->dense_limit > ELPIS_HYBRID_MAX_CANDIDATES ||
        (uint64_t)p->lexical_limit + p->dense_limit > ELPIS_HYBRID_MAX_CANDIDATES ||
        p->primary_limit == 0 || p->primary_limit > p->total_limit ||
        p->total_limit > ELPIS_HYBRID_MAX_BUNDLE_ITEMS ||
        p->graph_seed_limit > p->primary_limit ||
        p->graph_neighbors_per_seed > ELPIS_HYBRID_MAX_BUNDLE_ITEMS ||
        p->rrf_k == 0 || p->rrf_k > 100000 ||
        p->lexical_weight == 0 || p->lexical_weight > 1000000 ||
        p->dense_weight == 0 || p->dense_weight > 1000000 ||
        p->min_graph_authority > 3)
        return -1;
    for (uint32_t v : p->reserved) if (v != 0) return -1;
    return 0;
}

int elpis_hybrid_policy_digest(const elpis_hybrid_policy *p, char out[65]) {
    if (!out || elpis_hybrid_policy_validate(p) != 0) return -1;
    static const char domain[] = "elpis.hybrid_policy.v1";
    elpis_sha256_ctx h;
    elpis_sha256_init(&h);
    elpis_sha256_update(&h, domain, sizeof domain);
    const uint32_t vals[] = {p->abi_version, p->lexical_limit, p->dense_limit,
        p->primary_limit, p->graph_seed_limit, p->graph_neighbors_per_seed,
        p->total_limit, p->rrf_k, p->lexical_weight, p->dense_weight,
        p->min_graph_authority};
    for (uint32_t v : vals) put_le32(&h, v);
    uint8_t d[32];
    elpis_sha256_final(&h, d);
    elpis_hex32(d, out);
    return 0;
}

int elpis_hybrid_retriever_create(elpis_corpus *corpus, elpis_vector_index *index,
                                  const elpis_context_graph *graph,
                                  const elpis_hybrid_policy *policy,
                                  elpis_hybrid_retriever **out) {
    if (!corpus || !index || !policy || !out || elpis_hybrid_policy_validate(policy) != 0)
        return ELPIS_HYBRID_E_INVAL;
    *out = nullptr;
    try {
        std::unique_ptr<elpis_hybrid_retriever> r(new elpis_hybrid_retriever());
        r->corpus = corpus;
        r->index = index;
        r->graph = graph;
        r->policy = *policy;
        if (elpis_hybrid_policy_digest(policy, r->policy_digest) != 0 ||
            manifest_corpus(corpus, r->corpus_digest) != 0 ||
            manifest_index(index, r->index_digest) != 0) {
            return ELPIS_HYBRID_E_INTERNAL;
        }
        char index_corpus[65];
        if (elpis_vector_index_profile_digest(index, r->profile_digest, index_corpus) != ELPIS_VEC_OK ||
            std::strcmp(index_corpus, r->corpus_digest) != 0 ||
            std::strcmp(index_corpus, kZeroDigest) == 0) {
            return ELPIS_HYBRID_E_INTEGRITY;
        }
        if (graph) {
            if (elpis_context_graph_digest(graph, r->graph_digest) != 0) {
                return ELPIS_HYBRID_E_GRAPH;
            }
        } else {
            std::memcpy(r->graph_digest, kZeroDigest, 65);
        }
        *out = r.release();
        return ELPIS_HYBRID_OK;
    } catch (...) {
        return ELPIS_HYBRID_E_INTERNAL;
    }
}

void elpis_hybrid_retriever_destroy(elpis_hybrid_retriever *r) { delete r; }
const char *elpis_hybrid_retriever_error(const elpis_hybrid_retriever *r) {
    return tls_owner == r ? tls_error.detail : "";
}
const elpis_hybrid_error *elpis_hybrid_retriever_last_error(const elpis_hybrid_retriever *r) {
    return tls_owner == r ? &tls_error : nullptr;
}

int elpis_hybrid_retrieve(elpis_hybrid_retriever *r, const elpis_hybrid_query *q,
                          elpis_retrieval_bundle **out) {
    if (!r) return ELPIS_HYBRID_E_INVAL;
    try {
        return retrieve_impl(r, q, out);
    } catch (...) {
        if (out) *out = nullptr;
        return set_error(r, ELPIS_HYBRID_E_INTERNAL, 0, "unhandled internal exception");
    }
}

} // extern C
