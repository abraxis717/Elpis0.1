/* evidence_typer_profile.c — Evidence-typer provider profile implementation. */

#include "elpis_semantic/evidence_typer_profile.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"




#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
/* Domain: "elpis.semantic.evidence_typer_profile.v1" */
static const char TYPER_PROFILE_DOMAIN[] = "elpis.semantic.evidence_typer_profile.v1";

void elpis_typer_profile_init(elpis_evidence_typer_profile_v1 *profile) {
    memset(profile, 0, sizeof(*profile));
    profile->abi_version = EVIDENCE_TYPER_PROFILE_ABI_VERSION;
}

int elpis_typer_profile_identity(const elpis_evidence_typer_profile_v1 *profile, hacf_digest *out) {
    if (!profile || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    /* Domain tag */
    elpis_sha256_update(&ctx, (const uint8_t *)TYPER_PROFILE_DOMAIN,
                       strlen(TYPER_PROFILE_DOMAIN));

    /* abi_version */
    uint32_t v = __builtin_bswap32(profile->abi_version);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    /* provider_kind */
    v = __builtin_bswap32(profile->provider_kind);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    /* Digests */
    elpis_sha256_update(&ctx, profile->provider_identity_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, profile->provider_code_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, profile->provider_configuration_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, profile->input_schema_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, profile->output_schema_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, profile->normalization_policy_digest.bytes, HACF_DIGEST_BYTES);

    /* confidence_scale */
    v = __builtin_bswap32(profile->confidence_scale);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    /* maximum_claims_per_item */
    v = __builtin_bswap32(profile->maximum_claims_per_item);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    /* maximum_relations_per_item */
    v = __builtin_bswap32(profile->maximum_relations_per_item);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    /* determinism_declaration */
    elpis_sha256_update(&ctx, profile->determinism_declaration.bytes, HACF_DIGEST_BYTES);

    /* provider_flags */
    v = __builtin_bswap32(profile->provider_flags);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_typer_profile_validate(const elpis_evidence_typer_profile_v1 *profile) {
    if (!profile) return SEMANTIC_E_INVAL;

    /* ABI version */
    if (profile->abi_version != EVIDENCE_TYPER_PROFILE_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    /* Provider kind must be valid */
    switch (profile->provider_kind) {
        case TYPER_KIND_DETERMINISTIC_RULE:
        case TYPER_KIND_EXTERNAL_MODEL:
        case TYPER_KIND_MANUAL_CURATED:
        case TYPER_KIND_IMPORTED_SEALED:
            break;
        default:
            return SEMANTIC_E_INVAL;
    }

    /* Confidence scale must be positive */
    if (profile->confidence_scale == 0)
        return SEMANTIC_E_INVAL;

    /* Maximum counts must be nonzero and bounded */
    if (profile->maximum_claims_per_item == 0)
        return SEMANTIC_E_INVAL;
    if (profile->maximum_claims_per_item > 10000)
        return SEMANTIC_E_INVAL;
    if (profile->maximum_relations_per_item == 0)
        return SEMANTIC_E_INVAL;
    if (profile->maximum_relations_per_item > 10000)
        return SEMANTIC_E_INVAL;

    /* Flags must not have unknown bits */
    if (profile->provider_flags & ~TYPER_FLAG_MASK)
        return SEMANTIC_E_RESERVATION;

    /* Reserved fields must be zero */
    for (uint32_t i = 0; i < sizeof(profile->reserved); i++) {
        if (profile->reserved[i] != 0)
            return SEMANTIC_E_RESERVATION;
    }

    return SEMANTIC_OK;
}

int elpis_typer_profile_cmp(const elpis_evidence_typer_profile_v1 *a,
                            const elpis_evidence_typer_profile_v1 *b) {
    if (!a || !b) return 1;
    return memcmp(a->profile_identity.bytes, b->profile_identity.bytes,
                  HACF_DIGEST_BYTES);
}
