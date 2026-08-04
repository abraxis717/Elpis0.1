/* test_p12_handoff.c — Integration handoff tests for P12. */
#include "elpis_semantic/refinement_integration_handoff.h"
#include "elpis_semantic/identity.h"
#include <stdio.h>
#include <string.h>

static int tests_passed = 0, tests_failed = 0;
#define CHECK(cond, msg) do { \
    if (cond) { tests_passed++; printf("  PASS: %s\n", msg); } \
    else { tests_failed++; printf("  FAIL: %s\n", msg); } \
} while(0)

int main(void) {
    printf("P12 Integration Handoff Tests\n");

    elpis_semantic_refinement_integration_handoff_v1 handoff;
    elpis_refinement_integration_handoff_init(&handoff);
    CHECK(handoff.abi_version == REFINEMENT_INTEGRATION_HANDOFF_VERSION, "init sets version");

    /* Runtime admission must be false */
    handoff.runtime_admission = 1;
    CHECK(elpis_refinement_integration_handoff_validate(&handoff) != SEMANTIC_OK,
          "handoff rejects when runtime_admission is true");

    handoff.runtime_admission = 0;
    handoff.no_projector_target = 1;
    handoff.no_residual81 = 1;
    handoff.no_training = 1;
    handoff.no_gpu_dependency = 1;
    handoff.handoff_kind = HANDOFF_CANONICAL_STRUCTURAL_REFINER_INTEGRATED;

    CHECK(elpis_refinement_integration_handoff_validate(&handoff) == SEMANTIC_OK,
          "valid handoff passes validation");

    printf("\nResults: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
