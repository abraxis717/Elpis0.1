/* test_p12_registry.c — Backend registry tests for P12.
 * Tests: exactly one active canonical, ACTV1 retired, unknown rejected.
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
    printf("P12 Registry Tests\n");

    /* Test 1: Registry init */
    elpis_semantic_refinement_backend_registry_v1 registry;
    elpis_refinement_backend_registry_init(&registry);
    CHECK(registry.backend_count == 0, "registry starts empty");

    /* Test 2: Zero active backends rejected by validate */
    int rc = elpis_refinement_backend_registry_validate(&registry);
    CHECK(rc != SEMANTIC_OK, "empty registry fails validation");

    /* Test 3: Build MRV backend (ACTIVE_CANONICAL) */
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

    rc = elpis_refinement_backend_registry_add(&registry, &mrv);
    CHECK(rc == SEMANTIC_OK, "can add MRV as ACTIVE_CANONICAL");

    /* Test 4: Exactly one active canonical */
    const elpis_semantic_refinement_backend_v1 *canonical =
        elpis_refinement_backend_registry_resolve_canonical(&registry);
    CHECK(canonical != NULL, "canonical resolved");
    CHECK(strcmp(canonical->backend_name, "DETERMINISTIC_MRV_SOLVER") == 0,
          "canonical is MRV solver");

    /* Test 5: Validate passes with one active */
    rc = elpis_refinement_backend_registry_validate(&registry);
    CHECK(rc == SEMANTIC_OK, "registry with one active canonical validates");

    /* Test 6: ACTV1 as RETIRED_NEGATIVE_CONTROL */
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

    rc = elpis_refinement_backend_registry_add(&registry, &actv1);
    CHECK(rc == SEMANTIC_OK, "can add ACTV1 as RETIRED_NEGATIVE_CONTROL");

    /* Test 7: ACTV1 cannot be resolved as canonical */
    canonical = elpis_refinement_backend_registry_resolve_canonical(&registry);
    CHECK(strcmp(canonical->backend_name, "DETERMINISTIC_MRV_SOLVER") == 0,
          "ACTV1 present but MRV still canonical");

    /* Test 8: Cannot add second active canonical */
    elpis_semantic_refinement_backend_v1 fake_active;
    elpis_refinement_backend_init(&fake_active);
    snprintf(fake_active.backend_name, sizeof(fake_active.backend_name), "FAKE_ACTIVE");
    fake_active.candidate_class = REFINER_CLASS_DET_SEARCH;
    fake_active.status = REFINEMENT_STATUS_ACTIVE_CANONICAL;
    fake_active.CPU_execution_supported = 1;
    fake_active.deterministic_execution_supported = 1;
    fake_active.semantic_sidecar_access = 0;
    fake_active.reference_solution_access = 0;
    fake_active.training_required = 0;
    snprintf(fake_active.adapter_name, sizeof(fake_active.adapter_name), "FAKE");
    elpis_refinement_backend_identity(&fake_active, &fake_active.backend_digest);

    rc = elpis_refinement_backend_registry_add(&registry, &fake_active);
    CHECK(rc != SEMANTIC_OK, "cannot add second ACTIVE_CANONICAL");

    /* Test 9: Unknown backend rejected */
    const elpis_semantic_refinement_backend_v1 *unknown =
        elpis_refinement_backend_registry_resolve_by_name(&registry, "NONEXISTENT");
    CHECK(unknown == NULL, "unknown backend resolves to NULL");

    /* Test 10: Backend with sidecar access is rejected */
    elpis_semantic_refinement_backend_v1 bad_backend;
    elpis_refinement_backend_init(&bad_backend);
    snprintf(bad_backend.backend_name, sizeof(bad_backend.backend_name), "BAD_BACKEND");
    bad_backend.candidate_class = REFINER_CLASS_DET_RULE;
    bad_backend.status = REFINEMENT_STATUS_AVAILABLE_NONCANONICAL;
    bad_backend.CPU_execution_supported = 1;
    bad_backend.deterministic_execution_supported = 1;
    bad_backend.semantic_sidecar_access = 1;  /* BAD */
    bad_backend.reference_solution_access = 0;
    bad_backend.training_required = 0;
    snprintf(bad_backend.adapter_name, sizeof(bad_backend.adapter_name), "BAD");
    rc = elpis_refinement_backend_validate(&bad_backend);
    CHECK(rc != SEMANTIC_OK, "backend with sidecar access fails validation");

    printf("\nResults: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
