#ifndef ELPIS_HYBRID_INTERNAL_H
#define ELPIS_HYBRID_INTERNAL_H

#include "elpis/retrieval_bundle.h"

#include <cstdint>
#include <string>
#include <vector>

struct R3OwnedItem {
    std::string chunk_digest;
    std::string doc_digest;
    std::string ns;
    std::string authority;
    std::string graph_parent_digest;
    std::string text_digest;
    std::string text;
    uint64_t fusion_score_key = 0;
    int64_t dense_score_key = 0;
    uint32_t lexical_rank = 0;
    uint32_t dense_rank = 0;
    uint32_t final_rank = 0;
    uint32_t source_mask = 0;
    uint32_t item_kind = 0;
    uint32_t graph_hop = 0;
    uint32_t edge_type = 0;
    uint32_t edge_authority = 0;
};

elpis_retrieval_bundle *r3_bundle_create(
    const std::string &query_text,
    const char query_digest[65],
    const char corpus_manifest_digest[65],
    const char vector_index_manifest_digest[65],
    const char graph_snapshot_digest[65],
    const char fusion_policy_digest[65],
    const char *namespace_filter,
    const char *authority_filter,
    std::vector<R3OwnedItem> &&items);

#endif
