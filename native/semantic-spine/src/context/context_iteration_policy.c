/* context_iteration_policy.c — P5 context-iteration policy. */
#include "elpis_semantic/context_iteration_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdbool.h>
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

static const char *POLICY_DOMAIN = "elpis.semantic.context_iteration_policy.v1";

void elpis_context_iteration_policy_init(elpis_semantic_context_iteration_policy_v1 *policy) {
    memset(policy, 0, sizeof(*policy));
    policy->abi_version = CONTEXT_ITERATION_POLICY_ABI_VERSION;
}

int elpis_context_iteration_policy_default(elpis_semantic_context_iteration_policy_v1 *policy) {
    if (!policy) return SEMANTIC_E_INVAL;
    elpis_context_iteration_policy_init(policy);
    policy->maximum_retrieval_rounds = 3;
    policy->maximum_stagnant_rounds = 1;
    policy->identical_requirement_bundle_behavior = IDENTICAL_STOP_NO_PROGRESS;
    policy->identical_typed_view_behavior = IDENTICAL_STOP_NO_PROGRESS;
    policy->identical_deficit_set_behavior = IDENTICAL_STOP_NO_PROGRESS;
    policy->no_new_semantic_object_behavior = IDENTICAL_STOP_NO_PROGRESS;
    policy->no_new_contributing_assertion_behavior = IDENTICAL_STOP_NO_PROGRESS;
    policy->blocked_evaluation_behavior = IDENTICAL_STOP_NO_PROGRESS;
    policy->invalid_requirement_set_behavior = IDENTICAL_STOP_NO_PROGRESS;
    policy->round_limit_behavior = IDENTICAL_STOP_NO_PROGRESS;
    policy->progress_measurement_policy = PROGRESS_MEASURE_SEMANTIC;
    policy->continuation_policy_digest = (hacf_digest){0};
    policy->policy_flags = CONTEXT_ITERATION_FLAG_NONE;
    elpis_context_iteration_policy_identity(policy, &policy->policy_identity);
    return SEMANTIC_OK;
}

int elpis_context_iteration_policy_identity(
    const elpis_semantic_context_iteration_policy_v1 *policy, hacf_digest *out) {
    if (!policy || !out || policy->abi_version != CONTEXT_ITERATION_POLICY_ABI_VERSION)
        return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, POLICY_DOMAIN);
    write_u32_be(&ctx, policy->abi_version);
    write_u32_be(&ctx, policy->maximum_retrieval_rounds);
    write_u32_be(&ctx, policy->maximum_stagnant_rounds);
    write_u32_be(&ctx, policy->identical_requirement_bundle_behavior);
    write_u32_be(&ctx, policy->identical_typed_view_behavior);
    write_u32_be(&ctx, policy->identical_deficit_set_behavior);
    write_u32_be(&ctx, policy->no_new_semantic_object_behavior);
    write_u32_be(&ctx, policy->no_new_contributing_assertion_behavior);
    write_u32_be(&ctx, policy->blocked_evaluation_behavior);
    write_u32_be(&ctx, policy->invalid_requirement_set_behavior);
    write_u32_be(&ctx, policy->round_limit_behavior);
    write_u32_be(&ctx, policy->progress_measurement_policy);
    elpis_sha256_update(&ctx, policy->continuation_policy_digest.bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, policy->policy_flags);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_context_iteration_policy_validate(
    const elpis_semantic_context_iteration_policy_v1 *policy) {
    if (!policy) return SEMANTIC_E_INVAL;
    if (policy->abi_version != CONTEXT_ITERATION_POLICY_ABI_VERSION) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(policy->reserved); i++) {
        if (policy->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }
    if (policy->maximum_retrieval_rounds == 0) return SEMANTIC_E_INVAL;
    if (policy->maximum_stagnant_rounds == 0) return SEMANTIC_E_INVAL;
    if (policy->identical_requirement_bundle_behavior > 1) return SEMANTIC_E_INVAL;
    if (policy->identical_typed_view_behavior > 1) return SEMANTIC_E_INVAL;
    if (policy->identical_deficit_set_behavior > 1) return SEMANTIC_E_INVAL;
    if (policy->no_new_semantic_object_behavior > 1) return SEMANTIC_E_INVAL;
    if (policy->no_new_contributing_assertion_behavior > 1) return SEMANTIC_E_INVAL;
    if (policy->blocked_evaluation_behavior > 1) return SEMANTIC_E_INVAL;
    if (policy->invalid_requirement_set_behavior > 1) return SEMANTIC_E_INVAL;
    if (policy->round_limit_behavior > 1) return SEMANTIC_E_INVAL;
    if ((policy->policy_flags & ~CONTEXT_ITERATION_FLAG_MASK) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

extern int p5_simple_write(const char *path, const uint8_t *data, size_t sz);

int elpis_write_iteration_policy(const char *path,
    const elpis_semantic_context_iteration_policy_v1 *policy) {
    if (!path || !policy) return SEMANTIC_E_INVAL;
    return p5_simple_write(path, (const uint8_t *)policy, sizeof(*policy));
}

int elpis_read_iteration_policy(const char *path,
    elpis_semantic_context_iteration_policy_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;
    fseek(f, 0, SEEK_END); long sz = ftell(f);
    if (sz != (long)sizeof(*out)) { fclose(f); return SEMANTIC_E_IO; }
    fseek(f, 0, SEEK_SET); size_t rd = fread(out, 1, sizeof(*out), f);
    fclose(f); if (rd != sizeof(*out)) return SEMANTIC_E_IO;
    int rc = elpis_context_iteration_policy_validate(out);
    if (rc != SEMANTIC_OK) return rc;
    hacf_digest computed; elpis_context_iteration_policy_identity(out, &computed);
    if (memcmp(&computed, &out->policy_identity, HACF_DIGEST_BYTES) != 0) return SEMANTIC_E_DIGEST;
    return SEMANTIC_OK;
}
