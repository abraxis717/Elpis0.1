/* test_bounded_view_policy.c — P5 bounded view policy tests */
#include "elpis_semantic/bounded_view_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>

static int test_default_policy_limits(void) {
    elpis_semantic_bounded_view_policy_v1 policy;
    int rc = elpis_bounded_view_policy_default(&policy);
    if (rc != SEMANTIC_OK) { printf("FAIL: default failed\n"); return 1; }

    if (policy.maximum_semantic_nodes != 256) { printf("FAIL: nodes\n"); return 1; }
    if (policy.maximum_semantic_hyperedges != 512) { printf("FAIL: hyperedges\n"); return 1; }
    if (policy.maximum_incidences != 2048) { printf("FAIL: incidences\n"); return 1; }
    if (policy.maximum_assertions != 1024) { printf("FAIL: assertions\n"); return 1; }
    if (policy.maximum_source_spans != 256) { printf("FAIL: spans\n"); return 1; }
    if (policy.maximum_transport_references != 256) { printf("FAIL: transport\n"); return 1; }
    if (policy.maximum_embedding_references != 256) { printf("FAIL: embedding\n"); return 1; }
    if (policy.maximum_metric_observations != 512) { printf("FAIL: metric\n"); return 1; }
    if (policy.maximum_graph_hops != 2) { printf("FAIL: hops\n"); return 1; }
    if (policy.maximum_metric_neighbors_per_seed != 8) { printf("FAIL: neighbors\n"); return 1; }

    printf("PASS: default_policy_limits\n");
    return 0;
}

static int test_identity_deterministic(void) {
    elpis_semantic_bounded_view_policy_v1 p1, p2;
    elpis_bounded_view_policy_default(&p1);
    elpis_bounded_view_policy_default(&p2);

    if (memcmp(&p1.policy_identity, &p2.policy_identity, HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: identity not deterministic\n");
        return 1;
    }

    printf("PASS: identity_deterministic\n");
    return 0;
}

static int test_capacity_change_changes_policy_identity(void) {
    elpis_semantic_bounded_view_policy_v1 p1, p2;
    elpis_bounded_view_policy_default(&p1);
    elpis_bounded_view_policy_default(&p2);

    p2.maximum_semantic_nodes = 512;
    elpis_bounded_view_policy_identity(&p2, &p2.policy_identity);

    if (memcmp(&p1.policy_identity, &p2.policy_identity, HACF_DIGEST_BYTES) == 0) {
        printf("FAIL: capacity change did not change identity\n");
        return 1;
    }

    printf("PASS: capacity_change_changes_policy_identity\n");
    return 0;
}

static int test_null_input(void) {
    if (elpis_bounded_view_policy_default(NULL) != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL default\n");
        return 1;
    }
    if (elpis_bounded_view_policy_validate(NULL) != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL validate\n");
        return 1;
    }
    printf("PASS: null_input\n");
    return 0;
}

static int test_zero_limits_rejected(void) {
    elpis_semantic_bounded_view_policy_v1 policy;
    elpis_bounded_view_policy_default(&policy);
    policy.maximum_graph_hops = 0;
    if (elpis_bounded_view_policy_validate(&policy) != SEMANTIC_E_INVAL) {
        printf("FAIL: zero hops not rejected\n");
        return 1;
    }
    printf("PASS: zero_limits_rejected\n");
    return 0;
}

int main(void) {
    int failures = 0;
    failures += test_default_policy_limits();
    failures += test_identity_deterministic();
    failures += test_capacity_change_changes_policy_identity();
    failures += test_null_input();
    failures += test_zero_limits_rejected();
    if (failures == 0) printf("ALL test_bounded_view_policy TESTS PASSED\n");
    else printf("FAILURES: %d\n", failures);
    return failures;
}
