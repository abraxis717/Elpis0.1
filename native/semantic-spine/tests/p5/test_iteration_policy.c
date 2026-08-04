/* test_iteration_policy.c — P5 iteration policy tests */
#include "elpis_semantic/context_iteration_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>

static int test_default_policy_identity_deterministic(void) {
    elpis_semantic_context_iteration_policy_v1 p1, p2;
    int rc;

    rc = elpis_context_iteration_policy_default(&p1);
    assert(rc == SEMANTIC_OK);
    rc = elpis_context_iteration_policy_default(&p2);
    assert(rc == SEMANTIC_OK);

    /* Two default constructions must produce identical identity */
    if (memcmp(&p1.policy_identity, &p2.policy_identity, HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: default policy identity not deterministic\n");
        return 1;
    }

    /* Verify stored identity matches computed */
    hacf_digest computed;
    elpis_context_iteration_policy_identity(&p1, &computed);
    if (memcmp(&computed, &p1.policy_identity, HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: policy identity mismatch\n");
        return 1;
    }

    printf("PASS: default_policy_identity_deterministic\n");
    return 0;
}

static int test_round_limit_bound(void) {
    elpis_semantic_context_iteration_policy_v1 policy;
    elpis_context_iteration_policy_default(&policy);

    if (policy.maximum_retrieval_rounds != 3) {
        printf("FAIL: max rounds not 3, got %u\n", policy.maximum_retrieval_rounds);
        return 1;
    }

    if (policy.maximum_stagnant_rounds != 1) {
        printf("FAIL: max stagnant not 1, got %u\n", policy.maximum_stagnant_rounds);
        return 1;
    }

    printf("PASS: round_limit_bound\n");
    return 0;
}

static int test_stagnant_round_limit_bound(void) {
    elpis_semantic_context_iteration_policy_v1 policy;
    elpis_context_iteration_policy_default(&policy);

    if (policy.maximum_stagnant_rounds != 1) {
        printf("FAIL: stagnant rounds not 1\n");
        return 1;
    }

    /* All identical behaviors should be STOP_NO_PROGRESS */
    if (policy.identical_requirement_bundle_behavior != IDENTICAL_STOP_NO_PROGRESS) {
        printf("FAIL: identical requirement bundle not STOP_NO_PROGRESS\n");
        return 1;
    }
    if (policy.identical_typed_view_behavior != IDENTICAL_STOP_NO_PROGRESS) {
        printf("FAIL: identical typed view not STOP_NO_PROGRESS\n");
        return 1;
    }
    if (policy.identical_deficit_set_behavior != IDENTICAL_STOP_NO_PROGRESS) {
        printf("FAIL: identical deficit set not STOP_NO_PROGRESS\n");
        return 1;
    }

    printf("PASS: stagnant_round_limit_bound\n");
    return 0;
}

static int test_unknown_behavior_rejected(void) {
    elpis_semantic_context_iteration_policy_v1 policy;
    elpis_context_iteration_policy_default(&policy);
    policy.identical_requirement_bundle_behavior = 99;

    if (elpis_context_iteration_policy_validate(&policy) != SEMANTIC_E_INVAL) {
        printf("FAIL: unknown behavior not rejected\n");
        return 1;
    }

    printf("PASS: unknown_behavior_rejected\n");
    return 0;
}

static int test_nonzero_reserved_rejected(void) {
    elpis_semantic_context_iteration_policy_v1 policy;
    elpis_context_iteration_policy_default(&policy);
    policy.reserved[5] = 0xAB;

    if (elpis_context_iteration_policy_validate(&policy) != SEMANTIC_E_RESERVATION) {
        printf("FAIL: nonzero reserved not rejected\n");
        return 1;
    }

    printf("PASS: nonzero_reserved_rejected\n");
    return 0;
}

static int test_policy_change_changes_identity(void) {
    elpis_semantic_context_iteration_policy_v1 p1, p2;
    elpis_context_iteration_policy_default(&p1);
    elpis_context_iteration_policy_default(&p2);

    p2.maximum_retrieval_rounds = 5;
    elpis_context_iteration_policy_identity(&p2, &p2.policy_identity);

    if (memcmp(&p1.policy_identity, &p2.policy_identity, HACF_DIGEST_BYTES) == 0) {
        printf("FAIL: policy change did not change identity\n");
        return 1;
    }

    printf("PASS: policy_change_changes_identity\n");
    return 0;
}

static int test_zero_limits_rejected(void) {
    elpis_semantic_context_iteration_policy_v1 policy;
    elpis_context_iteration_policy_default(&policy);

    policy.maximum_retrieval_rounds = 0;
    if (elpis_context_iteration_policy_validate(&policy) != SEMANTIC_E_INVAL) {
        printf("FAIL: zero max rounds not rejected\n");
        return 1;
    }

    policy.maximum_retrieval_rounds = 3;
    policy.maximum_stagnant_rounds = 0;
    if (elpis_context_iteration_policy_validate(&policy) != SEMANTIC_E_INVAL) {
        printf("FAIL: zero stagnant rounds not rejected\n");
        return 1;
    }

    printf("PASS: zero_limits_rejected\n");
    return 0;
}

static int test_null_input(void) {
    elpis_semantic_context_iteration_policy_v1 policy;
    hacf_digest digest;

    if (elpis_context_iteration_policy_default(NULL) != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL default not rejected\n");
        return 1;
    }
    if (elpis_context_iteration_policy_identity(NULL, &digest) != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL identity not rejected\n");
        return 1;
    }
    if (elpis_context_iteration_policy_validate(NULL) != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL validate not rejected\n");
        return 1;
    }

    printf("PASS: null_input\n");
    return 0;
}

int main(void) {
    int failures = 0;

    failures += test_default_policy_identity_deterministic();
    failures += test_round_limit_bound();
    failures += test_stagnant_round_limit_bound();
    failures += test_unknown_behavior_rejected();
    failures += test_nonzero_reserved_rejected();
    failures += test_policy_change_changes_identity();
    failures += test_zero_limits_rejected();
    failures += test_null_input();

    if (failures == 0) {
        printf("ALL test_iteration_policy TESTS PASSED\n");
    } else {
        printf("FAILURES: %d\n", failures);
    }
    return failures;
}
