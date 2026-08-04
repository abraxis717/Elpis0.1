/* evidence_typing_bundle.c — Evidence-typing proposal bundle implementation. */

#include "elpis_semantic/evidence_typing_bundle.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"




#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
static const char TYPING_BUNDLE_DOMAIN[] = "elpis.semantic.evidence_typing_bundle.v1";

void elpis_typing_bundle_init(elpis_evidence_typing_bundle_v1 *bundle) {
    memset(bundle, 0, sizeof(*bundle));
    bundle->abi_version = EVIDENCE_TYPING_BUNDLE_ABI_VERSION;
}

int elpis_typing_bundle_identity(const elpis_evidence_typing_bundle_v1 *bundle,
                                  hacf_digest *out) {
    if (!bundle || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    elpis_sha256_update(&ctx, (const uint8_t *)TYPING_BUNDLE_DOMAIN,
                       strlen(TYPING_BUNDLE_DOMAIN));

    uint32_t v = __builtin_bswap32(bundle->abi_version);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_update(&ctx, bundle->base_snapshot_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, bundle->query_overlay_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, bundle->retrieval_expansion_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, bundle->retrieval_expanded_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, bundle->typer_profile_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(bundle->evidence_span_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < bundle->evidence_span_count; i++) {
        elpis_sha256_update(&ctx, bundle->evidence_span_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(bundle->claim_candidate_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < bundle->claim_candidate_count; i++) {
        elpis_sha256_update(&ctx, bundle->claim_candidate_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(bundle->relation_candidate_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < bundle->relation_candidate_count; i++) {
        elpis_sha256_update(&ctx, bundle->relation_candidate_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    elpis_sha256_update(&ctx, bundle->typing_bundle_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, bundle->HACF_package_digest.bytes, HACF_DIGEST_BYTES);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_typing_bundle_validate(const elpis_evidence_typing_bundle_v1 *bundle) {
    if (!bundle) return SEMANTIC_E_INVAL;

    if (bundle->abi_version != EVIDENCE_TYPING_BUNDLE_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    /* All P3 references must be nonzero */
    if (digest_is_zero(&bundle->base_snapshot_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&bundle->query_overlay_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&bundle->retrieval_expansion_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&bundle->retrieval_expanded_view_digest))
        return SEMANTIC_E_INVAL;

    /* Typer profile must exist */
    if (digest_is_zero(&bundle->typer_profile_digest))
        return SEMANTIC_E_INVAL;

    /* Counts bounded */
    if (bundle->evidence_span_count > EVIDENCE_BUNDLE_MAX_SPANS)
        return SEMANTIC_E_INVAL;
    if (bundle->claim_candidate_count > EVIDENCE_BUNDLE_MAX_CLAIMS)
        return SEMANTIC_E_INVAL;
    if (bundle->relation_candidate_count > EVIDENCE_BUNDLE_MAX_RELATIONS)
        return SEMANTIC_E_INVAL;

    /* Each span digest must be nonzero */
    for (uint32_t i = 0; i < bundle->evidence_span_count; i++) {
        if (digest_is_zero(&bundle->evidence_span_digests[i]))
            return SEMANTIC_E_INVAL;
    }

    /* Each claim candidate digest must be nonzero */
    for (uint32_t i = 0; i < bundle->claim_candidate_count; i++) {
        if (digest_is_zero(&bundle->claim_candidate_digests[i]))
            return SEMANTIC_E_INVAL;
    }

    /* Each relation candidate digest must be nonzero */
    for (uint32_t i = 0; i < bundle->relation_candidate_count; i++) {
        if (digest_is_zero(&bundle->relation_candidate_digests[i]))
            return SEMANTIC_E_INVAL;
    }

    /* Reserved */
    for (uint32_t i = 0; i < sizeof(bundle->reserved); i++) {
        if (bundle->reserved[i] != 0)
            return SEMANTIC_E_RESERVATION;
    }

    return SEMANTIC_OK;
}

int elpis_typing_bundle_cmp(const elpis_evidence_typing_bundle_v1 *a,
                             const elpis_evidence_typing_bundle_v1 *b) {
    if (!a || !b) return 1;
    return memcmp(a->typing_bundle_digest.bytes, b->typing_bundle_digest.bytes,
                  HACF_DIGEST_BYTES);
}
