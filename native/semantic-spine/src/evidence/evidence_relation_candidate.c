/* evidence_relation_candidate.c — Relation candidate implementation. */

#include "elpis_semantic/evidence_relation_candidate.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"




#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
static const char RELATION_CANDIDATE_DOMAIN[] = "elpis.semantic.relation_candidate.v1";

void elpis_relation_candidate_init(elpis_evidence_relation_candidate_v1 *candidate) {
    memset(candidate, 0, sizeof(*candidate));
    candidate->abi_version = EVIDENCE_RELATION_CANDIDATE_ABI_VERSION;
}

int elpis_relation_candidate_identity(const elpis_evidence_relation_candidate_v1 *candidate,
                                       hacf_digest *out) {
    if (!candidate || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    elpis_sha256_update(&ctx, (const uint8_t *)RELATION_CANDIDATE_DOMAIN,
                       strlen(RELATION_CANDIDATE_DOMAIN));

    uint32_t v = __builtin_bswap32(candidate->abi_version);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_update(&ctx, candidate->typer_profile_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(candidate->relation_type);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_update(&ctx, candidate->evidence_claim_candidate_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(candidate->evidence_object_kind);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    elpis_sha256_update(&ctx, candidate->evidence_object_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(candidate->target_object_kind);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    elpis_sha256_update(&ctx, candidate->target_object_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(candidate->evidence_role);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(candidate->target_role);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    v = __builtin_bswap32(candidate->additional_participant_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < candidate->additional_participant_count; i++) {
        elpis_sha256_update(&ctx, candidate->additional_participants[i].object_digest.bytes,
                          HACF_DIGEST_BYTES);
        v = __builtin_bswap32(candidate->additional_participants[i].role);
        elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
        v = __builtin_bswap32(candidate->additional_participants[i].ordinal);
        elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    }

    v = __builtin_bswap32(candidate->relation_polarity);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    elpis_sha256_update(&ctx, candidate->relation_scope_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, candidate->relation_qualifier_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(candidate->source_span_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < candidate->source_span_count; i++) {
        elpis_sha256_update(&ctx, candidate->source_span_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(candidate->confidence_key);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(candidate->candidate_flags);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_relation_candidate_validate(const elpis_evidence_relation_candidate_v1 *candidate) {
    if (!candidate) return SEMANTIC_E_INVAL;

    if (candidate->abi_version != EVIDENCE_RELATION_CANDIDATE_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    /* Typer profile must be nonzero */
    if (digest_is_zero(&candidate->typer_profile_digest))
        return SEMANTIC_E_INVAL;

    /* Relation type must be allowed */
    if (!elpis_relation_type_is_allowed(candidate->relation_type))
        return SEMANTIC_E_INVAL;

    /* Evidence object must exist */
    if (candidate->evidence_object_kind == OBJECT_KIND_NONE)
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&candidate->evidence_object_digest))
        return SEMANTIC_E_INVAL;

    /* Target object must exist */
    if (candidate->target_object_kind == OBJECT_KIND_NONE)
        return SEMANTIC_E_INVAL;
    if (digest_is_zero(&candidate->target_object_digest))
        return SEMANTIC_E_INVAL;

    /* Roles must be valid */
    if (candidate->evidence_role == 0 || candidate->target_role == 0)
        return SEMANTIC_E_INVAL;

    /* Additional participant count bounded */
    if (candidate->additional_participant_count > EVIDENCE_MAX_RELATION_PARTICIPANTS)
        return SEMANTIC_E_INVAL;

    /* No duplicate ordinals in additional participants */
    for (uint32_t i = 0; i < candidate->additional_participant_count; i++) {
        for (uint32_t j = i + 1; j < candidate->additional_participant_count; j++) {
            if (candidate->additional_participants[i].ordinal ==
                candidate->additional_participants[j].ordinal)
                return SEMANTIC_E_DUPLICATE;
        }
    }

    /* Source span count bounded */
    if (candidate->source_span_count > EVIDENCE_MAX_RELATION_SOURCE_SPANS)
        return SEMANTIC_E_INVAL;

    /* Each source span digest must be nonzero */
    for (uint32_t i = 0; i < candidate->source_span_count; i++) {
        if (digest_is_zero(&candidate->source_span_digests[i]))
            return SEMANTIC_E_INVAL;
    }

    /* Flags */
    if (candidate->candidate_flags & ~RELATION_CANDIDATE_FLAG_MASK)
        return SEMANTIC_E_RESERVATION;

    /* Reserved */
    for (uint32_t i = 0; i < sizeof(candidate->reserved); i++) {
        if (candidate->reserved[i] != 0)
            return SEMANTIC_E_RESERVATION;
    }

    return SEMANTIC_OK;
}

int elpis_relation_type_is_allowed(evidence_relation_type type) {
    switch (type) {
        case RELATION_TYPE_MENTIONS:
        case RELATION_TYPE_DEFINES:
        case RELATION_TYPE_SUPPORTS:
        case RELATION_TYPE_CONTRADICTS:
        case RELATION_TYPE_QUALIFIES:
        case RELATION_TYPE_LIMITS_SCOPE_OF:
        case RELATION_TYPE_PROVIDES_CONTEXT_FOR:
            return 1;
        default:
            return 0;
    }
}

uint32_t elpis_relation_allowed_roles(evidence_relation_type type,
                                       uint32_t *roles, uint32_t max_roles) {
    uint32_t count = 0;
    /* All relation types allow EVIDENCE and TARGET roles */
    if (max_roles > count) roles[count++] = RELATION_ROLE_EVIDENCE;
    if (max_roles > count) roles[count++] = RELATION_ROLE_TARGET;

    /* SUPPORTS, CONTRADICTS, QUALIFIES, LIMITS_SCOPE_OF allow QUALIFIER and SCOPE */
    switch (type) {
        case RELATION_TYPE_SUPPORTS:
        case RELATION_TYPE_CONTRADICTS:
        case RELATION_TYPE_QUALIFIES:
        case RELATION_TYPE_LIMITS_SCOPE_OF:
            if (max_roles > count) roles[count++] = RELATION_ROLE_QUALIFIER;
            if (max_roles > count) roles[count++] = RELATION_ROLE_SCOPE;
            break;
        default:
            break;
    }

    return count;
}

int elpis_relation_candidate_cmp(const elpis_evidence_relation_candidate_v1 *a,
                                  const elpis_evidence_relation_candidate_v1 *b) {
    if (!a || !b) return 1;
    return memcmp(a->candidate_identity.bytes, b->candidate_identity.bytes,
                  HACF_DIGEST_BYTES);
}

int elpis_relation_candidate_canonical_cmp(const elpis_evidence_relation_candidate_v1 *a,
                                            const elpis_evidence_relation_candidate_v1 *b) {
    if (!a || !b) return 1;
    int c;
    if (a->relation_type < b->relation_type) return -1;
    if (a->relation_type > b->relation_type) return 1;
    c = memcmp(a->target_object_digest.bytes, b->target_object_digest.bytes,
               HACF_DIGEST_BYTES);
    if (c != 0) return c;
    c = memcmp(a->evidence_object_digest.bytes, b->evidence_object_digest.bytes,
               HACF_DIGEST_BYTES);
    if (c != 0) return c;
    return memcmp(a->candidate_identity.bytes, b->candidate_identity.bytes,
                  HACF_DIGEST_BYTES);
}
