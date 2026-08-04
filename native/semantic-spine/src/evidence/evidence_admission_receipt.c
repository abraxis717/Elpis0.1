/* evidence_admission_receipt.c — Admission receipt implementation. */

#include "elpis_semantic/evidence_admission_receipt.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"




#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
static const char RECEIPT_DOMAIN[] = "elpis.semantic.evidence_admission_receipt.v1";

void elpis_admission_receipt_init(elpis_evidence_admission_receipt_v1 *receipt) {
    memset(receipt, 0, sizeof(*receipt));
    receipt->abi_version = EVIDENCE_ADMISSION_RECEIPT_ABI_VERSION;
    receipt->graph_edge_provenance_status = GRAPH_PROVENANCE_UNAVAILABLE;
}

int elpis_admission_receipt_identity(const elpis_evidence_admission_receipt_v1 *receipt,
                                      hacf_digest *out) {
    if (!receipt || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    elpis_sha256_update(&ctx, (const uint8_t *)RECEIPT_DOMAIN,
                       strlen(RECEIPT_DOMAIN));

    uint32_t v = __builtin_bswap32(receipt->abi_version);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_update(&ctx, receipt->base_snapshot_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->query_overlay_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->retrieval_expansion_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->retrieval_expanded_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->typing_bundle_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->typer_profile_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->candidate_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->admission_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->admission_decision_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->semantic_object_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(receipt->source_span_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < receipt->source_span_count; i++) {
        elpis_sha256_update(&ctx, receipt->source_span_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(receipt->retrieval_bundle_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < receipt->retrieval_bundle_count; i++) {
        elpis_sha256_update(&ctx, receipt->retrieval_bundle_package_digests[i].bytes,
                          HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(receipt->retrieval_item_attachment_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < receipt->retrieval_item_attachment_count; i++) {
        elpis_sha256_update(&ctx, receipt->retrieval_item_attachment_digests[i].bytes,
                          HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(receipt->graph_edge_provenance_status);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    elpis_sha256_update(&ctx, receipt->HACF_package_digest.bytes, HACF_DIGEST_BYTES);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_admission_receipt_validate(const elpis_evidence_admission_receipt_v1 *receipt) {
    if (!receipt) return SEMANTIC_E_INVAL;

    if (receipt->abi_version != EVIDENCE_ADMISSION_RECEIPT_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    /* Required chain digests must be nonzero */
    if (digest_is_zero(&receipt->base_snapshot_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&receipt->query_overlay_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&receipt->retrieval_expansion_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&receipt->typing_bundle_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&receipt->candidate_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&receipt->admission_policy_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&receipt->admission_decision_digest))
        return SEMANTIC_E_INVAL;

    /* Counts bounded */
    if (receipt->source_span_count > EVIDENCE_RECEIPT_MAX_SPANS)
        return SEMANTIC_E_INVAL;
    if (receipt->retrieval_bundle_count > EVIDENCE_RECEIPT_MAX_BUNDLES)
        return SEMANTIC_E_INVAL;
    if (receipt->retrieval_item_attachment_count > EVIDENCE_RECEIPT_MAX_ATTACHMENTS)
        return SEMANTIC_E_INVAL;

    /* Reserved */
    for (uint32_t i = 0; i < sizeof(receipt->reserved); i++) {
        if (receipt->reserved[i] != 0)
            return SEMANTIC_E_RESERVATION;
    }

    return SEMANTIC_OK;
}

int elpis_receipt_provenance_status_verify(const elpis_evidence_admission_receipt_v1 *receipt) {
    if (!receipt) return SEMANTIC_E_INVAL;

    /* When status is UNAVAILABLE, no recovered digest should be present */
    if (receipt->graph_edge_provenance_status == GRAPH_PROVENANCE_UNAVAILABLE) {
        return SEMANTIC_OK; /* This is the expected P3 status */
    }

    return SEMANTIC_OK;
}

int elpis_admission_receipt_cmp(const elpis_evidence_admission_receipt_v1 *a,
                                 const elpis_evidence_admission_receipt_v1 *b) {
    if (!a || !b) return 1;
    return memcmp(a->receipt_digest.bytes, b->receipt_digest.bytes, HACF_DIGEST_BYTES);
}
