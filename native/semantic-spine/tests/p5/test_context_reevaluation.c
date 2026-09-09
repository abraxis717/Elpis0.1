/* test_context_reevaluation.c — P5 context reevaluation tests */
#include "elpis_semantic/context_reevaluation.h"
#include "elpis_semantic/context_progress.h"
#include "elpis_semantic/context_iteration_state.h"
#include "elpis_semantic/context_iteration_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis_semantic/context_rebind.h"
#include "elpis_semantic/context_requirement_set.h"
#include "elpis_semantic/context_requirement.h"
#include "elpis_semantic/context_deficit_report.h"
#include "elpis_semantic/context_deficit_policy.h"
#include "elpis_semantic/typed_evidence_view.h"
#include "elpis_semantic/embedding_collection.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <stdlib.h>

static void set_digest(hacf_digest *d, uint32_t seed) {
    memset(d, 0, HACF_DIGEST_BYTES);
    d->bytes[0] = (uint8_t)(seed & 0xFF);
    d->bytes[1] = (uint8_t)((seed >> 8) & 0xFF);
    d->bytes[2] = (uint8_t)((seed >> 16) & 0xFF);
    d->bytes[3] = (uint8_t)((seed >> 24) & 0xFF);
}

static int test_null_input_rejected(void) {
    elpis_semantic_context_reevaluation_v1 receipt;
    elpis_semantic_context_rebind_v1 rebind;
    elpis_semantic_context_requirement_set_v1 rset;
    elpis_semantic_context_deficit_policy_v1 policy;
    elpis_typed_evidence_view_v1 tv;

    elpis_context_rebind_init(&rebind);
    elpis_context_requirement_set_init(&rset);
    elpis_context_deficit_policy_init(&policy);
    elpis_typed_evidence_view_init(&tv);

    /* NULL typed view */
    if (elpis_context_reevaluate(NULL, &rebind, &rset, &policy, NULL, &receipt)
        != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL typed view not rejected\n");
        return 1;
    }

    /* NULL receipt */
    if (elpis_context_reevaluate(&tv, &rebind, &rset, &policy, NULL, NULL)
        != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL receipt not rejected\n");
        return 1;
    }

    printf("PASS: null_input_rejected\n");
    return 0;
}

static void make_valid_deficit_policy(
    elpis_semantic_context_deficit_policy_v1 *policy) {
    elpis_context_deficit_policy_init(policy);
    policy->mandatory_failure_behavior = MAND_BEHAVIOR_RETRIEVAL_REQUIRED;
    policy->preferred_failure_behavior = PREFERRED_BEHAVIOR_REPORT_ONLY;
    policy->diagnostic_failure_behavior = DIAG_BEHAVIOR_REPORT_ONLY;
    policy->max_retrieval_requirements = 8;
    policy->max_deficits = 8;
    policy->deficit_priority_policy = PRIORITY_LEVEL_THEN_TYPE;
    policy->retrieval_dedup_policy = DEDUP_EXACT_COLLAPSE;
    policy->unsupported_requirement_behavior = UNSUPPORTED_BEHAVIOR_FAIL_CLOSED;
    elpis_context_deficit_policy_identity(policy, &policy->policy_identity);
}

static int test_report_consumption_and_exact_binding(void) {
    elpis_typed_evidence_view_v1 tv;
    elpis_typed_evidence_view_init(&tv);
    set_digest(&tv.base_snapshot_digest, 0x101);
    set_digest(&tv.query_overlay_digest, 0x102);
    set_digest(&tv.retrieval_expansion_digest, 0x103);
    set_digest(&tv.admission_layer_digest, 0x104);
    elpis_typed_evidence_view_identity(&tv, &tv.typed_evidence_view_digest);

    elpis_semantic_context_requirement_v1 requirement;
    elpis_context_requirement_init(&requirement);
    requirement.requirement_type = TYPE_EXPLICIT_EXTERNAL_CONTEXT;
    requirement.requirement_level = MANDATORY;
    requirement.target_object_kind = KIND_GLOBAL;
    context_external_context_ext ext;
    memset(&ext, 0, sizeof(ext));
    ext.external_context_class = 1;
    memcpy(requirement.extension_bytes, &ext, sizeof(ext));
    requirement.extension_size = sizeof(ext);
    elpis_context_requirement_identity(
        &requirement, &requirement.requirement_identity);

    elpis_semantic_context_requirement_set_v1 orig;
    elpis_context_requirement_set_init(&orig);
    set_digest(&orig.target_query_overlay_digest, 0x201);
    set_digest(&orig.target_composed_view_digest, 0x202);
    elpis_context_requirement_set_add(&orig, &requirement.requirement_identity);
    set_digest(&orig.requirement_set_policy_digest, 0x204);
    elpis_context_requirement_set_identity(&orig, &orig.requirement_set_identity);

    elpis_semantic_context_rebind_v1 rebind;
    if (elpis_context_rebind_requirement_set(
            &orig, &tv.query_overlay_digest, &tv.typed_evidence_view_digest,
            &rebind) != SEMANTIC_OK) {
        printf("FAIL: setup rebind failed\n");
        return 1;
    }

    elpis_semantic_context_requirement_set_v1 rebound;
    if (elpis_context_rebind_construct_set(&rebind, &rebound) != SEMANTIC_OK) {
        printf("FAIL: setup rebound set failed\n");
        return 1;
    }

    elpis_semantic_context_deficit_policy_v1 policy;
    make_valid_deficit_policy(&policy);

    elpis_semantic_requirement_result_v1 result;
    elpis_requirement_result_init(&result);
    result.requirement_digest = rebound.requirement_digests[0];
    result.evaluation_status = EVAL_STATUS_EVALUATED;
    result.satisfaction_status = SAT_STATUS_SATISFIED;
    elpis_requirement_result_diagnostic(&result, &result.diagnostic_digest);

    elpis_semantic_context_deficit_report_v1 *report = NULL;
    if (elpis_context_deficit_report_build(
            &tv.typed_evidence_view_digest, NULL, 0, &rebound,
            &requirement, 1, &policy, &result, 1, &report) != SEMANTIC_OK || !report) {
        printf("FAIL: report build failed\n");
        return 1;
    }

    elpis_semantic_context_reevaluation_v1 receipt;
    int rc = elpis_context_reevaluate(
        &tv, &rebind, &rebound, &policy, report, &receipt);
    if (rc != SEMANTIC_OK) {
        printf("FAIL: exact report binding rejected: %d\n", rc);
        free(report);
        return 1;
    }
    if (receipt.P2_report_disposition != report->overall_disposition ||
        memcmp(&receipt.P2_deficit_report_digest, &report->report_identity,
               HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: report disposition/identity not preserved\n");
        free(report);
        return 1;
    }

    report->composed_view_digest.bytes[0] ^= 0x01u;
    elpis_context_deficit_report_identity(report, &report->report_identity);
    rc = elpis_context_reevaluate(
        &tv, &rebind, &rebound, &policy, report, &receipt);
    free(report);
    if (rc == SEMANTIC_OK) {
        printf("FAIL: mismatched P2 report view binding accepted\n");
        return 1;
    }

    printf("PASS: report_consumption_and_exact_binding\n");
    return 0;
}

static int test_disposition_preservation(void) {
    /* Test that each P2 disposition maps to the correct outcome */
    elpis_semantic_context_iteration_policy_v1 policy;
    elpis_context_iteration_policy_default(&policy);

    elpis_semantic_context_iteration_state_v1 state;
    elpis_context_iteration_state_init(&state);
    state.round_index = 1;

    /* CONTEXT_SUFFICIENT → bounded view ready */
    int outcome = elpis_context_iteration_outcome_adjudicate(
        &state, DISP_CONTEXT_SUFFICIENT, PROGRESS_FIRST_EVALUATED_ROUND, &policy);
    if (outcome != (int)OUTCOME_CONTEXT_SUFFICIENT_AND_BOUNDED_VIEW_READY) {
        printf("FAIL: CONTEXT_SUFFICIENT did not produce BOUNDED_VIEW_READY (got %d)\n", outcome);
        return 1;
    }

    /* RETRIEVAL_REQUIRED + progress → continuation */
    outcome = elpis_context_iteration_outcome_adjudicate(
        &state, DISP_RETRIEVAL_REQUIRED, PROGRESS_MEASURABLE_PROGRESS, &policy);
    if (outcome != (int)OUTCOME_RETRIEVAL_CONTINUATION_REQUIRED) {
        printf("FAIL: RETRIEVAL_REQUIRED+progress not continuation (got %d)\n", outcome);
        return 1;
    }

    /* REQUIREMENT_SET_INVALID → invalid */
    outcome = elpis_context_iteration_outcome_adjudicate(
        &state, DISP_REQUIREMENT_SET_INVALID, PROGRESS_FIRST_EVALUATED_ROUND, &policy);
    if (outcome != (int)OUTCOME_CONTEXT_REQUIREMENT_SET_INVALID) {
        printf("FAIL: REQUIREMENT_SET_INVALID not blocked (got %d)\n", outcome);
        return 1;
    }

    /* EVALUATION_BLOCKED → blocked */
    outcome = elpis_context_iteration_outcome_adjudicate(
        &state, DISP_EVALUATION_BLOCKED, PROGRESS_FIRST_EVALUATED_ROUND, &policy);
    if (outcome != (int)OUTCOME_CONTEXT_REEVALUATION_BLOCKED) {
        printf("FAIL: EVALUATION_BLOCKED not blocked (got %d)\n", outcome);
        return 1;
    }

    printf("PASS: disposition_preservation\n");
    return 0;
}

static int test_retrieval_bundle_only_when_required(void) {
    elpis_semantic_context_iteration_policy_v1 policy;
    elpis_context_iteration_policy_default(&policy);

    elpis_semantic_context_iteration_state_v1 state;
    elpis_context_iteration_state_init(&state);
    state.round_index = 1;

    /* CONTEXT_SUFFICIENT — no retrieval bundle needed */
    int outcome = elpis_context_iteration_outcome_adjudicate(
        &state, DISP_CONTEXT_SUFFICIENT, PROGRESS_FIRST_EVALUATED_ROUND, &policy);
    if (outcome != (int)OUTCOME_CONTEXT_SUFFICIENT_AND_BOUNDED_VIEW_READY) {
        printf("FAIL: sufficient did not produce bounded view ready\n");
        return 1;
    }

    /* RETRIEVAL_REQUIRED — continuation with bundle */
    outcome = elpis_context_iteration_outcome_adjudicate(
        &state, DISP_RETRIEVAL_REQUIRED, PROGRESS_MEASURABLE_PROGRESS, &policy);
    if (outcome != (int)OUTCOME_RETRIEVAL_CONTINUATION_REQUIRED) {
        printf("FAIL: retrieval required not continuation\n");
        return 1;
    }

    printf("PASS: retrieval_bundle_only_when_required\n");
    return 0;
}

static int test_error_never_becomes_sufficient(void) {
    elpis_semantic_context_iteration_policy_v1 policy;
    elpis_context_iteration_policy_default(&policy);

    elpis_semantic_context_iteration_state_v1 state;
    elpis_context_iteration_state_init(&state);
    state.round_index = 1;

    /* EVALUATION_BLOCKED must never produce sufficient */
    int outcome = elpis_context_iteration_outcome_adjudicate(
        &state, DISP_EVALUATION_BLOCKED, PROGRESS_MEASURABLE_PROGRESS, &policy);
    if (outcome == (int)OUTCOME_CONTEXT_SUFFICIENT_AND_BOUNDED_VIEW_READY) {
        printf("FAIL: EVALUATION_BLOCKED became sufficient\n");
        return 1;
    }

    /* REQUIREMENT_SET_INVALID must never become sufficient */
    outcome = elpis_context_iteration_outcome_adjudicate(
        &state, DISP_REQUIREMENT_SET_INVALID, PROGRESS_MEASURABLE_PROGRESS, &policy);
    if (outcome == (int)OUTCOME_CONTEXT_SUFFICIENT_AND_BOUNDED_VIEW_READY) {
        printf("FAIL: REQUIREMENT_SET_INVALID became sufficient\n");
        return 1;
    }

    printf("PASS: error_never_becomes_sufficient\n");
    return 0;
}

static int test_reevaluation_init_sets_abi(void) {
    elpis_semantic_context_reevaluation_v1 receipt;
    elpis_context_reevaluation_init(&receipt);

    if (receipt.abi_version != CONTEXT_REEVALUATION_ABI_VERSION) {
        printf("FAIL: init did not set abi_version\n");
        return 1;
    }

    /* All fields zero except abi_version */
    if (receipt.P2_report_disposition != 0) {
        printf("FAIL: init left P2 disposition nonzero\n");
        return 1;
    }

    printf("PASS: reevaluation_init_sets_abi\n");
    return 0;
}

static int test_identity_deterministic(void) {
    elpis_semantic_context_reevaluation_v1 r1, r2;
    elpis_context_reevaluation_init(&r1);
    elpis_context_reevaluation_init(&r2);

    set_digest(&r1.typed_evidence_view_digest, 0x11);
    set_digest(&r1.rebind_receipt_digest, 0x22);
    r1.P2_report_disposition = DISP_CONTEXT_SUFFICIENT;

    r2 = r1;

    hacf_digest d1, d2;
    elpis_context_reevaluation_identity(&r1, &d1);
    elpis_context_reevaluation_identity(&r2, &d2);

    if (memcmp(&d1, &d2, HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: identity not deterministic\n");
        return 1;
    }

    printf("PASS: identity_deterministic\n");
    return 0;
}

int main(void) {
    int failures = 0;

    failures += test_null_input_rejected();
    failures += test_report_consumption_and_exact_binding();
    failures += test_disposition_preservation();
    failures += test_retrieval_bundle_only_when_required();
    failures += test_error_never_becomes_sufficient();
    failures += test_reevaluation_init_sets_abi();
    failures += test_identity_deterministic();

    if (failures == 0) {
        printf("ALL test_context_reevaluation TESTS PASSED\n");
    } else {
        printf("FAILURES: %d\n", failures);
    }
    return failures;
}
