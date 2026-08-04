/* test_p5_determinism.c — P5 determinism tests */
#include "elpis_semantic/context_iteration_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis_semantic/bounded_view_policy.h"
#include "elpis_semantic/context_rebind.h"
#include "elpis_semantic/context_requirement_set.h"
#include "elpis_semantic/context_progress.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>

static void set_digest(hacf_digest *d, uint32_t seed) {
    memset(d, 0, HACF_DIGEST_BYTES);
    d->bytes[0] = (uint8_t)(seed & 0xFF);
}

static int test_complete_trace_determinism(void) {
    elpis_semantic_context_iteration_policy_v1 policies[3];
    elpis_semantic_bounded_view_policy_v1 bview_policies[3];
    for (int i = 0; i < 3; i++) {
        elpis_context_iteration_policy_default(&policies[i]);
        elpis_bounded_view_policy_default(&bview_policies[i]);
    }
    for (int i = 1; i < 3; i++) {
        if (memcmp(&policies[0].policy_identity, &policies[i].policy_identity,
                   HACF_DIGEST_BYTES) != 0) {
            printf("FAIL: iteration policy identity differs at %d\n", i);
            return 1;
        }
    }
    for (int i = 1; i < 3; i++) {
        if (memcmp(&bview_policies[0].policy_identity,
                   &bview_policies[i].policy_identity,
                   HACF_DIGEST_BYTES) != 0) {
            printf("FAIL: bounded view policy identity differs at %d\n", i);
            return 1;
        }
    }
    printf("PASS: complete_trace_determinism\n");
    return 0;
}

static int test_rebind_receipt_identity(void) {
    elpis_semantic_context_requirement_set_v1 orig[3];
    elpis_semantic_context_rebind_v1 receipts[3];
    for (int i = 0; i < 3; i++) {
        elpis_context_requirement_set_init(&orig[i]);
        set_digest(&orig[i].target_query_overlay_digest, 0x11);
        set_digest(&orig[i].target_composed_view_digest, 0x22);
        orig[i].requirement_count = 1;
        set_digest(&orig[i].requirement_digests[0], 0x33);
        elpis_context_requirement_set_identity(&orig[i],
                                               &orig[i].requirement_set_identity);
    }
    hacf_digest overlay2, view2;
    set_digest(&overlay2, 0x55);
    set_digest(&view2, 0x66);
    for (int i = 0; i < 3; i++) {
        elpis_context_rebind_requirement_set(&orig[i], &overlay2, &view2,
                                              &receipts[i]);
    }
    for (int i = 1; i < 3; i++) {
        if (memcmp(&receipts[0].rebind_receipt_digest,
                   &receipts[i].rebind_receipt_digest,
                   HACF_DIGEST_BYTES) != 0) {
            printf("FAIL: rebind identity differs at %d\n", i);
            return 1;
        }
    }
    printf("PASS: rebind_receipt_identity\n");
    return 0;
}

static int test_progress_identity_deterministic(void) {
    elpis_semantic_context_progress_v1 r1, r2;
    elpis_context_progress_init(&r1);
    elpis_context_progress_init(&r2);
    r1.progress_disposition = PROGRESS_MEASURABLE_PROGRESS;
    r1.resolved_mandatory_deficit_count = 3;
    r2 = r1;
    hacf_digest d1, d2;
    elpis_context_progress_identity(&r1, &d1);
    elpis_context_progress_identity(&r2, &d2);
    if (memcmp(&d1, &d2, HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: progress identity not deterministic\n");
        return 1;
    }
    printf("PASS: progress_identity_deterministic\n");
    return 0;
}

int main(void) {
    int f = 0;
    f += test_complete_trace_determinism();
    f += test_rebind_receipt_identity();
    f += test_progress_identity_deterministic();
    if (f == 0) printf("ALL test_p5_determinism TESTS PASSED\n");
    else printf("FAILURES: %d\n", f);
    return f;
}
