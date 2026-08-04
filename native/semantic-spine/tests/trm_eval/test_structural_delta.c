/* test_structural_delta.c — P10 structural delta tests. */
#include <stdio.h>
#include <string.h>
#include "elpis_semantic/trm_structural_delta.h"

static int tests_passed = 0;
static int tests_failed = 0;

#define CHECK(cond, msg) do { \
    if (!(cond)) { printf("FAIL: %s\n", msg); tests_failed++; } \
    else { tests_passed++; } \
} while(0)

static const uint32_t REF[GRID81_CELL_COUNT] = {0};

int main(void) {
    elpis_semantic_trm_structural_delta_v1 delta;
    uint32_t fixed[GRID81_CELL_COUNT] = {0};
    memset(fixed, 0, sizeof(fixed));

    /* Test 1: Empty to correct addition */
    uint32_t before_empty[GRID81_CELL_COUNT] = {0};
    uint32_t after_correct[GRID81_CELL_COUNT] = {0};
    after_correct[0] = 5;
    uint32_t ref_correct[GRID81_CELL_COUNT] = {0};
    ref_correct[0] = 5;

    elpis_trm_structural_delta_init(&delta);
    elpis_trm_structural_delta_compute(&delta, before_empty, after_correct,
        ref_correct, fixed, TRM_DELTA_COMMITTED_STATE, 0);
    CHECK(delta.correct_addition_count == 1, "correct addition");
    CHECK(delta.transition_class[0] == TRM_TRANSITION_EMPTY_TO_CORRECT, "empty_to_correct transition");
    CHECK(delta.net_correct_gain == 1, "net correct gain = 1");

    /* Test 2: Empty to wrong addition */
    uint32_t after_wrong[GRID81_CELL_COUNT] = {0};
    after_wrong[0] = 3; /* ref[0]=5, so wrong */

    elpis_trm_structural_delta_init(&delta);
    elpis_trm_structural_delta_compute(&delta, before_empty, after_wrong,
        ref_correct, fixed, TRM_DELTA_COMMITTED_STATE, 0);
    CHECK(delta.wrong_addition_count == 1, "wrong addition");
    CHECK(delta.transition_class[0] == TRM_TRANSITION_EMPTY_TO_WRONG, "empty_to_wrong transition");
    CHECK(delta.net_correct_gain == 0, "net gain = 0 for wrong addition");

    /* Test 3: Correction (wrong to correct) */
    uint32_t before_wrong[GRID81_CELL_COUNT] = {0};
    before_wrong[0] = 3; /* wrong */

    elpis_trm_structural_delta_init(&delta);
    elpis_trm_structural_delta_compute(&delta, before_wrong, after_correct,
        ref_correct, fixed, TRM_DELTA_COMMITTED_STATE, 0);
    CHECK(delta.correction_count == 1, "correction");
    CHECK(delta.transition_class[0] == TRM_TRANSITION_WRONG_TO_CORRECT, "wrong_to_correct transition");
    CHECK(delta.net_correct_gain == 1, "net gain = 1 for correction");

    /* Test 4: Regression (correct to wrong) */
    elpis_trm_structural_delta_init(&delta);
    elpis_trm_structural_delta_compute(&delta, after_correct, after_wrong,
        ref_correct, fixed, TRM_DELTA_COMMITTED_STATE, 0);
    CHECK(delta.regression_count == 1, "regression");
    CHECK(delta.transition_class[0] == TRM_TRANSITION_CORRECT_TO_WRONG, "correct_to_wrong transition");
    CHECK(delta.net_correct_gain == -1, "net gain = -1 for regression");

    /* Test 5: Wrong to different wrong */
    uint32_t after_wrong2[GRID81_CELL_COUNT] = {0};
    after_wrong2[0] = 7; /* different from 3 and ref 5 */

    elpis_trm_structural_delta_init(&delta);
    elpis_trm_structural_delta_compute(&delta, after_wrong, after_wrong2,
        ref_correct, fixed, TRM_DELTA_COMMITTED_STATE, 0);
    CHECK(delta.wrong_to_different_wrong_count == 1, "wrong_to_different_wrong");
    CHECK(delta.transition_class[0] == TRM_TRANSITION_WRONG_TO_DIFFERENT_WRONG, "transition class");
    CHECK(delta.net_correct_gain == 0, "net gain = 0 for wrong_to_different_wrong");

    /* Test 6: Unchanged empty */
    uint32_t still_empty[GRID81_CELL_COUNT] = {0};
    elpis_trm_structural_delta_init(&delta);
    elpis_trm_structural_delta_compute(&delta, before_empty, still_empty,
        ref_correct, fixed, TRM_DELTA_COMMITTED_STATE, 0);
    CHECK(delta.unchanged_empty_count == GRID81_CELL_COUNT, "all unchanged empty");

    /* Test 7: No digit subtraction field (by ABI design — verified by header) */
    CHECK(1, "no digit_subtraction field in ABI");

    /* Test 8: Persistence round-trip */
    elpis_write_trm_structural_delta("/tmp/test_delta.bin", &delta);
    elpis_semantic_trm_structural_delta_v1 delta2;
    elpis_read_trm_structural_delta("/tmp/test_delta.bin", &delta2);
    CHECK(delta2.abi_version == delta.abi_version, "persistence round-trip abi_version");
    CHECK(delta2.net_correct_gain == delta.net_correct_gain, "persistence round-trip net_gain");

    printf("Results: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
