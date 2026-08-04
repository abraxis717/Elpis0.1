/* evidence_claim_candidate.c — Claim candidate implementation. */

#include "elpis_semantic/evidence_claim_candidate.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"




#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
static const char CLAIM_CANDIDATE_DOMAIN[] = "elpis.semantic.claim_candidate.v1";

void elpis_claim_candidate_init(elpis_evidence_claim_candidate_v1 *candidate) {
    memset(candidate, 0, sizeof(*candidate));
    candidate->abi_version = EVIDENCE_CLAIM_CANDIDATE_ABI_VERSION;
}

int elpis_claim_candidate_identity(const elpis_evidence_claim_candidate_v1 *candidate,
                                    hacf_digest *out) {
    if (!candidate || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    elpis_sha256_update(&ctx, (const uint8_t *)CLAIM_CANDIDATE_DOMAIN,
                       strlen(CLAIM_CANDIDATE_DOMAIN));

    uint32_t v = __builtin_bswap32(candidate->abi_version);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_update(&ctx, candidate->typer_profile_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(candidate->claim_type);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_update(&ctx, candidate->claim_payload_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, candidate->claim_payload_object_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(candidate->source_span_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < candidate->source_span_count; i++) {
        elpis_sha256_update(&ctx, candidate->source_span_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(candidate->subject_object_kind);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    elpis_sha256_update(&ctx, candidate->subject_object_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(candidate->claim_polarity);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(candidate->claim_modality);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_update(&ctx, candidate->claim_scope_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, candidate->claim_qualifier_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(candidate->confidence_key);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(candidate->candidate_flags);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_claim_candidate_validate(const elpis_evidence_claim_candidate_v1 *candidate) {
    if (!candidate) return SEMANTIC_E_INVAL;

    if (candidate->abi_version != EVIDENCE_CLAIM_CANDIDATE_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    /* Typer profile must be nonzero */
    if (digest_is_zero(&candidate->typer_profile_digest))
        return SEMANTIC_E_INVAL;

    /* Claim type must be nonzero */
    if (candidate->claim_type == 0)
        return SEMANTIC_E_INVAL;

    /* Payload digests must be nonzero */
    if (digest_is_zero(&candidate->claim_payload_digest))
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&candidate->claim_payload_object_digest))
        return SEMANTIC_E_INVAL;

    /* Source span count: nonzero and bounded */
    if (candidate->source_span_count == 0)
        return SEMANTIC_E_INVAL;
    if (candidate->source_span_count > EVIDENCE_MAX_SOURCE_SPANS)
        return SEMANTIC_E_INVAL;

    /* Each span digest must be nonzero */
    for (uint32_t i = 0; i < candidate->source_span_count; i++) {
        if (digest_is_zero(&candidate->source_span_digests[i]))
            return SEMANTIC_E_INVAL;
    }

    /* Subject: if kind is nonzero, digest must be nonzero */
    if (candidate->subject_object_kind != SUBJECT_KIND_NONE) {
        if (digest_is_zero(&candidate->subject_object_digest))
            return SEMANTIC_E_INVAL;
    }

    /* Polarity validation */
    switch (candidate->claim_polarity) {
        case 0: /* UNSPECIFIED default */
        case CLAIM_POLARITY_AFFIRMATIVE:
        case CLAIM_POLARITY_NEGATIVE:
        case CLAIM_POLARITY_NEUTRAL:
        case CLAIM_POLARITY_UNSPECIFIED:
            break;
        default:
            return SEMANTIC_E_INVAL;
    }

    /* Modality validation */
    switch (candidate->claim_modality) {
        case 0: /* UNSPECIFIED default */
        case CLAIM_MODALITY_ASSERTED:
        case CLAIM_MODALITY_POSSIBLE:
        case CLAIM_MODALITY_PROBABLE:
        case CLAIM_MODALITY_CONDITIONAL:
        case CLAIM_MODALITY_COUNTERFACTUAL:
        case CLAIM_MODALITY_QUOTED_ONLY:
        case CLAIM_MODALITY_UNSPECIFIED:
            break;
        default:
            return SEMANTIC_E_INVAL;
    }

    /* Flags */
    if (candidate->candidate_flags & ~CLAIM_CANDIDATE_FLAG_MASK)
        return SEMANTIC_E_RESERVATION;

    /* Reserved */
    for (uint32_t i = 0; i < sizeof(candidate->reserved); i++) {
        if (candidate->reserved[i] != 0)
            return SEMANTIC_E_RESERVATION;
    }

    return SEMANTIC_OK;
}

int elpis_claim_candidate_cmp(const elpis_evidence_claim_candidate_v1 *a,
                               const elpis_evidence_claim_candidate_v1 *b) {
    if (!a || !b) return 1;
    return memcmp(a->candidate_identity.bytes, b->candidate_identity.bytes,
                  HACF_DIGEST_BYTES);
}

int elpis_claim_candidate_canonical_cmp(const elpis_evidence_claim_candidate_v1 *a,
                                         const elpis_evidence_claim_candidate_v1 *b) {
    if (!a || !b) return 1;
    int c;
    if (a->claim_type < b->claim_type) return -1;
    if (a->claim_type > b->claim_type) return 1;
    c = memcmp(a->claim_payload_digest.bytes, b->claim_payload_digest.bytes,
               HACF_DIGEST_BYTES);
    if (c != 0) return c;
    return memcmp(a->candidate_identity.bytes, b->candidate_identity.bytes,
                  HACF_DIGEST_BYTES);
}
