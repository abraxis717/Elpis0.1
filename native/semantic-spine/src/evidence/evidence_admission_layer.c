/* evidence_admission_layer.c — Immutable evidence-admission layer implementation. */

#include "elpis_semantic/evidence_admission.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"




#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
static const char ADMISSION_LAYER_DOMAIN[] = "elpis.semantic.evidence_admission.v1";

void elpis_evidence_admission_init(elpis_evidence_admission_v1 *admission) {
    memset(admission, 0, sizeof(*admission));
    admission->abi_version = EVIDENCE_ADMISSION_ABI_VERSION;
}

int elpis_evidence_admission_identity(const elpis_evidence_admission_v1 *admission,
                                       hacf_digest *out) {
    if (!admission || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    elpis_sha256_update(&ctx, (const uint8_t *)ADMISSION_LAYER_DOMAIN,
                       strlen(ADMISSION_LAYER_DOMAIN));

    uint32_t v = __builtin_bswap32(admission->abi_version);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_update(&ctx, admission->base_snapshot_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, admission->query_overlay_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, admission->retrieval_expansion_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, admission->retrieval_expanded_view_digest.bytes,
                       HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, admission->typing_bundle_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, admission->admission_policy_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(admission->admission_decision_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < admission->admission_decision_count; i++) {
        elpis_sha256_update(&ctx, admission->admission_decision_digests[i].bytes,
                          HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(admission->admission_receipt_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < admission->admission_receipt_count; i++) {
        elpis_sha256_update(&ctx, admission->admission_receipt_digests[i].bytes,
                          HACF_DIGEST_BYTES);
    }

    elpis_sha256_update(&ctx, admission->admission_segment_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(admission->admitted_claim_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(admission->admitted_relation_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(admission->rejected_claim_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(admission->rejected_relation_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_update(&ctx, admission->HACF_package_digest.bytes, HACF_DIGEST_BYTES);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_evidence_admission_validate(const elpis_evidence_admission_v1 *admission) {
    if (!admission) return SEMANTIC_E_INVAL;

    if (admission->abi_version != EVIDENCE_ADMISSION_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    /* Required digests must be nonzero */
    if (digest_is_zero(&admission->base_snapshot_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&admission->query_overlay_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&admission->retrieval_expansion_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&admission->typing_bundle_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&admission->admission_policy_digest))
        return SEMANTIC_E_INVAL;

    /* Counts bounded */
    if (admission->admission_decision_count > EVIDENCE_ADMISSION_MAX_DECISIONS)
        return SEMANTIC_E_INVAL;
    if (admission->admission_receipt_count > EVIDENCE_ADMISSION_MAX_RECEIPTS)
        return SEMANTIC_E_INVAL;

    /* Decision and receipt counts must match */
    if (admission->admission_decision_count != admission->admission_receipt_count)
        return SEMANTIC_E_INVAL;

    /* Counts must be consistent with admitted/rejected tallies */
    if (admission->admitted_claim_count + admission->admitted_relation_count +
        admission->rejected_claim_count + admission->rejected_relation_count !=
        admission->admission_decision_count)
        return SEMANTIC_E_INVAL;

    /* Reserved */
    for (uint32_t i = 0; i < sizeof(admission->reserved); i++) {
        if (admission->reserved[i] != 0)
            return SEMANTIC_E_RESERVATION;
    }

    return SEMANTIC_OK;
}

int elpis_evidence_admission_cmp(const elpis_evidence_admission_v1 *a,
                                  const elpis_evidence_admission_v1 *b) {
    if (!a || !b) return 1;
    return memcmp(a->admission_layer_digest.bytes, b->admission_layer_digest.bytes,
                  HACF_DIGEST_BYTES);
}
