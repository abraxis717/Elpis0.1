/* test_context_progress.c — P5 progress measurement tests */
#include "elpis_semantic/context_progress.h"
#include "elpis_semantic/identity.h"
#include "elpis_semantic/context_deficit.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>

static void set_digest(hacf_digest *d, uint32_t seed) {
    memset(d, 0, HACF_DIGEST_BYTES);
    d->bytes[0] = (uint8_t)(seed & 0xFF);
    d->bytes[1] = (uint8_t)((seed >> 8) & 0xFF);
    d->bytes[2] = (uint8_t)((seed >> 16) & 0xFF);
    d->bytes[3] = (uint8_t)((seed >> 24) & 0xFF);
}

static int test_first_evaluated_round_classified(void) {
    elpis_semantic_context_progress_v1 report;
    elpis_context_progress_init(&report);

    /* No previous results = first round */
    int rc = elpis_context_measure_progress(NULL, NULL, NULL, 0, NULL, 0, &report);
    if (rc != SEMANTIC_OK) {
        printf("FAIL: first round measure failed: %d\n", rc);
        return 1;
    }

    if (report.progress_disposition != PROGRESS_FIRST_EVALUATED_ROUND) {
        printf("FAIL: first round not classified as FIRST_EVALUATED (got %u)\n",
               report.progress_disposition);
        return 1;
    }

    printf("PASS: first_evaluated_round_classified\n");
    return 0;
}

static int test_identical_typed_view_detected(void) {
    elpis_semantic_context_progress_v1 prev_in, curr_in;
    elpis_context_progress_init(&prev_in);
    elpis_context_progress_init(&curr_in);

    /* Same typed view digest */
    set_digest(&prev_in.previous_typed_evidence_view_digest, 0xAA);
    set_digest(&curr_in.current_typed_evidence_view_digest, 0xAA);

    /* Pass real result arrays to indicate this is not the first round */
    elpis_semantic_requirement_result_v1 prev_r, curr_r;
    elpis_requirement_result_init(&prev_r);
    elpis_requirement_result_init(&curr_r);
    set_digest(&prev_r.requirement_digest, 0xBB);
    set_digest(&curr_r.requirement_digest, 0xBB);

    elpis_semantic_context_progress_v1 report;
    int rc = elpis_context_measure_progress(&prev_in, &curr_in, &prev_r, 1, &curr_r, 1, &report);
    if (rc != SEMANTIC_OK) {
        printf("FAIL: identical view measure failed\n");
        return 1;
    }

    if (report.progress_disposition != PROGRESS_NO_PROGRESS_IDENTICAL_VIEW) {
        printf("FAIL: identical view not detected (got %u)\n",
               report.progress_disposition);
        return 1;
    }

    printf("PASS: identical_typed_view_detected\n");
    return 0;
}

static int test_identical_view_with_results(void) {
    elpis_semantic_context_progress_v1 prev_in, curr_in;
    elpis_context_progress_init(&prev_in);
    elpis_context_progress_init(&curr_in);

    /* Same typed view digest, with result arrays so it's not first round */
    set_digest(&prev_in.previous_typed_evidence_view_digest, 0xAA);
    set_digest(&curr_in.current_typed_evidence_view_digest, 0xAA);

    elpis_semantic_requirement_result_v1 prev_r2, curr_r2;
    elpis_requirement_result_init(&prev_r2);
    elpis_requirement_result_init(&curr_r2);
    set_digest(&prev_r2.requirement_digest, 0xCC);
    set_digest(&curr_r2.requirement_digest, 0xCC);

    elpis_semantic_context_progress_v1 report;
    int rc = elpis_context_measure_progress(&prev_in, &curr_in, &prev_r2, 1, &curr_r2, 1, &report);
    if (rc != SEMANTIC_OK) {
        printf("FAIL: identical view measure failed\n");
        return 1;
    }

    if (report.progress_disposition != PROGRESS_NO_PROGRESS_IDENTICAL_VIEW) {
        printf("FAIL: identical view not detected with results (got %u)\n",
               report.progress_disposition);
        return 1;
    }
    printf("PASS: identical_view_with_results\n");
    return 0;
}

static int test_identical_requirement_bundle_detected(void) {
    elpis_semantic_context_progress_v1 prev_in, curr_in;
    elpis_context_progress_init(&prev_in);
    elpis_context_progress_init(&curr_in);

    /* Different views but identical requirement bundles */
    set_digest(&prev_in.previous_typed_evidence_view_digest, 0x11);
    set_digest(&curr_in.current_typed_evidence_view_digest, 0x22);
    set_digest(&prev_in.previous_retrieval_requirement_bundle_digest, 0xAA);
    set_digest(&curr_in.current_retrieval_requirement_bundle_digest, 0xAA);

    elpis_semantic_requirement_result_v1 prev_r3, curr_r3;
    elpis_requirement_result_init(&prev_r3);
    elpis_requirement_result_init(&curr_r3);
    set_digest(&prev_r3.requirement_digest, 0xDD);
    set_digest(&curr_r3.requirement_digest, 0xDD);

    elpis_semantic_context_progress_v1 report;
    int rc = elpis_context_measure_progress(&prev_in, &curr_in, &prev_r3, 1, &curr_r3, 1, &report);
    if (rc != SEMANTIC_OK) {
        printf("FAIL: identical bundle measure failed\n");
        return 1;
    }

    if (report.progress_disposition != PROGRESS_NO_PROGRESS_IDENTICAL_REQUIREMENTS) {
        printf("FAIL: identical bundle not detected (got %u)\n",
               report.progress_disposition);
        return 1;
    }

    printf("PASS: identical_requirement_bundle_detected\n");
    return 0;
}

static int test_identical_bundle_with_results(void) {
    elpis_semantic_context_progress_v1 prev_in, curr_in;
    elpis_context_progress_init(&prev_in);
    elpis_context_progress_init(&curr_in);

    /* Different views but identical requirement bundles, with result arrays */
    set_digest(&prev_in.previous_typed_evidence_view_digest, 0x11);
    set_digest(&curr_in.current_typed_evidence_view_digest, 0x22);
    set_digest(&prev_in.previous_retrieval_requirement_bundle_digest, 0xAA);
    set_digest(&curr_in.current_retrieval_requirement_bundle_digest, 0xAA);

    elpis_semantic_requirement_result_v1 prev_r4, curr_r4;
    elpis_requirement_result_init(&prev_r4);
    elpis_requirement_result_init(&curr_r4);
    set_digest(&prev_r4.requirement_digest, 0xEE);
    set_digest(&curr_r4.requirement_digest, 0xEE);

    elpis_semantic_context_progress_v1 report;
    int rc = elpis_context_measure_progress(&prev_in, &curr_in, &prev_r4, 1, &curr_r4, 1, &report);
    if (rc != SEMANTIC_OK) {
        printf("FAIL: identical bundle measure failed\n");
        return 1;
    }

    if (report.progress_disposition != PROGRESS_NO_PROGRESS_IDENTICAL_REQUIREMENTS) {
        printf("FAIL: identical bundle not detected with results (got %u)\n",
               report.progress_disposition);
        return 1;
    }
    printf("PASS: identical_bundle_with_results\n");
    return 0;
}

static int test_resolved_mandatory_deficit_counted(void) {
    elpis_semantic_requirement_result_v1 prev_results[1], curr_results[1];
    elpis_requirement_result_init(&prev_results[0]);
    elpis_requirement_result_init(&curr_results[0]);

    /* Same requirement */
    set_digest(&prev_results[0].requirement_digest, 0xBB);
    set_digest(&curr_results[0].requirement_digest, 0xBB);

    /* Was unsatisfied, now satisfied */
    prev_results[0].satisfaction_status = SAT_STATUS_UNSATISFIED;
    curr_results[0].satisfaction_status = SAT_STATUS_SATISFIED;

    elpis_semantic_context_progress_v1 report;
    int rc = elpis_context_measure_progress(NULL, NULL,
                                             prev_results, 1,
                                             curr_results, 1,
                                             &report);
    if (rc != SEMANTIC_OK) {
        printf("FAIL: deficit delta measure failed\n");
        return 1;
    }

    if (report.resolved_mandatory_deficit_count != 1) {
        printf("FAIL: resolved deficit not counted (got %u)\n",
               report.resolved_mandatory_deficit_count);
        return 1;
    }

    if (report.contributing_semantic_delta_count != 1) {
        printf("FAIL: contributing delta not counted (got %u)\n",
               report.contributing_semantic_delta_count);
        return 1;
    }

    printf("PASS: resolved_mandatory_deficit_counted\n");
    return 0;
}

static int test_new_mandatory_deficit_counted(void) {
    elpis_semantic_requirement_result_v1 prev_results[1], curr_results[1];
    elpis_requirement_result_init(&prev_results[0]);
    elpis_requirement_result_init(&curr_results[0]);

    set_digest(&prev_results[0].requirement_digest, 0xBB);
    set_digest(&curr_results[0].requirement_digest, 0xBB);

    /* Was satisfied, now unsatisfied */
    prev_results[0].satisfaction_status = SAT_STATUS_SATISFIED;
    curr_results[0].satisfaction_status = SAT_STATUS_UNSATISFIED;

    elpis_semantic_context_progress_v1 report;
    int rc = elpis_context_measure_progress(NULL, NULL,
                                             prev_results, 1,
                                             curr_results, 1,
                                             &report);
    if (rc != SEMANTIC_OK) {
        printf("FAIL: new deficit measure failed\n");
        return 1;
    }

    if (report.new_mandatory_deficit_count != 1) {
        printf("FAIL: new deficit not counted (got %u)\n",
               report.new_mandatory_deficit_count);
        return 1;
    }

    printf("PASS: new_mandatory_deficit_counted\n");
    return 0;
}

static int test_unchanged_mandatory_deficit_counted(void) {
    elpis_semantic_requirement_result_v1 prev_results[1], curr_results[1];
    elpis_requirement_result_init(&prev_results[0]);
    elpis_requirement_result_init(&curr_results[0]);

    set_digest(&prev_results[0].requirement_digest, 0xBB);
    set_digest(&curr_results[0].requirement_digest, 0xBB);

    /* Both unsatisfied */
    prev_results[0].satisfaction_status = SAT_STATUS_UNSATISFIED;
    curr_results[0].satisfaction_status = SAT_STATUS_UNSATISFIED;

    elpis_semantic_context_progress_v1 report;
    int rc = elpis_context_measure_progress(NULL, NULL,
                                             prev_results, 1,
                                             curr_results, 1,
                                             &report);
    if (rc != SEMANTIC_OK) {
        printf("FAIL: unchanged deficit measure failed\n");
        return 1;
    }

    if (report.unchanged_mandatory_deficit_count != 1) {
        printf("FAIL: unchanged deficit not counted (got %u)\n",
               report.unchanged_mandatory_deficit_count);
        return 1;
    }

    if (report.contributing_semantic_delta_count != 0) {
        printf("FAIL: unchanged deficit counted as contributing\n");
        return 1;
    }

    printf("PASS: unchanged_mandatory_deficit_counted\n");
    return 0;
}

static int test_identity_deterministic(void) {
    elpis_semantic_context_progress_v1 r1, r2;
    elpis_context_progress_init(&r1);
    elpis_context_progress_init(&r2);

    r1.progress_disposition = PROGRESS_MEASURABLE_PROGRESS;
    r1.resolved_mandatory_deficit_count = 2;
    r2 = r1;

    hacf_digest d1, d2;
    elpis_context_progress_identity(&r1, &d1);
    elpis_context_progress_identity(&r2, &d2);

    if (memcmp(&d1, &d2, HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: progress identity not deterministic\n");
        return 1;
    }

    printf("PASS: identity_deterministic\n");
    return 0;
}

static int test_null_input(void) {
    elpis_semantic_context_progress_v1 report;
    if (elpis_context_measure_progress(NULL, NULL, NULL, 0, NULL, 0, NULL)
        != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL not rejected\n");
        return 1;
    }
    if (elpis_context_progress_validate(NULL) != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL validate not rejected\n");
        return 1;
    }
    printf("PASS: null_input\n");
    return 0;
}

int main(void) {
    int failures = 0;

    failures += test_first_evaluated_round_classified();
    failures += test_identical_typed_view_detected();
    failures += test_identical_view_with_results();
    failures += test_identical_requirement_bundle_detected();
    failures += test_identical_bundle_with_results();
    failures += test_resolved_mandatory_deficit_counted();
    failures += test_new_mandatory_deficit_counted();
    failures += test_unchanged_mandatory_deficit_counted();
    failures += test_identity_deterministic();
    failures += test_null_input();

    if (failures == 0) {
        printf("ALL test_context_progress TESTS PASSED\n");
    } else {
        printf("FAILURES: %d\n", failures);
    }
    return failures;
}
