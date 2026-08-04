/* test_p11_refiner.c — P11 refinement engine bakeoff unit tests.
 *
 * Tests: candidate identity, adapter conformance, execution transaction,
 *        metrics validation, selection ranking, handoff integrity.
 */
#include "elpis_semantic/refiner_candidate.h"
#include "elpis_semantic/refiner_adapter.h"
#include "elpis_semantic/refiner_execution.h"
#include "elpis_semantic/refiner_metrics.h"
#include "elpis_semantic/refiner_selection.h"
#include "elpis_semantic/refiner_handoff.h"
#include "elpis_semantic/refiner_bakeoff_policy.h"

#include <stdio.h>
#include <string.h>
#include <assert.h>

static int tests_run = 0;
static int tests_pass = 0;

static const uint8_t zeroes[64] = {0};

#define TEST(name, expr) do { \
    tests_run++; \
    if (!(expr)) { \
        fprintf(stderr, "FAIL: %s at line %d\n", name, __LINE__); \
    } else { \
        tests_pass++; \
    } \
} while(0)

/* ── Candidate identity ── */
static void test_candidate_init(void) {
    elpis_semantic_refiner_candidate_v1 c;
    elpis_refiner_candidate_init(&c);
    TEST("candidate_init_abi", c.abi_version == REFINER_CANDIDATE_VERSION);
    TEST("candidate_init_zero_name", c.candidate_name[0] == '\0');
    TEST("candidate_init_zero_reserved", memcmp(c.reserved, (uint8_t[64]){0}, 64) == 0);
}

static void test_candidate_identity_deterministic(void) {
    elpis_semantic_refiner_candidate_v1 c1, c2;
    elpis_refiner_candidate_init(&c1);
    elpis_refiner_candidate_init(&c2);

    strcpy(c1.candidate_name, "TEST_CANDIDATE");
    strcpy(c2.candidate_name, "TEST_CANDIDATE");
    c1.candidate_class = REFINER_CLASS_DET_RULE;
    c2.candidate_class = REFINER_CLASS_DET_RULE;

    hacf_digest d1, d2;
    elpis_refiner_candidate_identity(&c1, &d1);
    elpis_refiner_candidate_identity(&c2, &d2);
    TEST("candidate_identity_same", memcmp(d1.bytes, d2.bytes, 32) == 0);

    c2.candidate_class = REFINER_CLASS_DET_SEARCH;
    elpis_refiner_candidate_identity(&c2, &d2);
    TEST("candidate_identity_diff_class", memcmp(d1.bytes, d2.bytes, 32) != 0);
}

static void test_candidate_validate(void) {
    elpis_semantic_refiner_candidate_v1 c;
    elpis_refiner_candidate_init(&c);
    TEST("candidate_validate_ok", elpis_refiner_candidate_validate(&c) == SEMANTIC_OK);

    c.abi_version = 999;
    TEST("candidate_validate_bad_abi", elpis_refiner_candidate_validate(&c) != SEMANTIC_OK);

    c.abi_version = REFINER_CANDIDATE_VERSION;
    c.candidate_class = 999;
    TEST("candidate_validate_bad_class", elpis_refiner_candidate_validate(&c) != SEMANTIC_OK);
}

/* ── Adapter conformance ── */
static void test_adapter_init(void) {
    elpis_semantic_refiner_adapter_v1 a;
    elpis_refiner_adapter_init(&a);
    TEST("adapter_init_abi", a.abi_version == REFINER_ADAPTER_VERSION);
    TEST("adapter_init_zero_reserved", memcmp(a.reserved, (uint8_t[64]){0}, 64) == 0);
}

static void test_adapter_validate(void) {
    elpis_semantic_refiner_adapter_v1 a;
    elpis_refiner_adapter_init(&a);
    TEST("adapter_validate_no_name", elpis_refiner_adapter_validate(&a) != SEMANTIC_OK);

    strcpy(a.adapter_name, "test_adapter");
    a.execute = NULL;
    TEST("adapter_validate_no_fn", elpis_refiner_adapter_validate(&a) != SEMANTIC_OK);
}

/* ── Execution transaction ── */
static void test_execution_init(void) {
    elpis_semantic_refiner_execution_v1 e;
    elpis_refiner_execution_init(&e);
    TEST("execution_init_abi", e.abi_version == REFINER_EXECUTION_VERSION);
    TEST("execution_init_zero_reserved", memcmp(e.reserved, (uint8_t[64]){0}, 64) == 0);
    TEST("execution_init_zero_steps", e.execution_steps == 0);
}

static void test_execution_validate(void) {
    elpis_semantic_refiner_execution_v1 e;
    elpis_refiner_execution_init(&e);
    TEST("execution_validate_ok", elpis_refiner_execution_validate(&e) == SEMANTIC_OK);

    e.abi_version = 999;
    TEST("execution_validate_bad_abi", elpis_refiner_execution_validate(&e) != SEMANTIC_OK);
}

/* ── Metrics ── */
static void test_metrics_init(void) {
    elpis_semantic_refiner_metrics_v1 m;
    elpis_refiner_metrics_init(&m);
    TEST("metrics_init_abi", m.abi_version == REFINER_METRICS_VERSION);
    TEST("metrics_init_zero_fixtures", m.positive_bounded_fixtures == 0);
    TEST("metrics_init_zero_reserved", memcmp(m.reserved, (uint8_t[64]){0}, 64) == 0);
}

static void test_metrics_validate(void) {
    elpis_semantic_refiner_metrics_v1 m;
    elpis_refiner_metrics_init(&m);
    TEST("metrics_validate_ok", elpis_refiner_metrics_validate(&m) == SEMANTIC_OK);

    m.abi_version = 999;
    TEST("metrics_validate_bad_abi", elpis_refiner_metrics_validate(&m) != SEMANTIC_OK);

    m.abi_version = REFINER_METRICS_VERSION;
    m.positive_bounded_fixtures = 17;
    TEST("metrics_validate_too_many_fixtures", elpis_refiner_metrics_validate(&m) != SEMANTIC_OK);
}

/* ── Selection ── */
static void test_selection_init(void) {
    elpis_semantic_refiner_selection_v1 s;
    elpis_refiner_selection_init(&s);
    TEST("selection_init_abi", s.abi_version == REFINER_SELECTION_VERSION);
    TEST("selection_init_zero_count", s.qualified_count == 0);
    TEST("selection_init_zero_reserved", memcmp(s.reserved, (uint8_t[64]){0}, 64) == 0);
}

static void test_selection_validate(void) {
    elpis_semantic_refiner_selection_v1 s;
    elpis_refiner_selection_init(&s);
    TEST("selection_validate_ok", elpis_refiner_selection_validate(&s) == SEMANTIC_OK);

    s.abi_version = 999;
    TEST("selection_validate_bad_abi", elpis_refiner_selection_validate(&s) != SEMANTIC_OK);

    s.abi_version = REFINER_SELECTION_VERSION;
    s.selection_valid = 1;
    s.ranking_count = 0;
    TEST("selection_validate_no_ranking", elpis_refiner_selection_validate(&s) != SEMANTIC_OK);
}

/* ── Handoff ── */
static void test_handoff_init(void) {
    elpis_semantic_refiner_handoff_v1 h;
    elpis_refiner_handoff_init(&h);
    TEST("handoff_init_abi", h.abi_version == REFINER_HANDOFF_VERSION);
    TEST("handoff_init_zero_reserved", memcmp(h.reserved, (uint8_t[64]){0}, 64) == 0);
}

static void test_handoff_validate(void) {
    elpis_semantic_refiner_handoff_v1 h;
    elpis_refiner_handoff_init(&h);
    TEST("handoff_validate_ok", elpis_refiner_handoff_validate(&h) == SEMANTIC_OK);

    h.abi_version = 999;
    TEST("handoff_validate_bad_abi", elpis_refiner_handoff_validate(&h) != SEMANTIC_OK);
}

/* ── Bakeoff policy ── */
static void test_policy_init(void) {
    elpis_semantic_refiner_bakeoff_policy_v1 p;
    elpis_refiner_bakeoff_policy_init(&p);
    TEST("policy_init_abi", p.abi_version == REFINER_BAKEOFF_POLICY_VERSION);
    TEST("policy_init_timeout", p.timeout_seconds == REFINER_DEFAULT_TIMEOUT_SECONDS);
    TEST("policy_init_zero_reserved", memcmp(p.reserved, (uint8_t[64]){0}, 64) == 0);
}

static void test_policy_validate(void) {
    elpis_semantic_refiner_bakeoff_policy_v1 p;
    elpis_refiner_bakeoff_policy_init(&p);
    TEST("policy_validate_ok", elpis_refiner_bakeoff_policy_validate(&p) == SEMANTIC_OK);

    p.abi_version = 999;
    TEST("policy_validate_bad_abi", elpis_refiner_bakeoff_policy_validate(&p) != SEMANTIC_OK);
}

/* ── ACTV1 retirement ── */
static void test_actv1_retired_class(void) {
    elpis_semantic_refiner_candidate_v1 c;
    elpis_refiner_candidate_init(&c);
    c.candidate_class = REFINER_CLASS_FROZEN_NEURAL;
    c.eligibility_disposition = REFINER_RETIRED_NEGATIVE_CONTROL;
    TEST("actv1_retired_disposition", elpis_refiner_candidate_validate(&c) == SEMANTIC_OK);
}

int main(void) {
    printf("P11 refiner tests\n");

    test_candidate_init();
    test_candidate_identity_deterministic();
    test_candidate_validate();

    test_adapter_init();
    test_adapter_validate();

    test_execution_init();
    test_execution_validate();

    test_metrics_init();
    test_metrics_validate();

    test_selection_init();
    test_selection_validate();

    test_handoff_init();
    test_handoff_validate();

    test_policy_init();
    test_policy_validate();

    test_actv1_retired_class();

    printf("  %d/%d tests passed\n", tests_pass, tests_run);
    return tests_pass == tests_run ? 0 : 1;
}
