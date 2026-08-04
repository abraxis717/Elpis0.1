#ifndef HACF_R3_TEST_SUPPORT_H
#define HACF_R3_TEST_SUPPORT_H

#include "r2_test_support.h"
#include "elpis/context_graph.h"
#include "elpis/chunking.h"
#include "elpis/corpus.h"
#include "elpis/hybrid_retrieval.h"
#include "elpis/retrieval_bundle.h"
#include "elpis/vector_index.h"

#include <cstring>
#include <map>
#include <string>
#include <vector>

namespace r3t {

struct Env {
    std::string root;
    elpis_corpus *corpus = nullptr;
    elpis_embedder *embedder = nullptr;
    fms_ctx *fms = nullptr;
    elpis_vector_index *index = nullptr;
    elpis_embedding_profile profile{};
    char corpus_digest[65]{};
    std::map<std::string, std::string> doc_by_label;
    std::map<std::string, elpis_chunk_ref> ref_by_label;
    std::map<std::string, std::string> text_by_label;
    void *shard_bytes = nullptr;
    size_t shard_len = 0;

    ~Env() {
        if (index) elpis_vector_index_destroy(index);
        if (fms) fms_destroy(fms);
        if (embedder) elpis_embedder_destroy(embedder);
        if (corpus) elpis_corpus_close(corpus);
        std::free(shard_bytes);
    }

    int build(const std::string &base) {
        root = base;
        r2t::rmtree(root);
        r2t::mkdirp(root);
        struct D { const char *label, *text, *ns, *auth; } docs[] = {
            {"alpha", "alpha engine exact retrieval anchor", "elpis.docs", "canonical"},
            {"beta",  "beta companion context bridge", "elpis.docs", "reference"},
            {"gamma", "gamma vector semantic neighbor", "elpis.code", "canonical"},
            {"delta", "delta unrelated background note", "elpis.notes", "advisory"}
        };
        if (elpis_corpus_open((root + "/corpus").c_str(), &corpus) != 0) return -1;
        for (const D &d : docs) {
            elpis_ingest_meta m{};
            m.ns = d.ns; m.authority = d.auth; m.media_type = ELPIS_MT_TEXT; m.origin = d.label;
            elpis_ingest_result ir{};
            if (elpis_corpus_ingest_bytes(corpus, d.text, std::strlen(d.text), &m, &ir) != 0)
                return -1;
            doc_by_label[d.label] = ir.doc_digest;
            text_by_label[d.label] = d.text;
        }
        char *cj = nullptr;
        if (elpis_corpus_manifest_json(corpus, &cj, corpus_digest) != 0) return -1;
        elpis_free(cj);
        std::vector<elpis_chunk_ref> refs(16);
        uint32_t n = 0;
        if (elpis_corpus_list_chunks(corpus, nullptr, nullptr, 0, refs.size(), refs.data(), &n) != 0)
            return -1;
        for (uint32_t i = 0; i < n; ++i)
            for (const auto &kv : doc_by_label)
                if (kv.second == refs[i].doc_digest) ref_by_label[kv.first] = refs[i];
        if (ref_by_label.size() != 4) return -1;

        if (elpis_embedder_fixture_create(ELPIS_NORM_L2, &embedder) != 0) return -1;
        if (elpis_embedder_profile(embedder, &profile) != 0) return -1;
        std::vector<std::vector<float>> vecs;
        std::vector<elpis_vshard_input> inputs;
        for (const auto &kv : ref_by_label) {
            char *text = nullptr;
            if (elpis_corpus_chunk_text(corpus, kv.second.chunk_digest, &text) != 0) return -1;
            vecs.emplace_back(ELPIS_EMBEDDING_DIM);
            if (elpis_embedder_embed(embedder, text, std::strlen(text), vecs.back().data(),
                                     ELPIS_EMBEDDING_DIM) != 0) {
                elpis_free(text); return -1;
            }
            elpis_free(text);
            elpis_vshard_input in{};
            std::snprintf(in.chunk_digest, sizeof in.chunk_digest, "%s", kv.second.chunk_digest);
            std::snprintf(in.doc_digest, sizeof in.doc_digest, "%s", kv.second.doc_digest);
            in.ns = kv.second.ns; in.authority = kv.second.authority; in.vector = vecs.back().data();
            inputs.push_back(in);
        }
        char shard_digest[65];
        if (elpis_vshard_build(inputs.data(), inputs.size(), &profile, corpus_digest,
                               &shard_bytes, &shard_len, shard_digest) != 0) return -1;
        fms = r2t::make_fms(root + "/cold", 16ull << 20);
        if (!fms) return -1;
        if (elpis_vector_index_create(fms, &profile, corpus_digest, &index) != ELPIS_VEC_OK)
            return -1;
        if (elpis_vector_index_add_shard_bytes(index, shard_bytes, shard_len, nullptr) != ELPIS_VEC_OK)
            return -1;
        return 0;
    }

    std::vector<float> embed(const std::string &s) const {
        std::vector<float> v(ELPIS_EMBEDDING_DIM);
        elpis_embedder_embed(embedder, s.data(), s.size(), v.data(), ELPIS_EMBEDDING_DIM);
        return v;
    }
};

inline elpis_context_graph *graph_for(const Env &e, bool two_hop = false,
                                      uint32_t authority = 2) {
    std::vector<elpis_context_edge_input> edges;
    auto add = [&](const char *from, const char *to, uint32_t type) {
        elpis_context_edge_input x{};
        std::snprintf(x.subject_chunk_digest, sizeof x.subject_chunk_digest, "%s",
                      e.ref_by_label.at(from).chunk_digest);
        std::snprintf(x.object_chunk_digest, sizeof x.object_chunk_digest, "%s",
                      e.ref_by_label.at(to).chunk_digest);
        std::string p = r2t::hex_of(std::string("edge/") + from + "/" + to);
        std::snprintf(x.provenance_digest, sizeof x.provenance_digest, "%s", p.c_str());
        x.edge_type = type; x.authority = authority; edges.push_back(x);
    };
    add("alpha", "gamma", 1);
    add("beta", "gamma", 1);
    if (two_hop) add("gamma", "delta", 2);
    elpis_context_graph *g = nullptr;
    if (elpis_context_graph_create(edges.data(), edges.size(), &g) != 0) return nullptr;
    return g;
}

inline elpis_hybrid_query query(const Env &e, const char *text_label,
                                const char *vector_label, std::vector<float> &storage) {
    storage = e.embed(e.text_by_label.at(vector_label));
    elpis_hybrid_query q{};
    q.text = e.text_by_label.at(text_label).c_str();
    q.vector = storage.data();
    q.dimensions = ELPIS_EMBEDDING_DIM;
    return q;
}

} // namespace r3t
#endif
