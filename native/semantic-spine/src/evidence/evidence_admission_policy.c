/* evidence_admission_policy.c — Evidence-admission policy implementation. */

#include "elpis_semantic/evidence_admission_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"




#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
static const char ADMISSION_POLICY_DOMAIN[] = "elpis.semantic.evidence_admission_policy.v1";

/* Default authority ceilings */
#define AUTH_CEILING_ADMISSORY    1u
#define AUTH_CEILING_PROVISIONAL  2u

void elpis_admission_policy_init(elpis_evidence_admission_policy_v1 *policy) {
    memset(policy, 0, sizeof(*policy));
    policy->abi_version = EVIDENCE_ADMISSION_POLICY_ABI_VERSION;
}

void elpis_admission_policy_init_default(elpis_evidence_admission_policy_v1 *policy) {
    elpis_admission_policy_init(policy);

    /* Default P4 v1 policy */
    policy->minimum_claim_confidence_key = 0;
    policy->minimum_relation_confidence_key = 0;
    policy->maximum_claim_authority = AUTH_CEILING_ADMISSORY;
    policy->maximum_relation_authority = AUTH_CEILING_PROVISIONAL;
    policy->minimum_source_authority = 0;

    policy->require_exact_span_validation = 1;
    policy->require_target_resolution = 1;
    policy->require_subject_resolution = 0;
    policy->require_scope_resolution_when_present = 0;
    policy->require_qualifier_resolution_when_present = 0;

    policy->allow_primary_items = 1;
    policy->allow_context_items = 1;
    policy->context_item_parent_required = 1;

    policy->minimum_distinct_source_spans = 1;
    policy->minimum_distinct_retrieval_items = 1;
    policy->minimum_distinct_documents = 1;
    policy->minimum_distinct_bundles = 1;

    policy->duplicate_handling_policy = DUPLICATE_COLLAPSE;
    policy->conflict_handling_policy = CONFLICT_RETAIN_BOTH;
    policy->unsupported_type_behavior = UNSUPPORTED_REJECT;

    policy->admission_limit = 0; /* 0 = unlimited */
    policy->policy_flags = ADMISSION_POLICY_FLAG_STRICT;
}

int elpis_admission_policy_identity(const elpis_evidence_admission_policy_v1 *policy,
                                     hacf_digest *out) {
    if (!policy || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    elpis_sha256_update(&ctx, (const uint8_t *)ADMISSION_POLICY_DOMAIN,
                       strlen(ADMISSION_POLICY_DOMAIN));

    uint32_t v = __builtin_bswap32(policy->abi_version);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    v = __builtin_bswap32(policy->allowed_typer_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < policy->allowed_typer_count; i++) {
        elpis_sha256_update(&ctx, policy->allowed_typer_profile_digests[i].bytes,
                          HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(policy->allowed_claim_type_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < policy->allowed_claim_type_count; i++) {
        v = __builtin_bswap32(policy->allowed_claim_type_ids[i]);
        elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    }

    v = __builtin_bswap32(policy->allowed_relation_type_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < policy->allowed_relation_type_count; i++) {
        v = __builtin_bswap32(policy->allowed_relation_type_ids[i]);
        elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    }

    v = __builtin_bswap32(policy->minimum_claim_confidence_key);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->minimum_relation_confidence_key);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->maximum_claim_authority);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->maximum_relation_authority);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->minimum_source_authority);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    v = __builtin_bswap32(policy->require_exact_span_validation);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->require_target_resolution);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->require_subject_resolution);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->require_scope_resolution_when_present);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->require_qualifier_resolution_when_present);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    v = __builtin_bswap32(policy->allow_primary_items);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->allow_context_items);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->context_item_parent_required);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    v = __builtin_bswap32(policy->minimum_distinct_source_spans);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->minimum_distinct_retrieval_items);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->minimum_distinct_documents);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->minimum_distinct_bundles);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    v = __builtin_bswap32(policy->duplicate_handling_policy);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->conflict_handling_policy);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->unsupported_type_behavior);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    v = __builtin_bswap32(policy->admission_limit);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(policy->policy_flags);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_admission_policy_validate(const elpis_evidence_admission_policy_v1 *policy) {
    if (!policy) return SEMANTIC_E_INVAL;

    if (policy->abi_version != EVIDENCE_ADMISSION_POLICY_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    /* Counts in range */
    if (policy->allowed_typer_count > EVIDENCE_POLICY_MAX_PROVIDER_DIGESTS)
        return SEMANTIC_E_INVAL;
    if (policy->allowed_claim_type_count > EVIDENCE_POLICY_MAX_CLAIM_TYPE_IDS)
        return SEMANTIC_E_INVAL;
    if (policy->allowed_relation_type_count > EVIDENCE_POLICY_MAX_RELATION_TYPE_IDS)
        return SEMANTIC_E_INVAL;

    /* Flags */
    if (policy->policy_flags & ~ADMISSION_POLICY_FLAG_MASK)
        return SEMANTIC_E_RESERVATION;

    /* Reserved */
    for (uint32_t i = 0; i < sizeof(policy->reserved); i++) {
        if (policy->reserved[i] != 0)
            return SEMANTIC_E_RESERVATION;
    }

    return SEMANTIC_OK;
}

int elpis_policy_allows_typer(const elpis_evidence_admission_policy_v1 *policy,
                               const hacf_digest *typer_digest) {
    if (!policy || !typer_digest) return 0;

    /* If no allowlist specified, all allowed */
    if (policy->allowed_typer_count == 0) return 1;

    for (uint32_t i = 0; i < policy->allowed_typer_count; i++) {
        if (memcmp(policy->allowed_typer_profile_digests[i].bytes,
                   typer_digest->bytes, HACF_DIGEST_BYTES) == 0)
            return 1;
    }
    return 0;
}

int elpis_policy_allows_claim_type(const elpis_evidence_admission_policy_v1 *policy,
                                    uint32_t claim_type) {
    if (!policy) return 0;

    if (policy->allowed_claim_type_count == 0) return 1;

    for (uint32_t i = 0; i < policy->allowed_claim_type_count; i++) {
        if (policy->allowed_claim_type_ids[i] == claim_type)
            return 1;
    }
    return 0;
}

int elpis_policy_allows_relation_type(const elpis_evidence_admission_policy_v1 *policy,
                                       uint32_t relation_type) {
    if (!policy) return 0;

    if (policy->allowed_relation_type_count == 0) return 1;

    for (uint32_t i = 0; i < policy->allowed_relation_type_count; i++) {
        if (policy->allowed_relation_type_ids[i] == relation_type)
            return 1;
    }
    return 0;
}
