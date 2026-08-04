/* evidence_span.c — Exact evidence-span anchor implementation. */

#include "elpis_semantic/evidence_span.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"




#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
static const char EVIDENCE_SPAN_DOMAIN[] = "elpis.semantic.evidence_span.v1";

void elpis_evidence_span_init(elpis_evidence_span_v1 *span) {
    memset(span, 0, sizeof(*span));
    span->abi_version = EVIDENCE_SPAN_ABI_VERSION;
}

int elpis_evidence_span_identity(const elpis_evidence_span_v1 *span, hacf_digest *out) {
    if (!span || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    elpis_sha256_update(&ctx, (const uint8_t *)EVIDENCE_SPAN_DOMAIN,
                       strlen(EVIDENCE_SPAN_DOMAIN));

    uint32_t v = __builtin_bswap32(span->abi_version);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_update(&ctx, span->retrieval_expansion_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, span->retrieval_bundle_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, span->retrieval_bundle_package_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, span->retrieval_item_attachment_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, span->evidence_node_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, span->chunk_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, span->item_text_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(span->byte_start);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(span->byte_end_exclusive);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_update(&ctx, span->span_bytes_digest.bytes, HACF_DIGEST_BYTES);
    v = __builtin_bswap32(span->span_flags);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_evidence_span_validate(const elpis_evidence_span_v1 *span,
                                 const uint8_t *item_text, uint32_t item_text_bytes) {
    if (!span) return SEMANTIC_E_INVAL;

    if (span->abi_version != EVIDENCE_SPAN_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    /* All required digests must be nonzero */
    if (digest_is_zero(&span->retrieval_expansion_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&span->retrieval_bundle_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&span->retrieval_item_attachment_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&span->evidence_node_digest))
        return SEMANTIC_E_INVAL;

    /* byte_start < byte_end_exclusive */
    if (span->byte_start >= span->byte_end_exclusive)
        return SEMANTIC_E_INVAL;

    /* End offset does not exceed item text byte count */
    if (item_text && item_text_bytes) {
        if (span->byte_end_exclusive > item_text_bytes)
            return SEMANTIC_E_INVAL;

        /* Verify span bytes digest */
        hacf_digest computed;
        elpis_sha256_ctx ctx;
        elpis_sha256_init(&ctx);
        elpis_sha256_update(&ctx, item_text + span->byte_start,
                          span->byte_end_exclusive - span->byte_start);
        elpis_sha256_final(&ctx, computed.bytes);

        if (memcmp(computed.bytes, span->span_bytes_digest.bytes, HACF_DIGEST_BYTES) != 0)
            return SEMANTIC_E_DIGEST;
    }

    /* Flags */
    if (span->span_flags & ~EVIDENCE_SPAN_FLAG_MASK)
        return SEMANTIC_E_RESERVATION;

    /* Reserved fields */
    for (uint32_t i = 0; i < sizeof(span->reserved); i++) {
        if (span->reserved[i] != 0)
            return SEMANTIC_E_RESERVATION;
    }

    return SEMANTIC_OK;
}

int elpis_evidence_span_cmp(const elpis_evidence_span_v1 *a,
                            const elpis_evidence_span_v1 *b) {
    if (!a || !b) return 1;
    return memcmp(a->span_identity.bytes, b->span_identity.bytes, HACF_DIGEST_BYTES);
}

int elpis_evidence_span_canonical_cmp(const elpis_evidence_span_v1 *a,
                                      const elpis_evidence_span_v1 *b) {
    if (!a || !b) return 1;
    int c;
    c = memcmp(a->retrieval_item_attachment_digest.bytes,
               b->retrieval_item_attachment_digest.bytes, HACF_DIGEST_BYTES);
    if (c != 0) return c;
    if (a->byte_start < b->byte_start) return -1;
    if (a->byte_start > b->byte_start) return 1;
    if (a->byte_end_exclusive < b->byte_end_exclusive) return -1;
    if (a->byte_end_exclusive > b->byte_end_exclusive) return 1;
    return memcmp(a->span_bytes_digest.bytes, b->span_bytes_digest.bytes,
                  HACF_DIGEST_BYTES);
}
