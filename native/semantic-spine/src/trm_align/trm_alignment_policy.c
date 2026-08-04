#include "elpis_semantic/trm_alignment_policy.h"
#include <string.h>
#include <stdio.h>
#include <openssl/sha.h>

static void sha256_hex(const void *data, size_t len, char *out, size_t out_len) {
    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256(data, len, hash);
    for (int i = 0; i < SHA256_DIGEST_LENGTH && (size_t)(i * 2 + 2) < out_len; i++) {
        sprintf(out + i * 2, "%02x", hash[i]);
    }
}

trm_alignment_policy_t trm_alignment_policy_create(const trm_native_contract_t *native) {
    trm_alignment_policy_t policy;
    memset(&policy, 0, sizeof(policy));
    policy.abi_version = TRM_ALIGNMENT_POLICY_ABI_VERSION;
    policy.sealed = 0;

    if (native) {
        strncpy(policy.native_contract_digest, native->contract_digest, TRM_DIGEST_LEN - 1);
    }

    // Default enabled lanes
    strncpy(policy.enabled_representation_lanes[0], "R0_P8_PRODUCTION_ENCODING", TRM_LANE_ID_LEN - 1);
    policy.representation_lane_count = 1;
    strncpy(policy.enabled_placement_lanes[0], "P1_NATIVE_VALID_PLACEMENT", TRM_LANE_ID_LEN - 1);
    policy.placement_lane_count = 1;
    strncpy(policy.enabled_decoder_analyses[0], "P8_ARGMAX_LOWEST_TIEBREAK", TRM_LANE_ID_LEN - 1);
    policy.decoder_analysis_count = 1;
    strncpy(policy.enabled_guard_analyses[0], "P8_ATOMIC_GUARD", TRM_LANE_ID_LEN - 1);
    policy.guard_analysis_count = 1;
    strncpy(policy.enabled_recursive_shift_analyses[0], "STEP_ZERO_VS_POST_COMMIT", TRM_LANE_ID_LEN - 1);
    policy.recursive_shift_count = 1;
    policy.fixture_count_per_control = 16;
    policy.maximum_model_invocations_per_fixture = 4;
    return policy;
}

int trm_alignment_policy_seal(trm_alignment_policy_t *policy) {
    if (!policy) return 0;
    policy->sealed = 1;
    trm_alignment_policy_compute_digest(policy);
    return 1;
}

int trm_alignment_policy_is_sealed(const trm_alignment_policy_t *policy) {
    return policy ? policy->sealed : 0;
}

int trm_alignment_policy_validate(const trm_alignment_policy_t *policy) {
    if (!policy) return 0;
    if (policy->abi_version != TRM_ALIGNMENT_POLICY_ABI_VERSION) return 0;
    if (policy->fixture_count_per_control == 0) return 0;
    if (policy->hypothesis_count == 0) return 0;
    return 1;
}

void trm_alignment_policy_compute_digest(trm_alignment_policy_t *policy) {
    if (!policy) return;
    sha256_hex(policy, sizeof(trm_alignment_policy_t),
               policy->alignment_policy_digest, TRM_DIGEST_LEN);
}

int trm_alignment_policy_add_hypothesis(trm_alignment_policy_t *policy, trm_hypothesis_t h) {
    if (!policy || policy->sealed) return 0;
    if (policy->hypothesis_count >= TRM_HYPOTHESIS_MAX) return 0;
    policy->hypotheses[policy->hypothesis_count++] = h;
    return 1;
}
