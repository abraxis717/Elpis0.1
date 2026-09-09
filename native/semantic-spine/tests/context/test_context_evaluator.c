/* test_context_evaluator.c — explicit requirement binding and disposition rules. */
#include "elpis_semantic/context_deficit.h"
#include "elpis_semantic/context_deficit_report.h"
#include "elpis_semantic/context_requirement.h"
#include "elpis_semantic/context_requirement_set.h"
#include "elpis_semantic/context_deficit_policy.h"
#include <stdio.h>
#include <string.h>

static int passed = 0, failed = 0;
#define ASSERT_OK(expr) do { int r = (expr); if (r == SEMANTIC_OK) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s rc=%d\n", __FILE__, __LINE__, #expr, r); } } while(0)
#define ASSERT_EQ(a, b) do { if ((a) == (b)) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s != %s\n", __FILE__, __LINE__, #a, #b); } } while(0)
#define ASSERT_NEQ(a, b) do { if ((a) != (b)) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s == %s\n", __FILE__, __LINE__, #a, #b); } } while(0)

static void make_policy(elpis_semantic_context_deficit_policy_v1 *policy,
                        uint32_t preferred_behavior) {
    elpis_context_deficit_policy_init(policy);
    policy->mandatory_failure_behavior = MAND_BEHAVIOR_RETRIEVAL_REQUIRED;
    policy->preferred_failure_behavior = preferred_behavior;
    policy->diagnostic_failure_behavior = DIAG_BEHAVIOR_REPORT_ONLY;
    policy->max_retrieval_requirements = 128;
    policy->max_deficits = 256;
    policy->deficit_priority_policy = PRIORITY_LEVEL_THEN_TYPE;
    policy->retrieval_dedup_policy = DEDUP_EXACT_COLLAPSE;
    policy->unsupported_requirement_behavior = UNSUPPORTED_BEHAVIOR_FAIL_CLOSED;
    elpis_context_deficit_policy_identity(policy, &policy->policy_identity);
}

static void make_requirement(elpis_semantic_context_requirement_v1 *req,
                             uint32_t level, uint8_t tag) {
    elpis_context_requirement_init(req);
    req->requirement_type = TYPE_EXPLICIT_EXTERNAL_CONTEXT;
    req->requirement_level = (semantic_requirement_level)level;
    req->target_object_kind = KIND_GLOBAL;
    memset(req->target_object_digest.bytes, tag, HACF_DIGEST_BYTES);
    memset(req->requirement_policy_digest.bytes, (uint8_t)(tag + 1u), HACF_DIGEST_BYTES);

    context_external_context_ext ext;
    memset(&ext, 0, sizeof(ext));
    ext.external_context_class = tag;
    memcpy(req->extension_bytes, &ext, sizeof(ext));
    req->extension_size = sizeof(ext);

    elpis_context_requirement_identity(req, &req->requirement_identity);
}

static void sort_requirements(elpis_semantic_context_requirement_v1 *reqs,
                              uint32_t count) {
    for (uint32_t i = 1; i < count; ++i) {
        elpis_semantic_context_requirement_v1 key = reqs[i];
        uint32_t j = i;
        while (j > 0 &&
               memcmp(key.requirement_identity.bytes,
                      reqs[j - 1].requirement_identity.bytes,
                      HACF_DIGEST_BYTES) < 0) {
            reqs[j] = reqs[j - 1];
            --j;
        }
        reqs[j] = key;
    }
}

static void make_set_and_requirements(
    elpis_semantic_context_requirement_set_v1 *set,
    elpis_semantic_context_requirement_v1 reqs[3]) {
    make_requirement(&reqs[0], MANDATORY, 0x11);
    make_requirement(&reqs[1], PREFERRED, 0x22);
    make_requirement(&reqs[2], DIAGNOSTIC, 0x33);
    sort_requirements(reqs, 3);

    elpis_context_requirement_set_init(set);
    memset(set->target_query_overlay_digest.bytes, 0xAA, HACF_DIGEST_BYTES);
    memset(set->target_composed_view_digest.bytes, 0xBB, HACF_DIGEST_BYTES);
    memset(set->requirement_set_policy_digest.bytes, 0xCC, HACF_DIGEST_BYTES);
    for (uint32_t i = 0; i < 3; ++i)
        elpis_context_requirement_set_add(set, &reqs[i].requirement_identity);
    elpis_context_requirement_set_identity(set, &set->requirement_set_identity);
}

static int index_for_level(
    const elpis_semantic_context_requirement_v1 reqs[3], uint32_t level) {
    for (int i = 0; i < 3; ++i)
        if ((uint32_t)reqs[i].requirement_level == level) return i;
    return -1;
}

static void make_results(
    const elpis_semantic_context_requirement_v1 reqs[3],
    elpis_semantic_requirement_result_v1 results[3]) {
    for (uint32_t i = 0; i < 3; ++i) {
        elpis_requirement_result_init(&results[i]);
        results[i].requirement_digest = reqs[i].requirement_identity;
        results[i].evaluation_status = EVAL_STATUS_EVALUATED;
        results[i].satisfaction_status = SAT_STATUS_SATISFIED;
        elpis_requirement_result_diagnostic(&results[i], &results[i].diagnostic_digest);
    }
}

int main(void) {
    elpis_semantic_context_requirement_set_v1 set;
    elpis_semantic_context_requirement_v1 reqs[3];
    make_set_and_requirements(&set, reqs);

    ASSERT_OK(elpis_context_requirement_objects_validate_binding(&set, reqs, 3));

    {
        elpis_semantic_context_requirement_v1 tampered[3];
        memcpy(tampered, reqs, sizeof(tampered));
        tampered[1].minimum_authority ^= 1u;
        ASSERT_NEQ(elpis_context_requirement_objects_validate_binding(&set, tampered, 3),
                   SEMANTIC_OK);
        ASSERT_NEQ(elpis_context_requirement_objects_validate_binding(&set, reqs, 2),
                   SEMANTIC_OK);
    }

    elpis_semantic_context_deficit_policy_v1 policy;
    make_policy(&policy, PREFERRED_BEHAVIOR_REPORT_ONLY);

    {
        elpis_semantic_requirement_result_v1 results[3];
        make_results(reqs, results);
        uint32_t disp = 0;
        ASSERT_OK(elpis_context_deficit_report_disposition(
            results, 3, &set, reqs, 3, &policy, &disp));
        ASSERT_EQ(disp, DISP_CONTEXT_SUFFICIENT);
    }

    {
        elpis_semantic_requirement_result_v1 results[3];
        make_results(reqs, results);
        int idx = index_for_level(reqs, MANDATORY);
        results[idx].satisfaction_status = SAT_STATUS_UNSATISFIED;
        uint32_t disp = 0;
        ASSERT_OK(elpis_context_deficit_report_disposition(
            results, 3, &set, reqs, 3, &policy, &disp));
        ASSERT_EQ(disp, DISP_RETRIEVAL_REQUIRED);
    }

    {
        elpis_semantic_requirement_result_v1 results[3];
        make_results(reqs, results);
        int idx = index_for_level(reqs, PREFERRED);
        results[idx].satisfaction_status = SAT_STATUS_UNSATISFIED;
        uint32_t disp = 0;
        ASSERT_OK(elpis_context_deficit_report_disposition(
            results, 3, &set, reqs, 3, &policy, &disp));
        ASSERT_EQ(disp, DISP_CONTEXT_SUFFICIENT);

        make_policy(&policy, PREFERRED_BEHAVIOR_RETRIEVAL_REQUIRED);
        ASSERT_OK(elpis_context_deficit_report_disposition(
            results, 3, &set, reqs, 3, &policy, &disp));
        ASSERT_EQ(disp, DISP_RETRIEVAL_REQUIRED);
        make_policy(&policy, PREFERRED_BEHAVIOR_REPORT_ONLY);
    }

    {
        elpis_semantic_requirement_result_v1 results[3];
        make_results(reqs, results);
        int idx = index_for_level(reqs, DIAGNOSTIC);
        results[idx].satisfaction_status = SAT_STATUS_UNSATISFIED;
        uint32_t disp = 0;
        ASSERT_OK(elpis_context_deficit_report_disposition(
            results, 3, &set, reqs, 3, &policy, &disp));
        ASSERT_EQ(disp, DISP_CONTEXT_SUFFICIENT);
    }

    {
        elpis_semantic_requirement_result_v1 results[3];
        make_results(reqs, results);
        results[0].evaluation_status = EVAL_STATUS_BLOCKED_UNSUPPORTED;
        results[0].satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        uint32_t disp = 0;
        ASSERT_OK(elpis_context_deficit_report_disposition(
            results, 3, &set, reqs, 3, &policy, &disp));
        ASSERT_EQ(disp, DISP_EVALUATION_BLOCKED);
    }

    {
        elpis_semantic_requirement_result_v1 results[3];
        make_results(reqs, results);
        uint32_t sat, mand, pref, diag, blocked;
        ASSERT_OK(elpis_count_deficits(
            results, 3, &set, reqs, 3,
            &sat, &mand, &pref, &diag, &blocked));
        ASSERT_EQ(sat, 3u);
        ASSERT_EQ(mand, 0u);
        ASSERT_EQ(pref, 0u);
        ASSERT_EQ(diag, 0u);
        ASSERT_EQ(blocked, 0u);
    }

    {
        elpis_semantic_requirement_result_v1 results[1];
        memset(results, 0, sizeof(results));
        uint32_t disp = 0;
        ASSERT_OK(elpis_context_deficit_report_disposition(
            results, 0, &set, NULL, 0, &policy, &disp));
        ASSERT_EQ(disp, DISP_EVALUATION_BLOCKED);
    }

    {
        elpis_semantic_context_deficit_report_v1 report;
        elpis_context_deficit_report_init(&report);
        ASSERT_EQ(report.abi_version, CONTEXT_DEFICIT_REPORT_ABI_VERSION);
        report.result_count = 1;
        report.satisfied_count = 1;
        memset(report.composed_view_digest.bytes, 0x11, HACF_DIGEST_BYTES);
        memset(report.requirement_set_digest.bytes, 0x22, HACF_DIGEST_BYTES);
        memset(report.deficit_policy_digest.bytes, 0x33, HACF_DIGEST_BYTES);
        hacf_digest d1, d2;
        elpis_context_deficit_report_identity(&report, &d1);
        elpis_context_deficit_report_identity(&report, &d2);
        ASSERT_EQ(memcmp(d1.bytes, d2.bytes, HACF_DIGEST_BYTES), 0);
    }

    printf("Context explicit-requirement evaluator/disposition tests: %d passed, %d failed\n",
           passed, failed);
    return failed > 0 ? 1 : 0;
}
