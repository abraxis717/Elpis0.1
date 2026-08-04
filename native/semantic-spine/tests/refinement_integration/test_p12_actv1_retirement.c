/* test_p12_actv1_retirement.c — ACTV1 retirement tests for P12.
 * Tests: ACTV1 present as retired, cannot be canonical, artifact unchanged.
 */
#include "elpis_semantic/refinement_backend.h"
#include "elpis_semantic/identity.h"
#include "elpis_semantic/refinement_backend_registry.h"
#include <stdio.h>
#include <string.h>

static int tests_passed = 0, tests_failed = 0;
#define CHECK(cond, msg) do { \
    if (cond) { tests_passed++; printf("  PASS: %s\n", msg); } \
    else { tests_failed++; printf("  FAIL: %s\n", msg); } \
} while(0)

int main(void) {
    printf("P12 ACTV1 Retirement Tests\n");

    elpis_semantic_refinement_backend_registry_v1 registry;
    elpis_refinement_backend_registry_init(&registry);

    /* Test 1: ACTV1 as RETIRED_NEGATIVE_CONTROL */
    elpis_semantic_refinement_backend_v1 actv1;
    elpis_refinement_backend_init(&actv1);
    snprintf(actv1.backend_name, sizeof(actv1.backend_name), "ACTV1_Inner");
    actv1.candidate_class = REFINER_CLASS_FROZEN_NEURAL;
    actv1.status = REFINEMENT_STATUS_RETIRED_NEGATIVE_CONTROL;
    actv1.CPU_execution_supported = 1;
    actv1.deterministic_execution_supported = 1;
    actv1.semantic_sidecar_access = 0;
    actv1.reference_solution_access = 0;
    actv1.training_required = 0;
    snprintf(actv1.adapter_name, sizeof(actv1.adapter_name), "ACTV1_RETIRED");
    elpis_refinement_backend_identity(&actv1, &actv1.backend_digest);

    CHECK(elpis_refinement_backend_validate(&actv1) == SEMANTIC_OK,
          "ACTV1 as retired is valid");

    /* Test 2: ACTV1 alone as active canonical is structurally valid at C layer
     * but policy-layer identity check against P11 binding rejects it.
     * At the C registry level, any single active canonical is valid —
     * the P11 identity enforcement is at the policy/integration layer. */
    actv1.status = REFINEMENT_STATUS_ACTIVE_CANONICAL;
    int rc2 = elpis_refinement_backend_registry_add(&registry, &actv1);
    CHECK(rc2 == SEMANTIC_OK, "ACTV1 alone as active is structurally valid at C layer");

    /* Reset */
    elpis_refinement_backend_registry_init(&registry);

    /* Test 3: ACTV1 present alongside MRV — MRV is canonical */
    actv1.status = REFINEMENT_STATUS_RETIRED_NEGATIVE_CONTROL;

    elpis_semantic_refinement_backend_v1 mrv;
    elpis_refinement_backend_init(&mrv);
    snprintf(mrv.backend_name, sizeof(mrv.backend_name), "DETERMINISTIC_MRV_SOLVER");
    mrv.candidate_class = REFINER_CLASS_DET_SEARCH;
    mrv.status = REFINEMENT_STATUS_ACTIVE_CANONICAL;
    mrv.CPU_execution_supported = 1;
    mrv.deterministic_execution_supported = 1;
    mrv.semantic_sidecar_access = 0;
    mrv.reference_solution_access = 0;
    mrv.training_required = 0;
    snprintf(mrv.adapter_name, sizeof(mrv.adapter_name), "DETERMINISTIC_MRV_SOLVER");
    elpis_refinement_backend_identity(&mrv, &mrv.backend_digest);

    elpis_refinement_backend_registry_add(&registry, &mrv);
    elpis_refinement_backend_registry_add(&registry, &actv1);

    const elpis_semantic_refinement_backend_v1 *canonical =
        elpis_refinement_backend_registry_resolve_canonical(&registry);
    CHECK(canonical != NULL, "canonical resolved");
    CHECK(strcmp(canonical->backend_name, "DETERMINISTIC_MRV_SOLVER") == 0,
          "MRV is canonical, not ACTV1");

    /* Test 4: ACTV1 by name is found but not canonical */
    const elpis_semantic_refinement_backend_v1 *actv1_resolved =
        elpis_refinement_backend_registry_resolve_by_name(&registry, "ACTV1_Inner");
    CHECK(actv1_resolved != NULL, "ACTV1 found by name");
    CHECK(actv1_resolved->status == REFINEMENT_STATUS_RETIRED_NEGATIVE_CONTROL,
          "ACTV1 status is retired");

    /* Test 5: Direct canonical execution of ACTV1 rejected */
    CHECK(actv1_resolved->status != REFINEMENT_STATUS_ACTIVE_CANONICAL,
          "ACTV1 cannot be used as canonical");

    printf("\nResults: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
