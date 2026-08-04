/* test_p12_result.c — Integration result tests for P12. */
#include "elpis_semantic/refinement_integration_result.h"
#include "elpis_semantic/identity.h"
#include <stdio.h>
#include <string.h>

static int tests_passed = 0, tests_failed = 0;
#define CHECK(cond, msg) do { \
    if (cond) { tests_passed++; printf("  PASS: %s\n", msg); } \
    else { tests_failed++; printf("  FAIL: %s\n", msg); } \
} while(0)

int main(void) {
    printf("P12 Integration Result Tests\n");

    elpis_semantic_refinement_integration_result_v1 result;
    elpis_refinement_integration_result_init(&result);
    CHECK(result.abi_version == REFINEMENT_INTEGRATION_RESULT_VERSION, "init sets version");

    CHECK(elpis_refinement_integration_result_validate(&result) == SEMANTIC_OK,
          "empty result validates");

    /* Invalid termination reason */
    result.termination_reason = 99;
    CHECK(elpis_refinement_integration_result_validate(&result) != SEMANTIC_OK,
          "invalid termination reason rejected");

    result.termination_reason = INTEGRATION_TERMINATION_QUIESCENT_NO_CHANGE;
    CHECK(elpis_refinement_integration_result_validate(&result) == SEMANTIC_OK,
          "valid termination reason passes");

    /* Too many steps */
    result.step_count = REFINEMENT_MAX_STEPS + 1;
    CHECK(elpis_refinement_integration_result_validate(&result) != SEMANTIC_OK,
          "too many steps rejected");

    result.step_count = 16;
    CHECK(elpis_refinement_integration_result_validate(&result) == SEMANTIC_OK,
          "max steps passes");

    printf("\nResults: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
