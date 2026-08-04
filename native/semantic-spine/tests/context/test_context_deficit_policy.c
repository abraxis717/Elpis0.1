/* test_context_deficit_policy.c — Deficit policy validation and identity. */
#include "elpis_semantic/context_deficit_policy.h"
#include "elpis_semantic/identity.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int passed = 0, failed = 0;
#define ASSERT_OK(expr) do { int r = (expr); if (r == SEMANTIC_OK) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #expr); } } while(0)
#define ASSERT_NEQ(expr, v) do { int r = (expr); if (r == (v)) { failed++; fprintf(stderr, "FAIL %s:%d %s == %d\n", __FILE__, __LINE__, #expr, v); } else passed++; } while(0)
#define ASSERT_EQ(a, b) do { if ((a) == (b)) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s != %s\n", __FILE__, __LINE__, #a, #b); } } while(0)
#define ASSERT_DIGEST_EQ(a, b) do { if (memcmp((a)->bytes, (b)->bytes, HACF_DIGEST_BYTES) == 0) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d digests differ\n", __FILE__, __LINE__); } } while(0)

int main(void) {
    /* Test: valid policy */
    {
        elpis_semantic_context_deficit_policy_v1 p;
        elpis_context_deficit_policy_init(&p);
        p.mandatory_failure_behavior = MAND_BEHAVIOR_RETRIEVAL_REQUIRED;
        p.preferred_failure_behavior = PREFERRED_BEHAVIOR_REPORT_ONLY;
        p.diagnostic_failure_behavior = DIAG_BEHAVIOR_REPORT_ONLY;
        p.max_retrieval_requirements = 128;
        p.max_deficits = 256;
        p.deficit_priority_policy = PRIORITY_LEVEL_THEN_TYPE;
        p.retrieval_dedup_policy = DEDUP_EXACT_COLLAPSE;
        p.unsupported_requirement_behavior = UNSUPPORTED_BEHAVIOR_FAIL_CLOSED;
        ASSERT_OK(elpis_context_deficit_policy_validate(&p));
    }

    /* Test: policy identity deterministic */
    {
        elpis_semantic_context_deficit_policy_v1 p;
        elpis_context_deficit_policy_init(&p);
        p.mandatory_failure_behavior = MAND_BEHAVIOR_RETRIEVAL_REQUIRED;
        p.preferred_failure_behavior = PREFERRED_BEHAVIOR_REPORT_ONLY;
        p.diagnostic_failure_behavior = DIAG_BEHAVIOR_REPORT_ONLY;
        p.max_retrieval_requirements = 128;
        p.max_deficits = 256;
        p.deficit_priority_policy = PRIORITY_LEVEL_THEN_TYPE;
        p.retrieval_dedup_policy = DEDUP_EXACT_COLLAPSE;
        p.unsupported_requirement_behavior = UNSUPPORTED_BEHAVIOR_FAIL_CLOSED;
        hacf_digest d1, d2;
        elpis_context_deficit_policy_identity(&p, &d1);
        elpis_context_deficit_policy_identity(&p, &d2);
        ASSERT_DIGEST_EQ(&d1, &d2);
    }

    /* Test: policy identity changes with different preferred behavior */
    {
        elpis_semantic_context_deficit_policy_v1 p1, p2;
        elpis_context_deficit_policy_init(&p1); elpis_context_deficit_policy_init(&p2);
        p1.mandatory_failure_behavior = MAND_BEHAVIOR_RETRIEVAL_REQUIRED;
        p1.preferred_failure_behavior = PREFERRED_BEHAVIOR_REPORT_ONLY;
        p1.diagnostic_failure_behavior = DIAG_BEHAVIOR_REPORT_ONLY;
        p1.max_retrieval_requirements = 128; p1.max_deficits = 256;
        p1.deficit_priority_policy = PRIORITY_LEVEL_THEN_TYPE;
        p1.retrieval_dedup_policy = DEDUP_EXACT_COLLAPSE;
        p1.unsupported_requirement_behavior = UNSUPPORTED_BEHAVIOR_FAIL_CLOSED;
        p2 = p1;
        p2.preferred_failure_behavior = PREFERRED_BEHAVIOR_RETRIEVAL_REQUIRED;
        hacf_digest d1, d2;
        elpis_context_deficit_policy_identity(&p1, &d1);
        elpis_context_deficit_policy_identity(&p2, &d2);
        ASSERT_NEQ(memcmp(d1.bytes, d2.bytes, HACF_DIGEST_BYTES), 0);
    }

    /* Test: nonzero reserved fields rejected */
    {
        elpis_semantic_context_deficit_policy_v1 p;
        elpis_context_deficit_policy_init(&p);
        p.mandatory_failure_behavior = MAND_BEHAVIOR_RETRIEVAL_REQUIRED;
        p.preferred_failure_behavior = PREFERRED_BEHAVIOR_REPORT_ONLY;
        p.diagnostic_failure_behavior = DIAG_BEHAVIOR_REPORT_ONLY;
        p.max_retrieval_requirements = 128; p.max_deficits = 256;
        p.deficit_priority_policy = PRIORITY_LEVEL_THEN_TYPE;
        p.retrieval_dedup_policy = DEDUP_EXACT_COLLAPSE;
        p.unsupported_requirement_behavior = UNSUPPORTED_BEHAVIOR_FAIL_CLOSED;
        p.reserved[0] = 1;
        ASSERT_NEQ(elpis_context_deficit_policy_validate(&p), SEMANTIC_OK);
    }

    /* Test: invalid mandatory behavior rejected */
    {
        elpis_semantic_context_deficit_policy_v1 p;
        elpis_context_deficit_policy_init(&p);
        p.mandatory_failure_behavior = (mandatory_failure_behavior)99;
        p.preferred_failure_behavior = PREFERRED_BEHAVIOR_REPORT_ONLY;
        p.diagnostic_failure_behavior = DIAG_BEHAVIOR_REPORT_ONLY;
        p.max_retrieval_requirements = 128; p.max_deficits = 256;
        ASSERT_NEQ(elpis_context_deficit_policy_validate(&p), SEMANTIC_OK);
    }

    /* Test: invalid preferred behavior rejected */
    {
        elpis_semantic_context_deficit_policy_v1 p;
        elpis_context_deficit_policy_init(&p);
        p.mandatory_failure_behavior = MAND_BEHAVIOR_RETRIEVAL_REQUIRED;
        p.preferred_failure_behavior = (preferred_failure_behavior)99;
        p.diagnostic_failure_behavior = DIAG_BEHAVIOR_REPORT_ONLY;
        p.max_retrieval_requirements = 128; p.max_deficits = 256;
        ASSERT_NEQ(elpis_context_deficit_policy_validate(&p), SEMANTIC_OK);
    }

    printf("Context deficit policy tests: %d passed, %d failed\n", passed, failed);
    return failed > 0 ? 1 : 0;
}
