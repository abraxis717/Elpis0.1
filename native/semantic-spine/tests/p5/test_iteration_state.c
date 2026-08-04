/* test_iteration_state.c — P5 iteration state tests */
#include "elpis_semantic/context_iteration_state.h"
#include "elpis_semantic/identity.h"
#include "elpis_semantic/context_iteration_policy.h"
#include "elpis_semantic/context_deficit_report.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>

static void set_digest(hacf_digest *d, uint32_t seed) {
    memset(d, 0, HACF_DIGEST_BYTES);
    d->bytes[0] = (uint8_t)(seed & 0xFF);
    d->bytes[1] = (uint8_t)((seed >> 8) & 0xFF);
    d->bytes[2] = (uint8_t)((seed >> 16) & 0xFF);
    d->bytes[3] = (uint8_t)((seed >> 24) & 0xFF);
}

static int test_round_zero_baseline(void) {
    hacf_digest overlay, report, policy;
    set_digest(&overlay, 0x11);
    set_digest(&report, 0x22);
    set_digest(&policy, 0x33);

    elpis_semantic_context_iteration_state_v1 state;
    int rc = elpis_context_iteration_state_round_zero(&state, &overlay, &report, &policy);
    if (rc != SEMANTIC_OK) {
        printf("FAIL: round_zero failed: %d\n", rc);
        return 1;
    }

    if (state.round_index != 0) {
        printf("FAIL: round_index not 0\n");
        return 1;
    }

    /* Predecessor should be all-zero */
    for (int i = 0; i < HACF_DIGEST_BYTES; i++) {
        if (state.previous_iteration_state_digest.bytes[i] != 0) {
            printf("FAIL: predecessor not all-zero for round 0\n");
            return 1;
        }
    }

    /* Identity should be set */
    int all_zero = 1;
    for (int i = 0; i < HACF_DIGEST_BYTES; i++) {
        if (state.iteration_state_digest.bytes[i] != 0) { all_zero = 0; break; }
    }
    if (all_zero) {
        printf("FAIL: state identity is all-zero\n");
        return 1;
    }

    printf("PASS: round_zero_baseline\n");
    return 0;
}

static int test_valid_round_one_predecessor(void) {
    hacf_digest overlay, report, policy;
    set_digest(&overlay, 0x11);
    set_digest(&report, 0x22);
    set_digest(&policy, 0x33);

    elpis_semantic_context_iteration_state_v1 prev;
    elpis_context_iteration_state_round_zero(&prev, &overlay, &report, &policy);

    /* Advance to round 1 */
    elpis_semantic_context_iteration_state_v1 next;
    elpis_context_iteration_state_init(&next);
    next.round_index = 1;
    memcpy(&next.root_query_overlay_digest, &overlay, HACF_DIGEST_BYTES);
    memcpy(&next.iteration_policy_digest, &policy, HACF_DIGEST_BYTES);

    hacf_digest P3, P4_view, rebound, P2_report, P2_bundle, progress;
    set_digest(&P3, 0x44);
    set_digest(&P4_view, 0x55);
    set_digest(&rebound, 0x66);
    set_digest(&P2_report, 0x77);
    set_digest(&P2_bundle, 0x88);
    set_digest(&progress, 0x99);

    int rc = elpis_context_iteration_state_advance(&next, &prev, &P3, NULL, &P4_view,
                                                    &rebound, &P2_report, &P2_bundle, &progress);
    if (rc != SEMANTIC_OK) {
        printf("FAIL: advance to round 1 failed: %d\n", rc);
        return 1;
    }

    if (next.round_index != 1) {
        printf("FAIL: round_index not 1\n");
        return 1;
    }

    printf("PASS: valid_round_one_predecessor\n");
    return 0;
}

static int test_skipped_round_rejected(void) {
    hacf_digest overlay, report, policy;
    set_digest(&overlay, 0x11);
    set_digest(&report, 0x22);
    set_digest(&policy, 0x33);

    elpis_semantic_context_iteration_state_v1 prev;
    elpis_context_iteration_state_round_zero(&prev, &overlay, &report, &policy);

    /* Try to skip to round 3 */
    elpis_semantic_context_iteration_state_v1 next;
    elpis_context_iteration_state_init(&next);
    next.round_index = 3;
    memcpy(&next.root_query_overlay_digest, &overlay, HACF_DIGEST_BYTES);
    memcpy(&next.iteration_policy_digest, &policy, HACF_DIGEST_BYTES);

    hacf_digest P3, P4_view, rebound, P2_report, P2_bundle, progress;
    set_digest(&P3, 0x44);
    set_digest(&P4_view, 0x55);
    set_digest(&rebound, 0x66);
    set_digest(&P2_report, 0x77);
    set_digest(&P2_bundle, 0x88);
    set_digest(&progress, 0x99);

    int rc = elpis_context_iteration_state_advance(&next, &prev, &P3, NULL, &P4_view,
                                                    &rebound, &P2_report, &P2_bundle, &progress);
    if (rc != SEMANTIC_E_INVAL) {
        printf("FAIL: skipped round not rejected (rc=%d)\n", rc);
        return 1;
    }

    printf("PASS: skipped_round_rejected\n");
    return 0;
}

static int test_duplicate_round_rejected(void) {
    hacf_digest overlay, report, policy;
    set_digest(&overlay, 0x11);
    set_digest(&report, 0x22);
    set_digest(&policy, 0x33);

    elpis_semantic_context_iteration_state_v1 prev;
    elpis_context_iteration_state_round_zero(&prev, &overlay, &report, &policy);

    elpis_semantic_context_iteration_state_v1 next;
    elpis_context_iteration_state_init(&next);
    next.round_index = 0; /* Same as previous */
    memcpy(&next.root_query_overlay_digest, &overlay, HACF_DIGEST_BYTES);
    memcpy(&next.iteration_policy_digest, &policy, HACF_DIGEST_BYTES);

    hacf_digest P3, P4_view, rebound, P2_report, P2_bundle, progress;
    set_digest(&P3, 0x44); set_digest(&P4_view, 0x55);
    set_digest(&rebound, 0x66); set_digest(&P2_report, 0x77);
    set_digest(&P2_bundle, 0x88); set_digest(&progress, 0x99);

    int rc = elpis_context_iteration_state_advance(&next, &prev, &P3, NULL, &P4_view,
                                                    &rebound, &P2_report, &P2_bundle, &progress);
    if (rc != SEMANTIC_E_INVAL) {
        printf("FAIL: duplicate round not rejected\n");
        return 1;
    }

    printf("PASS: duplicate_round_rejected\n");
    return 0;
}

static int test_wrong_root_overlay_rejected(void) {
    hacf_digest overlay1, report, policy;
    set_digest(&overlay1, 0x11);
    set_digest(&report, 0x22);
    set_digest(&policy, 0x33);

    elpis_semantic_context_iteration_state_v1 prev;
    elpis_context_iteration_state_round_zero(&prev, &overlay1, &report, &policy);

    /* Different overlay */
    hacf_digest overlay2;
    set_digest(&overlay2, 0xAA);

    elpis_semantic_context_iteration_state_v1 next;
    elpis_context_iteration_state_init(&next);
    next.round_index = 1;
    memcpy(&next.root_query_overlay_digest, &overlay2, HACF_DIGEST_BYTES);
    memcpy(&next.iteration_policy_digest, &policy, HACF_DIGEST_BYTES);

    hacf_digest P3, P4_view, rebound, P2_report, P2_bundle, progress;
    set_digest(&P3, 0x44); set_digest(&P4_view, 0x55);
    set_digest(&rebound, 0x66); set_digest(&P2_report, 0x77);
    set_digest(&P2_bundle, 0x88); set_digest(&progress, 0x99);

    int rc = elpis_context_iteration_state_advance(&next, &prev, &P3, NULL, &P4_view,
                                                    &rebound, &P2_report, &P2_bundle, &progress);
    if (rc != SEMANTIC_E_INVAL) {
        printf("FAIL: wrong overlay not rejected\n");
        return 1;
    }

    printf("PASS: wrong_root_overlay_rejected\n");
    return 0;
}

static int test_policy_drift_rejected(void) {
    hacf_digest overlay, report, policy1, policy2;
    set_digest(&overlay, 0x11);
    set_digest(&report, 0x22);
    set_digest(&policy1, 0x33);
    set_digest(&policy2, 0xBB);

    elpis_semantic_context_iteration_state_v1 prev;
    elpis_context_iteration_state_round_zero(&prev, &overlay, &report, &policy1);

    elpis_semantic_context_iteration_state_v1 next;
    elpis_context_iteration_state_init(&next);
    next.round_index = 1;
    memcpy(&next.root_query_overlay_digest, &overlay, HACF_DIGEST_BYTES);
    memcpy(&next.iteration_policy_digest, &policy2, HACF_DIGEST_BYTES);

    hacf_digest P3, P4_view, rebound, P2_report, P2_bundle, progress;
    set_digest(&P3, 0x44); set_digest(&P4_view, 0x55);
    set_digest(&rebound, 0x66); set_digest(&P2_report, 0x77);
    set_digest(&P2_bundle, 0x88); set_digest(&progress, 0x99);

    int rc = elpis_context_iteration_state_advance(&next, &prev, &P3, NULL, &P4_view,
                                                    &rebound, &P2_report, &P2_bundle, &progress);
    if (rc != SEMANTIC_E_INVAL) {
        printf("FAIL: policy drift not rejected\n");
        return 1;
    }

    printf("PASS: policy_drift_rejected\n");
    return 0;
}

static int test_state_identity_deterministic(void) {
    hacf_digest overlay, report, policy;
    set_digest(&overlay, 0x11);
    set_digest(&report, 0x22);
    set_digest(&policy, 0x33);

    elpis_semantic_context_iteration_state_v1 s1, s2;
    elpis_context_iteration_state_round_zero(&s1, &overlay, &report, &policy);
    elpis_context_iteration_state_round_zero(&s2, &overlay, &report, &policy);

    if (memcmp(&s1.iteration_state_digest, &s2.iteration_state_digest,
               HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: state identity not deterministic\n");
        return 1;
    }

    printf("PASS: state_identity_deterministic\n");
    return 0;
}

int main(void) {
    int failures = 0;

    failures += test_round_zero_baseline();
    failures += test_valid_round_one_predecessor();
    failures += test_skipped_round_rejected();
    failures += test_duplicate_round_rejected();
    failures += test_wrong_root_overlay_rejected();
    failures += test_policy_drift_rejected();
    failures += test_state_identity_deterministic();

    if (failures == 0) {
        printf("ALL test_iteration_state TESTS PASSED\n");
    } else {
        printf("FAILURES: %d\n", failures);
    }
    return failures;
}
