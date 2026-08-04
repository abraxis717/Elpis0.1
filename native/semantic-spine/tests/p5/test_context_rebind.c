/* test_context_rebind.c — P5 requirement-set rebind tests */
#include "elpis_semantic/context_rebind.h"
#include "elpis_semantic/context_requirement.h"
#include "elpis_semantic/context_requirement_set.h"
#include "elpis_semantic/context_deficit.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>

static void set_random_digest(hacf_digest *d, uint32_t seed) {
    memset(d, 0, HACF_DIGEST_BYTES);
    uint8_t *b = d->bytes;
    for (uint32_t i = 0; i < 4; i++) {
        b[i] = (uint8_t)((seed >> (8 * i)) & 0xFF);
    }
}

static int test_same_semantic_requirements_rebound_to_new_view(void) {
    /* Create original requirement set */
    elpis_semantic_context_requirement_set_v1 orig;
    elpis_context_requirement_set_init(&orig);

    hacf_digest overlay1;
    set_random_digest(&overlay1, 0x11111111);
    memcpy(&orig.target_query_overlay_digest, &overlay1, HACF_DIGEST_BYTES);

    hacf_digest view1;
    set_random_digest(&view1, 0x22222222);
    memcpy(&orig.target_composed_view_digest, &view1, HACF_DIGEST_BYTES);

    orig.requirement_count = 1;
    hacf_digest req1;
    set_random_digest(&req1, 0x33333333);
    memcpy(&orig.requirement_digests[0], &req1, HACF_DIGEST_BYTES);

    set_random_digest(&orig.requirement_set_policy_digest, 0x44444444);
    elpis_context_requirement_set_identity(&orig, &orig.requirement_set_identity);

    /* New view */
    hacf_digest overlay2;
    set_random_digest(&overlay2, 0x55555555);
    hacf_digest view2;
    set_random_digest(&view2, 0x66666666);

    /* Rebind */
    elpis_semantic_context_rebind_v1 receipt;
    int rc = elpis_context_rebind_requirement_set(&orig, &overlay2, &view2, &receipt);
    if (rc != SEMANTIC_OK) {
        printf("FAIL: rebind failed: %d\n", rc);
        return 1;
    }
    if (receipt.disposition != REQUIREMENT_SET_REBOUND) {
        printf("FAIL: disposition not REBOUND\n");
        return 1;
    }

    /* New identity must differ from original */
    if (memcmp(&receipt.original_requirement_set_digest,
               &receipt.rebound_requirement_set_digest, HACF_DIGEST_BYTES) == 0) {
        printf("FAIL: new identity equals original\n");
        return 1;
    }

    /* Original requirement digests preserved */
    if (receipt.original_requirement_count != orig.requirement_count) {
        printf("FAIL: requirement count mismatch\n");
        return 1;
    }
    for (uint32_t i = 0; i < orig.requirement_count; i++) {
        if (memcmp(&receipt.ordered_original_requirement_digests[i],
                   &orig.requirement_digests[i], HACF_DIGEST_BYTES) != 0) {
            printf("FAIL: original requirement digest %u not preserved\n", i);
            return 1;
        }
    }

    /* Receipt identity verified */
    hacf_digest computed;
    elpis_context_rebind_identity(&receipt, &computed);
    if (memcmp(&computed, &receipt.rebind_receipt_digest, HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: receipt identity mismatch\n");
        return 1;
    }

    /* Validation passes */
    if (elpis_context_rebind_validate(&receipt) != SEMANTIC_OK) {
        printf("FAIL: receipt validation failed\n");
        return 1;
    }

    /* Construct rebound set */
    elpis_semantic_context_requirement_set_v1 rebound;
    rc = elpis_context_rebind_construct_set(&receipt, &rebound);
    if (rc != SEMANTIC_OK) {
        printf("FAIL: construct rebound set failed\n");
        return 1;
    }
    if (memcmp(&rebound.target_composed_view_digest, &view2, HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: rebound view digest mismatch\n");
        return 1;
    }

    printf("PASS: same_semantic_requirements_rebound_to_new_view\n");
    return 0;
}

static int test_original_requirement_set_unchanged(void) {
    elpis_semantic_context_requirement_set_v1 orig;
    elpis_context_requirement_set_init(&orig);
    set_random_digest(&orig.target_query_overlay_digest, 0x11111111);
    set_random_digest(&orig.target_composed_view_digest, 0x22222222);
    orig.requirement_count = 1;
    set_random_digest(&orig.requirement_digests[0], 0x33333333);
    elpis_context_requirement_set_identity(&orig, &orig.requirement_set_identity);

    hacf_digest orig_identity_copy = orig.requirement_set_identity;

    hacf_digest overlay2;
    set_random_digest(&overlay2, 0x55555555);
    hacf_digest view2;
    set_random_digest(&view2, 0x66666666);

    elpis_semantic_context_rebind_v1 receipt;
    elpis_context_rebind_requirement_set(&orig, &overlay2, &view2, &receipt);

    /* Original must be unchanged */
    if (memcmp(&orig.requirement_set_identity, &orig_identity_copy,
               HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: original set was mutated\n");
        return 1;
    }

    printf("PASS: original_requirement_set_unchanged\n");
    return 0;
}

static int test_threshold_change_rejected(void) {
    /* Rebind should preserve all requirement digests.
     * A changed threshold would produce a different requirement digest,
     * which the rebind verification would reject. */
    elpis_semantic_context_requirement_set_v1 orig;
    elpis_context_requirement_set_init(&orig);
    set_random_digest(&orig.target_query_overlay_digest, 0x11111111);
    set_random_digest(&orig.target_composed_view_digest, 0x22222222);
    orig.requirement_count = 1;
    set_random_digest(&orig.requirement_digests[0], 0x33333333);
    elpis_context_requirement_set_identity(&orig, &orig.requirement_set_identity);

    hacf_digest overlay2;
    set_random_digest(&overlay2, 0x55555555);
    hacf_digest view2;
    set_random_digest(&view2, 0x66666666);

    elpis_semantic_context_rebind_v1 receipt;
    int rc = elpis_context_rebind_requirement_set(&orig, &overlay2, &view2, &receipt);
    assert(rc == SEMANTIC_OK);

    /* Semantic equivalence: original and rebound digests must match */
    rc = elpis_context_rebind_verify_semantic_equivalence(&receipt);
    assert(rc == SEMANTIC_OK);

    /* If we manually tamper with a rebound digest (simulating threshold change) */
    receipt.ordered_rebound_requirement_digests[0].bytes[0] ^= 0xFF;

    rc = elpis_context_rebind_verify_semantic_equivalence(&receipt);
    if (rc == SEMANTIC_OK) {
        printf("FAIL: tampered digest was accepted\n");
        return 1;
    }

    printf("PASS: threshold_change_rejected\n");
    return 0;
}

static int test_null_input_rejected(void) {
    elpis_semantic_context_rebind_v1 receipt;
    elpis_semantic_context_requirement_set_v1 orig;
    elpis_context_requirement_set_init(&orig);

    /* NULL original set */
    if (elpis_context_rebind_requirement_set(NULL, NULL, NULL, &receipt) != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL original not rejected\n");
        return 1;
    }

    /* NULL receipt */
    if (elpis_context_rebind_requirement_set(&orig, NULL, NULL, NULL) != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL receipt not rejected\n");
        return 1;
    }

    /* NULL receipt for validate */
    if (elpis_context_rebind_validate(NULL) != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL validate not rejected\n");
        return 1;
    }

    /* NULL for identity */
    hacf_digest out;
    if (elpis_context_rebind_identity(NULL, &out) != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL identity not rejected\n");
        return 1;
    }

    printf("PASS: null_input_rejected\n");
    return 0;
}

static int test_reserved_field_rejection(void) {
    elpis_semantic_context_rebind_v1 receipt;
    elpis_context_rebind_init(&receipt);
    receipt.reserved[0] = 0xFF;

    if (elpis_context_rebind_validate(&receipt) != SEMANTIC_E_RESERVATION) {
        printf("FAIL: reserved field not rejected\n");
        return 1;
    }

    printf("PASS: reserved_field_rejection\n");
    return 0;
}

int main(void) {
    int failures = 0;

    failures += test_same_semantic_requirements_rebound_to_new_view();
    failures += test_original_requirement_set_unchanged();
    failures += test_threshold_change_rejected();
    failures += test_null_input_rejected();
    failures += test_reserved_field_rejection();

    if (failures == 0) {
        printf("ALL test_context_rebind TESTS PASSED\n");
    } else {
        printf("FAILURES: %d\n", failures);
    }
    return failures;
}
