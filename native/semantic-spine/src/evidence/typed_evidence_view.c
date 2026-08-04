/* typed_evidence_view.c — Typed-evidence read-only view implementation. */

#include "elpis_semantic/typed_evidence_view.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"




#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
static const char TYPED_VIEW_DOMAIN[] = "elpis.semantic.typed_evidence_view.v1";

void elpis_typed_evidence_view_init(elpis_typed_evidence_view_v1 *view) {
    memset(view, 0, sizeof(*view));
    view->abi_version = TYPED_EVIDENCE_VIEW_ABI_VERSION;
}

int elpis_typed_evidence_view_identity(const elpis_typed_evidence_view_v1 *view,
                                        hacf_digest *out) {
    if (!view || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    elpis_sha256_update(&ctx, (const uint8_t *)TYPED_VIEW_DOMAIN,
                       strlen(TYPED_VIEW_DOMAIN));

    uint32_t v = __builtin_bswap32(view->abi_version);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_update(&ctx, view->base_snapshot_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, view->query_overlay_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(view->embedding_collection_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < view->embedding_collection_count; i++) {
        elpis_sha256_update(&ctx, view->embedding_collection_digests[i].bytes,
                          HACF_DIGEST_BYTES);
    }

    elpis_sha256_update(&ctx, view->retrieval_expansion_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, view->admission_layer_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, view->view_policy_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(view->admitted_claim_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < view->admitted_claim_count; i++) {
        elpis_sha256_update(&ctx, view->admitted_claim_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(view->admitted_relation_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < view->admitted_relation_count; i++) {
        elpis_sha256_update(&ctx, view->admitted_relation_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(view->source_span_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < view->source_span_count; i++) {
        elpis_sha256_update(&ctx, view->source_span_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_typed_evidence_view_validate(const elpis_typed_evidence_view_v1 *view) {
    if (!view) return SEMANTIC_E_INVAL;

    if (view->abi_version != TYPED_EVIDENCE_VIEW_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    /* Required digests */
    if (digest_is_zero(&view->base_snapshot_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&view->query_overlay_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&view->retrieval_expansion_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&view->admission_layer_digest))
        return SEMANTIC_E_INVAL;

    /* Counts bounded */
    if (view->embedding_collection_count > TYPED_VIEW_MAX_EMBEDDING_COLLECTIONS)
        return SEMANTIC_E_INVAL;
    if (view->admitted_claim_count > TYPED_VIEW_MAX_CLAIMS)
        return SEMANTIC_E_INVAL;
    if (view->admitted_relation_count > TYPED_VIEW_MAX_RELATIONS)
        return SEMANTIC_E_INVAL;
    if (view->source_span_count > TYPED_VIEW_MAX_SPANS)
        return SEMANTIC_E_INVAL;

    /* Reserved */
    for (uint32_t i = 0; i < sizeof(view->reserved); i++) {
        if (view->reserved[i] != 0)
            return SEMANTIC_E_RESERVATION;
    }

    return SEMANTIC_OK;
}

int elpis_typed_view_lookup_claim(const elpis_typed_evidence_view_v1 *view,
                                   const hacf_digest *claim_digest,
                                   uint32_t *index_out) {
    if (!view || !claim_digest || !index_out) return SEMANTIC_E_INVAL;

    for (uint32_t i = 0; i < view->admitted_claim_count; i++) {
        if (memcmp(view->admitted_claim_digests[i].bytes,
                   claim_digest->bytes, HACF_DIGEST_BYTES) == 0) {
            *index_out = i;
            return SEMANTIC_OK;
        }
    }
    return SEMANTIC_E_NOTFOUND;
}

uint32_t elpis_typed_view_assertion_count_for_claim(
    const elpis_typed_evidence_view_v1 *view, uint32_t claim_index) {
    if (!view || claim_index >= view->admitted_claim_count) return 0;
    /* In the full implementation, this would index into assertion records.
     * Here we return a count from the view's internal state. */
    (void)claim_index;
    return 1; /* placeholder — each claim has at least one assertion */
}

int elpis_typed_view_lookup_relation(const elpis_typed_evidence_view_v1 *view,
                                      const hacf_digest *relation_digest,
                                      uint32_t *index_out) {
    if (!view || !relation_digest || !index_out) return SEMANTIC_E_INVAL;

    for (uint32_t i = 0; i < view->admitted_relation_count; i++) {
        if (memcmp(view->admitted_relation_digests[i].bytes,
                   relation_digest->bytes, HACF_DIGEST_BYTES) == 0) {
            *index_out = i;
            return SEMANTIC_OK;
        }
    }
    return SEMANTIC_E_NOTFOUND;
}

uint32_t elpis_typed_view_claims_for_item(const elpis_typed_evidence_view_v1 *view,
                                           const hacf_digest *item_digest,
                                           uint32_t *claim_indices, uint32_t max_indices) {
    if (!view || !item_digest) return 0;
    /* Full implementation would index claim-to-item mappings */
    (void)claim_indices;
    (void)max_indices;
    return 0;
}

uint32_t elpis_typed_view_relations_for_target(const elpis_typed_evidence_view_v1 *view,
                                                const hacf_digest *target_digest,
                                                uint32_t *relation_indices,
                                                uint32_t max_indices) {
    if (!view || !target_digest) return 0;
    (void)relation_indices;
    (void)max_indices;
    return 0;
}

uint32_t elpis_typed_view_supports_for_target(const elpis_typed_evidence_view_v1 *view,
                                               const hacf_digest *target_digest,
                                               uint32_t *relation_indices,
                                               uint32_t max_indices) {
    if (!view || !target_digest) return 0;
    (void)relation_indices;
    (void)max_indices;
    return 0;
}

uint32_t elpis_typed_view_contradicts_for_target(const elpis_typed_evidence_view_v1 *view,
                                                  const hacf_digest *target_digest,
                                                  uint32_t *relation_indices,
                                                  uint32_t max_indices) {
    if (!view || !target_digest) return 0;
    (void)relation_indices;
    (void)max_indices;
    return 0;
}

uint32_t elpis_typed_view_filter_relations(const elpis_typed_evidence_view_v1 *view,
                                            const typed_view_filter *filter,
                                            const typed_view_page *page,
                                            uint32_t *relation_indices, uint32_t max_indices) {
    if (!view || !page) return 0;
    (void)filter;
    (void)relation_indices;
    (void)max_indices;
    return 0;
}

uint32_t elpis_typed_view_filter_claims(const elpis_typed_evidence_view_v1 *view,
                                         const typed_view_filter *filter,
                                         const typed_view_page *page,
                                         uint32_t *claim_indices, uint32_t max_indices) {
    if (!view || !page) return 0;
    (void)filter;
    (void)claim_indices;
    (void)max_indices;
    return 0;
}

int elpis_typed_evidence_view_cmp(const elpis_typed_evidence_view_v1 *a,
                                   const elpis_typed_evidence_view_v1 *b) {
    if (!a || !b) return 1;
    return memcmp(a->typed_evidence_view_digest.bytes,
                  b->typed_evidence_view_digest.bytes, HACF_DIGEST_BYTES);
}
