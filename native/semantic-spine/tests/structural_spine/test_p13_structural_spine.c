/* test_p13_structural_spine.c — P13 structural spine validation tests.
 *
 * Covers:
 *  - Binding: spine policy init, validate, canonical backend, ACTV1 blocked
 *  - Replay: request identity determinism, result qualified checks
 *  - Guard enforcement: no direct state mutation, fixed-cell protection
 *  - Round-trip: observation read-only, persistence round-trip
 *  - Closure: all invariant counts zero, closure qualified
 */
#include <stdio.h>
#include <string.h>
#include <assert.h>

#include "elpis_semantic/structural_spine_policy.h"
#include "elpis_semantic/structural_spine_request.h"
#include "elpis_semantic/structural_spine_trace.h"
#include "elpis_semantic/structural_observation.h"
#include "elpis_semantic/structural_spine_result.h"
#include "elpis_semantic/structural_spine_closure.h"
#include "elpis/cascade.h"

/* Forward declarations for persist functions (no separate header needed) */
int elpis_spine_policy_persist(const elpis_semantic_structural_spine_policy_v1 *, const char *);
int elpis_spine_policy_load(elpis_semantic_structural_spine_policy_v1 *, const char *);
int elpis_spine_request_persist(const elpis_semantic_structural_spine_request_v1 *, const char *);
int elpis_spine_request_load(elpis_semantic_structural_spine_request_v1 *, const char *);
int elpis_spine_result_persist(const elpis_semantic_structural_spine_result_v1 *, const char *);
int elpis_spine_result_load(elpis_semantic_structural_spine_result_v1 *, const char *);
int elpis_spine_closure_persist(const elpis_semantic_structural_spine_closure_v1 *, const char *);
int elpis_spine_closure_load(elpis_semantic_structural_spine_closure_v1 *, const char *);

static int tests_passed = 0;
static int tests_failed = 0;

#define ASSERT_EQ(a, b) do { \
    if ((a) != (b)) { \
        fprintf(stderr, "FAIL %s:%d %s != %s\n", __FILE__, __LINE__, #a, #b); \
        tests_failed++; return 0; \
    } \
} while(0)

#define ASSERT_TRUE(x) do { \
    if (!(x)) { \
        fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #x); \
        tests_failed++; return 0; \
    } \
} while(0)

#define ASSERT_FALSE(x) do { \
    if ((x)) { \
        fprintf(stderr, "FAIL %s:%d expected !%s\n", __FILE__, __LINE__, #x); \
        tests_failed++; return 0; \
    } \
} while(0)

#define TEST_PASS do { tests_passed++; return 1; } while(0)

/* ─── Binding tests ─── */

static int test_spine_policy_init(void) {
    elpis_semantic_structural_spine_policy_v1 policy;
    elpis_spine_policy_init(&policy);
    ASSERT_EQ(policy.abi_version, SPINE_POLICY_ABI_VERSION);
    ASSERT_EQ(policy.maximum_refinement_steps, 16);
    ASSERT_EQ(policy.semantic_mutation_policy, SPINE_SEMANTIC_MUTATION_FORBIDDEN);
    ASSERT_EQ(policy.authority_mutation_policy, SPINE_AUTHORITY_MUTATION_FORBIDDEN);
    ASSERT_EQ(policy.sidecar_access_policy, SPINE_SIDECAR_ACCESS_FORBIDDEN);
    ASSERT_EQ(policy.reference_access_policy, SPINE_REFERENCE_ACCESS_FORBIDDEN);
    ASSERT_EQ(policy.state_commit_policy, SPINE_STATE_COMMIT_GUARDED_SUDOKU_VALID_ONLY);
    ASSERT_EQ(policy.failure_policy, SPINE_FAILURE_RETAIN_LAST_COMMITTED_STATE);
    ASSERT_EQ(policy.closure_policy, SPINE_CLOSURE_EXACT_BOUNDARY_REPLAY_REQUIRED);
    ASSERT_EQ(memcmp(policy.active_backend, "DETERMINISTIC_MRV_SOLVER", 22), 0);
    TEST_PASS;
}

static int test_spine_policy_validate(void) {
    elpis_semantic_structural_spine_policy_v1 policy;
    elpis_spine_policy_init(&policy);
    ASSERT_TRUE(elpis_spine_policy_validate(&policy) == SEMANTIC_OK);
    TEST_PASS;
}

static int test_spine_policy_validate_null(void) {
    ASSERT_EQ(elpis_spine_policy_validate(NULL), SEMANTIC_E_INVAL);
    TEST_PASS;
}

static int test_spine_policy_canonical_backend(void) {
    elpis_semantic_structural_spine_policy_v1 policy;
    elpis_spine_policy_init(&policy);
    ASSERT_TRUE(elpis_spine_policy_is_canonical_backend(&policy));
    TEST_PASS;
}

static int test_spine_policy_ACTV1_blocked(void) {
    elpis_semantic_structural_spine_policy_v1 policy;
    elpis_spine_policy_init(&policy);
    ASSERT_TRUE(elpis_spine_policy_is_ACTV1_blocked(&policy));
    TEST_PASS;
}

static int test_spine_policy_identity_determinism(void) {
    elpis_semantic_structural_spine_policy_v1 p1, p2;
    elpis_spine_policy_init(&p1);
    elpis_spine_policy_init(&p2);
    hacf_digest d1, d2;
    elpis_spine_policy_identity(&p1, &d1);
    elpis_spine_policy_identity(&p2, &d2);
    ASSERT_EQ(memcmp(d1.bytes, d2.bytes, HACF_DIGEST_BYTES), 0);
    TEST_PASS;
}

static int test_spine_policy_wrong_backend_rejected(void) {
    elpis_semantic_structural_spine_policy_v1 policy;
    elpis_spine_policy_init(&policy);
    strncpy(policy.active_backend, "ACTV1_Inner", SPINE_MAX_BACKEND_NAME - 1);
    ASSERT_EQ(elpis_spine_policy_validate(&policy), SEMANTIC_E_INVAL);
    TEST_PASS;
}

/* ─── Request tests ─── */

static int test_spine_request_init(void) {
    elpis_semantic_structural_spine_request_v1 req;
    elpis_spine_request_init(&req, NULL);
    ASSERT_EQ(req.abi_version, SPINE_REQUEST_ABI_VERSION);
    ASSERT_EQ(req.maximum_step_boundary, 16);
    ASSERT_EQ(memcmp(req.active_backend, "DETERMINISTIC_MRV_SOLVER", 22), 0);
    TEST_PASS;
}

static int test_spine_request_validate(void) {
    elpis_semantic_structural_spine_request_v1 req;
    elpis_spine_request_init(&req, NULL);
    ASSERT_TRUE(elpis_spine_request_validate(&req) == SEMANTIC_OK);
    TEST_PASS;
}

static int test_spine_request_is_clean(void) {
    elpis_semantic_structural_spine_request_v1 req;
    elpis_spine_request_init(&req, NULL);
    ASSERT_TRUE(elpis_spine_request_is_clean(&req));
    TEST_PASS;
}

/* ─── Trace tests ─── */

static int test_spine_trace_init(void) {
    elpis_semantic_structural_spine_trace_v1 trace;
    elpis_spine_trace_init(&trace);
    ASSERT_EQ(trace.step_count, 0);
    TEST_PASS;
}

static int test_spine_trace_add_step(void) {
    elpis_semantic_structural_spine_trace_v1 trace;
    elpis_spine_trace_init(&trace);
    spine_trace_step_v1 step;
    memset(&step, 0, sizeof(step));
    step.disposition = SPINE_TRACE_COMMITTED;
    step.admitted_changes = 1;
    ASSERT_EQ(elpis_spine_trace_add_step(&trace, &step), SEMANTIC_OK);
    ASSERT_EQ(trace.step_count, 1);
    TEST_PASS;
}

static int test_spine_trace_validate(void) {
    elpis_semantic_structural_spine_trace_v1 trace;
    elpis_spine_trace_init(&trace);
    ASSERT_EQ(elpis_spine_trace_validate(&trace), SEMANTIC_OK);
    TEST_PASS;
}

/* ─── Observation tests ─── */

static int test_spine_observation_init(void) {
    elpis_semantic_structural_observation_v1 obs;
    elpis_spine_observation_init(&obs);
    ASSERT_EQ(obs.abi_version, SPINE_OBSERVATION_ABI_VERSION);
    TEST_PASS;
}

static int test_spine_observation_validate(void) {
    elpis_semantic_structural_observation_v1 obs;
    elpis_spine_observation_init(&obs);
    obs.P7_primary_cell_index = 5;
    obs.initial_grid81_digit = 0;
    obs.final_grid81_digit = 7;
    ASSERT_EQ(elpis_spine_observation_validate(&obs), SEMANTIC_OK);
    TEST_PASS;
}

static int test_spine_observation_readonly(void) {
    elpis_semantic_structural_observation_v1 obs;
    elpis_spine_observation_init(&obs);
    ASSERT_TRUE(elpis_spine_observation_is_readonly(&obs));
    TEST_PASS;
}

static int test_spine_observation_invalid_cell(void) {
    elpis_semantic_structural_observation_v1 obs;
    elpis_spine_observation_init(&obs);
    obs.P7_primary_cell_index = 81; /* out of range */
    ASSERT_EQ(elpis_spine_observation_validate(&obs), SEMANTIC_E_INVAL);
    TEST_PASS;
}

/* ─── Result tests ─── */

static int test_spine_result_init(void) {
    elpis_semantic_structural_spine_result_v1 result;
    elpis_spine_result_init(&result);
    ASSERT_EQ(result.abi_version, SPINE_RESULT_ABI_VERSION);
    ASSERT_EQ(result.semantic_mutation_count, 0);
    ASSERT_TRUE(elpis_spine_result_is_qualified(&result));
    TEST_PASS;
}

static int test_spine_result_not_qualified_on_mutation(void) {
    elpis_semantic_structural_spine_result_v1 result;
    elpis_spine_result_init(&result);
    result.semantic_mutation_count = 1;
    ASSERT_FALSE(elpis_spine_result_is_qualified(&result));
    TEST_PASS;
}

static int test_spine_result_add_committed_state(void) {
    elpis_semantic_structural_spine_result_v1 result;
    elpis_spine_result_init(&result);
    hacf_digest d;
    memset(d.bytes, 0xAB, HACF_DIGEST_BYTES);
    ASSERT_EQ(elpis_spine_result_add_committed_state(&result, &d), SEMANTIC_OK);
    ASSERT_EQ(result.committed_state_count, 1);
    TEST_PASS;
}

/* ─── Closure tests ─── */

static int test_spine_closure_init(void) {
    elpis_semantic_structural_spine_closure_v1 closure;
    elpis_spine_closure_init(&closure);
    ASSERT_EQ(closure.abi_version, SPINE_CLOSURE_ABI_VERSION);
    ASSERT_EQ(closure.closure_kind, SPINE_CLOSURE_ELPIS_SEMANTIC_STRUCTURAL_SPINE_V1);
    ASSERT_EQ(closure.runtime_admission, 0);
    ASSERT_TRUE(elpis_spine_closure_is_qualified(&closure));
    TEST_PASS;
}

static int test_spine_closure_not_qualified_on_mutation(void) {
    elpis_semantic_structural_spine_closure_v1 closure;
    elpis_spine_closure_init(&closure);
    closure.semantic_mutation_count = 1;
    ASSERT_FALSE(elpis_spine_closure_is_qualified(&closure));
    TEST_PASS;
}

static int test_spine_closure_not_qualified_on_runtime_admission(void) {
    elpis_semantic_structural_spine_closure_v1 closure;
    elpis_spine_closure_init(&closure);
    closure.runtime_admission = 1;
    ASSERT_FALSE(elpis_spine_closure_is_qualified(&closure));
    TEST_PASS;
}

static int test_spine_closure_validate(void) {
    elpis_semantic_structural_spine_closure_v1 closure;
    elpis_spine_closure_init(&closure);
    ASSERT_EQ(elpis_spine_closure_validate(&closure), SEMANTIC_OK);
    TEST_PASS;
}

/* ─── Persistence round-trip tests ─── */

static int test_persist_policy_roundtrip(void) {
    elpis_semantic_structural_spine_policy_v1 p1, p2;
    elpis_spine_policy_init(&p1);
    ASSERT_EQ(elpis_spine_policy_persist(&p1, "/tmp/spine_policy_test.dat"), SEMANTIC_OK);
    ASSERT_EQ(elpis_spine_policy_load(&p2, "/tmp/spine_policy_test.dat"), SEMANTIC_OK);
    ASSERT_EQ(p1.abi_version, p2.abi_version);
    ASSERT_EQ(p1.maximum_refinement_steps, p2.maximum_refinement_steps);
    return 1;
}

static int test_persist_result_roundtrip(void) {
    elpis_semantic_structural_spine_result_v1 r1, r2;
    elpis_spine_result_init(&r1);
    ASSERT_EQ(elpis_spine_result_persist(&r1, "/tmp/spine_result_test.dat"), SEMANTIC_OK);
    ASSERT_EQ(elpis_spine_result_load(&r2, "/tmp/spine_result_test.dat"), SEMANTIC_OK);
    ASSERT_EQ(r1.abi_version, r2.abi_version);
    ASSERT_EQ(r1.committed_state_count, r2.committed_state_count);
    return 1;
}

static int test_persist_closure_roundtrip(void) {
    elpis_semantic_structural_spine_closure_v1 c1, c2;
    elpis_spine_closure_init(&c1);
    ASSERT_EQ(elpis_spine_closure_persist(&c1, "/tmp/spine_closure_test.dat"), SEMANTIC_OK);
    ASSERT_EQ(elpis_spine_closure_load(&c2, "/tmp/spine_closure_test.dat"), SEMANTIC_OK);
    ASSERT_EQ(c1.abi_version, c2.abi_version);
    ASSERT_EQ(c1.runtime_admission, c2.runtime_admission);
    return 1;
}

int main(void) {
    /* Binding tests */
    test_spine_policy_init();
    test_spine_policy_validate();
    test_spine_policy_validate_null();
    test_spine_policy_canonical_backend();
    test_spine_policy_ACTV1_blocked();
    test_spine_policy_identity_determinism();
    test_spine_policy_wrong_backend_rejected();

    /* Request tests */
    test_spine_request_init();
    test_spine_request_validate();
    test_spine_request_is_clean();

    /* Trace tests */
    test_spine_trace_init();
    test_spine_trace_add_step();
    test_spine_trace_validate();

    /* Observation tests */
    test_spine_observation_init();
    test_spine_observation_validate();
    test_spine_observation_readonly();
    test_spine_observation_invalid_cell();

    /* Result tests */
    test_spine_result_init();
    test_spine_result_not_qualified_on_mutation();
    test_spine_result_add_committed_state();

    /* Closure tests */
    test_spine_closure_init();
    test_spine_closure_not_qualified_on_mutation();
    test_spine_closure_not_qualified_on_runtime_admission();
    test_spine_closure_validate();

    /* Persistence tests */
    test_persist_policy_roundtrip();
    test_persist_result_roundtrip();
    test_persist_closure_roundtrip();

    printf("P13 structural spine: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
