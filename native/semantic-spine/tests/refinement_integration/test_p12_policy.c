/* test_p12_policy.c — Integration policy tests for P12. */
#include "elpis_semantic/refinement_integration_policy.h"
#include "elpis_semantic/identity.h"
#include <stdio.h>
#include <string.h>

static int tests_passed = 0, tests_failed = 0;
#define CHECK(cond, msg) do { \
    if (cond) { tests_passed++; printf("  PASS: %s\n", msg); } \
    else { tests_failed++; printf("  FAIL: %s\n", msg); } \
} while(0)

int main(void) {
    printf("P12 Integration Policy Tests\n");

    elpis_semantic_refinement_integration_policy_v1 policy;
    elpis_refinement_integration_policy_init(&policy);
    CHECK(policy.abi_version == REFINEMENT_INTEGRATION_POLICY_VERSION, "init sets version");

    /* Test: sidecar_isolation and reference_isolation required */
    policy.sidecar_isolation_enforced = 0;
    CHECK(elpis_refinement_integration_policy_validate(&policy) != SEMANTIC_OK,
          "policy rejects when sidecar isolation disabled");

    policy.sidecar_isolation_enforced = 1;
    policy.reference_isolation_enforced = 0;
    CHECK(elpis_refinement_integration_policy_validate(&policy) != SEMANTIC_OK,
          "policy rejects when reference isolation disabled");

    policy.reference_isolation_enforced = 1;
    policy.maximum_steps = 0;
    CHECK(elpis_refinement_integration_policy_validate(&policy) != SEMANTIC_OK,
          "policy rejects when maximum_steps is zero");

    policy.maximum_steps = 16;
    CHECK(elpis_refinement_integration_policy_validate(&policy) == SEMANTIC_OK,
          "valid policy passes validation");

    /* Test: identity determinism */
    hacf_digest d1, d2;
    elpis_refinement_integration_policy_identity(&policy, &d1);
    elpis_refinement_integration_policy_identity(&policy, &d2);
    CHECK(memcmp(d1.bytes, d2.bytes, 32) == 0, "identity is deterministic");

    printf("\nResults: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
