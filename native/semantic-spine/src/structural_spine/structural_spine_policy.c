/* structural_spine_policy.c — Immutable structural spine policy v1. */
#include "elpis_semantic/structural_spine_policy.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>
#include <strings.h>
#include <stdint.h>

void elpis_spine_policy_init(elpis_semantic_structural_spine_policy_v1 *policy) {
    if (!policy) return;
    memset(policy, 0, sizeof(*policy));
    policy->abi_version = SPINE_POLICY_ABI_VERSION;
    policy->maximum_refinement_steps = 16;
    policy->semantic_mutation_policy = SPINE_SEMANTIC_MUTATION_FORBIDDEN;
    policy->authority_mutation_policy = SPINE_AUTHORITY_MUTATION_FORBIDDEN;
    policy->sidecar_access_policy = SPINE_SIDECAR_ACCESS_FORBIDDEN;
    policy->reference_access_policy = SPINE_REFERENCE_ACCESS_FORBIDDEN;
    policy->state_commit_policy = SPINE_STATE_COMMIT_GUARDED_SUDOKU_VALID_ONLY;
    policy->failure_policy = SPINE_FAILURE_RETAIN_LAST_COMMITTED_STATE;
    policy->closure_policy = SPINE_CLOSURE_EXACT_BOUNDARY_REPLAY_REQUIRED;
    strncpy(policy->active_backend, "DETERMINISTIC_MRV_SOLVER", SPINE_MAX_BACKEND_NAME - 1);
    strncpy(policy->active_adapter, "DETERMINISTIC_MRV_SOLVER", SPINE_MAX_BACKEND_NAME - 1);
}

int elpis_spine_policy_identity(
    const elpis_semantic_structural_spine_policy_v1 *policy, hacf_digest *out) {
    if (!policy || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.structural_spine_policy.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f;
    f = policy->abi_version;                elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, policy->P5_handoff_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, policy->P6_topology_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, policy->P7_grid81_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, policy->P8_adapter_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, policy->P9_guard_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, policy->P12_integration_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)policy->active_backend, SPINE_MAX_BACKEND_NAME);
    elpis_sha256_update(&ctx, (const uint8_t *)policy->active_adapter, SPINE_MAX_BACKEND_NAME);
    elpis_sha256_update(&ctx, policy->active_backend_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, policy->active_adapter_digest.bytes, HACF_DIGEST_BYTES);
    f = policy->maximum_refinement_steps;   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->semantic_mutation_policy;   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->authority_mutation_policy;  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->sidecar_access_policy;      elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->reference_access_policy;    elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->state_commit_policy;        elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->failure_policy;             elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->closure_policy;             elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_spine_policy_validate(const elpis_semantic_structural_spine_policy_v1 *policy) {
    if (!policy) return SEMANTIC_E_INVAL;
    if (policy->abi_version != SPINE_POLICY_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (policy->maximum_refinement_steps != 16) return SEMANTIC_E_INVAL;
    if (policy->semantic_mutation_policy != SPINE_SEMANTIC_MUTATION_FORBIDDEN) return SEMANTIC_E_INVAL;
    if (policy->authority_mutation_policy != SPINE_AUTHORITY_MUTATION_FORBIDDEN) return SEMANTIC_E_INVAL;
    if (policy->sidecar_access_policy != SPINE_SIDECAR_ACCESS_FORBIDDEN) return SEMANTIC_E_INVAL;
    if (policy->reference_access_policy != SPINE_REFERENCE_ACCESS_FORBIDDEN) return SEMANTIC_E_INVAL;
    if (policy->state_commit_policy != SPINE_STATE_COMMIT_GUARDED_SUDOKU_VALID_ONLY) return SEMANTIC_E_INVAL;
    if (policy->failure_policy != SPINE_FAILURE_RETAIN_LAST_COMMITTED_STATE) return SEMANTIC_E_INVAL;
    if (policy->closure_policy != SPINE_CLOSURE_EXACT_BOUNDARY_REPLAY_REQUIRED) return SEMANTIC_E_INVAL;
    if (strncmp(policy->active_backend, "DETERMINISTIC_MRV_SOLVER", SPINE_MAX_BACKEND_NAME) != 0) return SEMANTIC_E_INVAL;
    if (strncmp(policy->active_adapter, "DETERMINISTIC_MRV_SOLVER", SPINE_MAX_BACKEND_NAME) != 0) return SEMANTIC_E_INVAL;
    /* Reserved must be zeroed */
    for (size_t i = 0; i < sizeof(policy->reserved); i++) {
        if (policy->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }
    return SEMANTIC_OK;
}

int elpis_spine_policy_is_canonical_backend(
    const elpis_semantic_structural_spine_policy_v1 *policy) {
    if (!policy) return 0;
    return strncmp(policy->active_backend, "DETERMINISTIC_MRV_SOLVER", SPINE_MAX_BACKEND_NAME) == 0;
}

int elpis_spine_policy_is_ACTV1_blocked(
    const elpis_semantic_structural_spine_policy_v1 *policy) {
    if (!policy) return 0;
    /* ACTV1 must not be active */
    return strncmp(policy->active_backend, "ACTV1_Inner", SPINE_MAX_BACKEND_NAME) != 0;
}
