/* retrieval_bundle_verify.cpp — Independent RetrievalBundle verification.
 *
 * Verifies every returned bundle independently of the mere R3 success status.
 */
#include "elpis_semantic/retrieval_bundle_verify.h"
#include "elpis_semantic/identity.h"
#include "elpis/retrieval_bundle.h"
#include "elpis/corpus.h"
#include "elpis/sha256.h"

#include <cstring>
#include <cstdint>
#include <string>

namespace {

static const char kZeroDigest[] =
    "0000000000000000000000000000000000000000000000000000000000000000";

static std::string hex_bytes(const char *s, size_t n) {
    static const char h[] = "0123456789abcdef";
    std::string o;
    o.resize(n * 2);
    for (size_t i = 0; i < n; ++i) {
        unsigned char c = (unsigned char)s[i];
        o[i * 2] = h[c >> 4];
        o[i * 2 + 1] = h[c & 15];
    }
    return o;
}

} // namespace

extern "C" {

int elpis_bundle_verify(
    bundle_verify_result *result,
    elpis_retrieval_bundle *bundle,
    const elpis_r3_epoch_binding_v1 *epoch_binding,
    const char *expected_query_digest)
{
    if (!result || !bundle || !epoch_binding) {
        result->status = BUNDLE_VERIFY_NONCANONICAL_ORDER;
        std::strncpy(result->detail, "null input", sizeof(result->detail));
        return SEMANTIC_E_INVAL;
    }

    std::memset(result, 0, sizeof(*result));
    result->item_index = 0xFFFFFFFF;

    /* Get bundle identity */
    char qd[65], cd[65], vd[65], gd[65], pd[65], bd[65], hd[65];
    if (elpis_retrieval_bundle_identity(bundle, qd, cd, vd, gd, pd, bd, hd) != 0) {
        result->status = BUNDLE_VERIFY_NONCANONICAL_ORDER;
        std::strncpy(result->detail, "bundle identity failed", sizeof(result->detail));
        return SEMANTIC_E_INVAL;
    }

    /* Verify query digest */
    if (expected_query_digest && std::strcmp(qd, expected_query_digest) != 0) {
        result->status = BUNDLE_VERIFY_QUERY_MISMATCH;
        std::snprintf(result->detail, sizeof(result->detail),
            "query mismatch: bundle=%s expected=%s", qd, expected_query_digest);
        return SEMANTIC_OK; /* verified — with failure */
    }

    /* Verify corpus manifest digest */
    if (std::strcmp(cd, epoch_binding->corpus_manifest_digest) != 0) {
        result->status = BUNDLE_VERIFY_CORPUS_MISMATCH;
        std::strncpy(result->detail, "corpus manifest mismatch", sizeof(result->detail));
        return SEMANTIC_OK;
    }

    /* Verify vector index manifest digest */
    if (std::strcmp(vd, epoch_binding->vector_index_manifest_digest) != 0) {
        result->status = BUNDLE_VERIFY_INDEX_MISMATCH;
        std::strncpy(result->detail, "vector index manifest mismatch", sizeof(result->detail));
        return SEMANTIC_OK;
    }

    /* Verify graph snapshot digest (or all-zero) */
    if (std::strcmp(gd, epoch_binding->context_graph_digest) != 0) {
        result->status = BUNDLE_VERIFY_GRAPH_MISMATCH;
        std::strncpy(result->detail, "graph snapshot mismatch", sizeof(result->detail));
        return SEMANTIC_OK;
    }

    /* Verify fusion policy digest */
    if (std::strcmp(pd, epoch_binding->hybrid_policy_digest) != 0) {
        result->status = BUNDLE_VERIFY_POLICY_MISMATCH;
        std::strncpy(result->detail, "fusion policy mismatch", sizeof(result->detail));
        return SEMANTIC_OK;
    }

    /* Per-item verification */
    uint32_t count = elpis_retrieval_bundle_item_count(bundle);
    std::uint32_t seen_final_ranks = 0; /* bitmask for detecting duplicates in small bundles */

    for (uint32_t i = 0; i < count; ++i) {
        elpis_retrieval_item_view view;
        if (elpis_retrieval_bundle_item(bundle, i, &view) != 0) {
            result->status = BUNDLE_VERIFY_NONCANONICAL_ORDER;
            result->item_index = i;
            std::snprintf(result->detail, sizeof(result->detail),
                "item %u access failed", i);
            return SEMANTIC_OK;
        }

        /* Verify item kind */
        if (view.item_kind != ELPIS_RITEM_PRIMARY && view.item_kind != ELPIS_RITEM_CONTEXT) {
            result->status = BUNDLE_VERIFY_INVALID_KIND;
            result->item_index = i;
            std::snprintf(result->detail, sizeof(result->detail),
                "invalid item_kind=%u at index %u", view.item_kind, i);
            return SEMANTIC_OK;
        }

        /* Verify source mask is valid subset */
        if ((view.source_mask & ~0x07u) != 0) {
            result->status = BUNDLE_VERIFY_INVALID_SOURCE_MASK;
            result->item_index = i;
            std::snprintf(result->detail, sizeof(result->detail),
                "invalid source_mask=%u at index %u", view.source_mask, i);
            return SEMANTIC_OK;
        }

        /* Verify source mask has at least one source */
        if (view.source_mask == 0) {
            result->status = BUNDLE_VERIFY_INVALID_SOURCE_MASK;
            result->item_index = i;
            std::snprintf(result->detail, sizeof(result->detail),
                "zero source_mask at index %u", i);
            return SEMANTIC_OK;
        }

        /* Verify graph_hop */
        if (view.graph_hop > 1) {
            result->status = BUNDLE_VERIFY_IMPOSSIBLE_HOP;
            result->item_index = i;
            std::snprintf(result->detail, sizeof(result->detail),
                "graph_hop=%u at index %u", view.graph_hop, i);
            return SEMANTIC_OK;
        }

        /* Verify graph_parent_digest: all-zero for primary items */
        if (view.item_kind == ELPIS_RITEM_PRIMARY &&
            std::strcmp(view.graph_parent_digest, kZeroDigest) != 0) {
            result->status = BUNDLE_VERIFY_INVALID_GRAPH_PARENT;
            result->item_index = i;
            std::snprintf(result->detail, sizeof(result->detail),
                "primary item has nonzero graph_parent at index %u", i);
            return SEMANTIC_OK;
        }

        /* Verify final_rank matches index (canonical order) */
        if (view.final_rank != i) {
            result->status = BUNDLE_VERIFY_DUPLICATE_RANK;
            result->item_index = i;
            std::snprintf(result->detail, sizeof(result->detail),
                "final_rank=%u != index=%u", view.final_rank, i);
            return SEMANTIC_OK;
        }

        /* Verify no duplicate final ranks */
        if (i < 32) { /* bitmask only practical for small bundles */
            if (seen_final_ranks & ((uint32_t)1 << view.final_rank)) {
                result->status = BUNDLE_VERIFY_DUPLICATE_RANK;
                result->item_index = i;
                std::strncpy(result->detail, "duplicate final_rank", sizeof(result->detail));
                return SEMANTIC_OK;
            }
            seen_final_ranks |= (uint32_t)1 << view.final_rank;
        }

        /* Verify item text digest: compute SHA-256 of text and compare */
        if (view.text && view.text_bytes > 0) {
            uint8_t computed[32];
            char hex[65];
            elpis_sha256(view.text, view.text_bytes, computed);
            elpis_hex32(computed, hex);
            if (std::strcmp(hex, view.text_digest) != 0) {
                result->status = BUNDLE_VERIFY_ITEM_TEXT_MISMATCH;
                result->item_index = i;
                std::snprintf(result->detail, sizeof(result->detail),
                    "text_digest mismatch at index %u", i);
                return SEMANTIC_OK;
            }
        }

        /* Verify chunk digest is nonzero */
        if (std::strcmp(view.chunk_digest, kZeroDigest) == 0) {
            result->status = BUNDLE_VERIFY_METADATA_CONFLICT;
            result->item_index = i;
            std::strncpy(result->detail, "zero chunk_digest", sizeof(result->detail));
            return SEMANTIC_OK;
        }

        /* Verify ordering: higher fusion_score_key first, then lower chunk_digest */
        if (i > 0) {
            elpis_retrieval_item_view prev;
            elpis_retrieval_bundle_item(bundle, i - 1, &prev);
            if (view.fusion_score_key > prev.fusion_score_key) {
                result->status = BUNDLE_VERIFY_NONCANONICAL_ORDER;
                result->item_index = i;
                std::strncpy(result->detail, "fusion_score_key ordering violation",
                    sizeof(result->detail));
                return SEMANTIC_OK;
            }
            if (view.fusion_score_key == prev.fusion_score_key &&
                std::strcmp(view.chunk_digest, prev.chunk_digest) < 0) {
                result->status = BUNDLE_VERIFY_NONCANONICAL_ORDER;
                result->item_index = i;
                std::strncpy(result->detail, "chunk_digest tiebreak violation",
                    sizeof(result->detail));
                return SEMANTIC_OK;
            }
        }
    }

    /* Verify package identity by recomputing from bundle JSON */
    {
        char *json = nullptr;
        char computed_digest[65];
        if (elpis_retrieval_bundle_json(bundle, &json, computed_digest) == 0 && json) {
            if (std::strcmp(computed_digest, bd) != 0) {
                result->status = BUNDLE_VERIFY_PACKAGE_MISMATCH;
                std::snprintf(result->detail, sizeof(result->detail),
                    "bundle digest mismatch: computed=%s stored=%s", computed_digest, bd);
                elpis_free(json);
                return SEMANTIC_OK;
            }
            elpis_free(json);
        }
    }

    /* All checks passed */
    result->status = BUNDLE_VERIFY_OK;
    return SEMANTIC_OK;
}

} // extern "C"
