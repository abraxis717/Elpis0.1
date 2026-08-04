/* context_deficit_policy.c — Deficit policy identity and validation.
 *
 * Identity domain: "elpis.semantic.context_deficit_policy.v1"
 */
#include "elpis_semantic/context_deficit_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>

static void write_domain_tag(elpis_sha256_ctx *ctx, const char *domain) {
    size_t len = strlen(domain);
    uint32_t be_len = htonl((uint32_t)len);
    elpis_sha256_update(ctx, &be_len, 4);
    elpis_sha256_update(ctx, domain, len);
}

static void write_u32_be(elpis_sha256_ctx *ctx, uint32_t val) {
    uint32_t be = htonl(val);
    elpis_sha256_update(ctx, &be, 4);
}

static const char DOMAIN[] = "elpis.semantic.context_deficit_policy.v1";

void elpis_context_deficit_policy_init(
    elpis_semantic_context_deficit_policy_v1 *policy) {
    memset(policy, 0, sizeof(*policy));
    policy->abi_version = CONTEXT_DEFICIT_POLICY_ABI_VERSION;
}

int elpis_context_deficit_policy_identity(
    const elpis_semantic_context_deficit_policy_v1 *policy, hacf_digest *out) {
    if (!policy || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, DOMAIN);
    write_u32_be(&ctx, policy->abi_version);
    write_u32_be(&ctx, policy->mandatory_failure_behavior);
    write_u32_be(&ctx, policy->preferred_failure_behavior);
    write_u32_be(&ctx, policy->diagnostic_failure_behavior);
    write_u32_be(&ctx, policy->max_retrieval_requirements);
    write_u32_be(&ctx, policy->max_deficits);
    write_u32_be(&ctx, policy->deficit_priority_policy);
    write_u32_be(&ctx, policy->retrieval_dedup_policy);
    write_u32_be(&ctx, policy->unsupported_requirement_behavior);
    write_u32_be(&ctx, policy->policy_flags);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_context_deficit_policy_validate(
    const elpis_semantic_context_deficit_policy_v1 *policy) {
    if (!policy) return SEMANTIC_E_INVAL;
    if (policy->abi_version != CONTEXT_DEFICIT_POLICY_ABI_VERSION) return SEMANTIC_E_INVAL;

    /* Mandatory failure must be RETRIEVAL_REQUIRED */
    if (policy->mandatory_failure_behavior != MAND_BEHAVIOR_RETRIEVAL_REQUIRED) {
        return SEMANTIC_E_INVAL;
    }

    /* Preferred failure must be REPORT_ONLY or RETRIEVAL_REQUIRED */
    if (policy->preferred_failure_behavior != PREFERRED_BEHAVIOR_REPORT_ONLY &&
        policy->preferred_failure_behavior != PREFERRED_BEHAVIOR_RETRIEVAL_REQUIRED) {
        return SEMANTIC_E_INVAL;
    }

    /* Diagnostic failure must be REPORT_ONLY */
    if (policy->diagnostic_failure_behavior != DIAG_BEHAVIOR_REPORT_ONLY) {
        return SEMANTIC_E_INVAL;
    }

    /* Unsupported requirement must be FAIL_CLOSED */
    if (policy->unsupported_requirement_behavior != UNSUPPORTED_BEHAVIOR_FAIL_CLOSED) {
        return SEMANTIC_E_INVAL;
    }

    /* Max counts must be positive */
    if (policy->max_retrieval_requirements == 0) return SEMANTIC_E_INVAL;
    if (policy->max_deficits == 0) return SEMANTIC_E_INVAL;

    /* Dedup policy must be valid */
    if (policy->retrieval_dedup_policy != DEDUP_EXACT_COLLAPSE) return SEMANTIC_E_INVAL;

    /* Priority policy must be valid */
    if (policy->deficit_priority_policy != PRIORITY_LEVEL_THEN_TYPE) return SEMANTIC_E_INVAL;

    /* Reserved must be zero */
    {
        static const uint8_t zero_buf[32];
        if (memcmp(policy->reserved, zero_buf, sizeof(policy->reserved)) != 0) {
            return SEMANTIC_E_RESERVATION;
        }
    }

    return SEMANTIC_OK;
}
