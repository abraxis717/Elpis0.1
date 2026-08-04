/* trm_efficacy_policy.c — Pre-registered efficacy policy implementation. */
#include "elpis_semantic/trm_efficacy_policy.h"
#include <stdio.h>
#include <string.h>
#include "elpis/sha256.h"

void elpis_trm_efficacy_policy_init(
    elpis_semantic_trm_efficacy_policy_v1 *policy) {
    memset(policy, 0, sizeof(*policy));
    policy->abi_version = TRM_EFFICACY_POLICY_VERSION;
    policy->fixture_count = TRM_EFFICACY_POLICY_FIXTURE_COUNT;
    policy->clue_stratum_count = TRM_EFFICACY_POLICY_CLUE_STRATUM_COUNT;
    policy->fixtures_per_stratum = TRM_EFFICACY_POLICY_FIXTURES_PER_STRATUM;
    policy->clue_counts[0] = TRM_EFFICACY_POLICY_CLUE_COUNT_0;
    policy->clue_counts[1] = TRM_EFFICACY_POLICY_CLUE_COUNT_1;
    policy->clue_counts[2] = TRM_EFFICACY_POLICY_CLUE_COUNT_2;
    policy->clue_counts[3] = TRM_EFFICACY_POLICY_CLUE_COUNT_3;
    policy->minimum_positive_fixture_count = TRM_EFFICACY_MIN_POSITIVE_FIXTURES;
    policy->maximum_negative_fixture_count = TRM_EFFICACY_MAX_NEGATIVE_FIXTURES;
    policy->maximum_wrong_final_cell_count = TRM_EFFICACY_MAX_WRONG_FINAL_CELLS;
    policy->minimum_aggregate_net_correct_gain = 1;
    policy->require_each_stratum_improvement = TRM_EFFICACY_REQUIRE_STRATUM_IMPROVEMENT;
    policy->require_bounded_not_worse_than_one_step = TRM_EFFICACY_REQUIRE_BOUNDED_NOT_WORSE;
}

int elpis_trm_efficacy_policy_identity(
    const elpis_semantic_trm_efficacy_policy_v1 *policy,
    hacf_digest *out) {
    const char *domain = "elpis.semantic.trm_efficacy_policy.v1";
    uint8_t hash[32];
    elpis_sha256((const void *)policy, offsetof(elpis_semantic_trm_efficacy_policy_v1, reserved), hash);
    memcpy(out->bytes, hash, sizeof(out->bytes));
    return 0;
}

int elpis_trm_efficacy_policy_validate(
    const elpis_semantic_trm_efficacy_policy_v1 *policy) {
    if (policy->abi_version != TRM_EFFICACY_POLICY_VERSION) return -1;
    if (policy->fixture_count != TRM_EFFICACY_POLICY_FIXTURE_COUNT) return -1;
    if (policy->clue_stratum_count != TRM_EFFICACY_POLICY_CLUE_STRATUM_COUNT) return -1;
    return 0;
}

int elpis_write_trm_efficacy_policy(const char *path,
    const elpis_semantic_trm_efficacy_policy_v1 *policy) {
    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    size_t sz = offsetof(elpis_semantic_trm_efficacy_policy_v1, reserved) + sizeof(policy->reserved);
    if (fwrite(policy, 1, sz, f) != sz) { fclose(f); return -1; }
    fclose(f);
    return 0;
}

int elpis_read_trm_efficacy_policy(const char *path,
    elpis_semantic_trm_efficacy_policy_v1 *out) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    size_t sz = offsetof(elpis_semantic_trm_efficacy_policy_v1, reserved) + sizeof(out->reserved);
    if (fread(out, 1, sz, f) != sz) { fclose(f); return -1; }
    fclose(f);
    return elpis_trm_efficacy_policy_validate(out);
}
