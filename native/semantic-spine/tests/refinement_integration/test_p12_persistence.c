/* test_p12_persistence.c — Persistence round-trip tests for P12. */
#include "elpis_semantic/refinement_backend.h"
#include "elpis_semantic/identity.h"
#include "elpis_semantic/refinement_backend_registry.h"
#include "elpis_semantic/refinement_integration_policy.h"
#include "elpis_semantic/refinement_integration_request.h"
#include "elpis_semantic/refinement_integration_result.h"
#include "elpis_semantic/refinement_integration_handoff.h"
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

static int tests_passed = 0, tests_failed = 0;
#define CHECK(cond, msg) do { \
    if (cond) { tests_passed++; printf("  PASS: %s\n", msg); } \
    else { tests_failed++; printf("  FAIL: %s\n", msg); } \
} while(0)

int main(void) {
    printf("P12 Persistence Tests\n");

    /* Create temp dir */
    mkdir("test_persist_tmp", 0755);

    char policy_path[256], request_path[256], result_path[256];
    char handoff_path[256], backend_path[256];
    snprintf(policy_path, sizeof(policy_path), "%s", "test_persist_tmp/policy.bin");
    snprintf(request_path, sizeof(request_path), "%s", "test_persist_tmp/request.bin");
    snprintf(result_path, sizeof(result_path), "%s", "test_persist_tmp/result.bin");
    snprintf(handoff_path, sizeof(handoff_path), "%s", "test_persist_tmp/handoff.bin");
    snprintf(backend_path, sizeof(backend_path), "%s", "test_persist_tmp/backend.bin");

    /* Test: policy round-trip */
    elpis_semantic_refinement_integration_policy_v1 policy1, policy2;
    elpis_refinement_integration_policy_init(&policy1);
    policy1.maximum_steps = 16;
    policy1.sidecar_isolation_enforced = 1;
    policy1.reference_isolation_enforced = 1;

    CHECK(elpis_write_refinement_integration_policy(policy_path, &policy1) == SEMANTIC_OK,
          "can write policy");
    CHECK(elpis_read_refinement_integration_policy(policy_path, &policy2) == SEMANTIC_OK,
          "can read policy");
    CHECK(policy1.maximum_steps == policy2.maximum_steps, "policy round-trip: max_steps");

    /* Test: request round-trip */
    elpis_semantic_refinement_integration_request_v1 req1, req2;
    elpis_refinement_integration_request_init(&req1);
    CHECK(elpis_write_refinement_integration_request(request_path, &req1) == SEMANTIC_OK,
          "can write request");
    CHECK(elpis_read_refinement_integration_request(request_path, &req2) == SEMANTIC_OK,
          "can read request");
    CHECK(req1.abi_version == req2.abi_version, "request round-trip: abi_version");

    /* Test: result round-trip */
    elpis_semantic_refinement_integration_result_v1 result1, result2;
    elpis_refinement_integration_result_init(&result1);
    CHECK(elpis_write_refinement_integration_result(result_path, &result1) == SEMANTIC_OK,
          "can write result");
    CHECK(elpis_read_refinement_integration_result(result_path, &result2) == SEMANTIC_OK,
          "can read result");
    CHECK(result1.abi_version == result2.abi_version, "result round-trip: abi_version");

    /* Test: handoff round-trip */
    elpis_semantic_refinement_integration_handoff_v1 handoff1, handoff2;
    elpis_refinement_integration_handoff_init(&handoff1);
    handoff1.runtime_admission = 0;
    handoff1.no_projector_target = 1;
    handoff1.no_residual81 = 1;
    handoff1.no_training = 1;
    handoff1.no_gpu_dependency = 1;
    CHECK(elpis_write_refinement_integration_handoff(handoff_path, &handoff1) == SEMANTIC_OK,
          "can write handoff");
    CHECK(elpis_read_refinement_integration_handoff(handoff_path, &handoff2) == SEMANTIC_OK,
          "can read handoff");
    CHECK(handoff1.runtime_admission == handoff2.runtime_admission,
          "handoff round-trip: runtime_admission");

    /* Test: backend round-trip */
    elpis_semantic_refinement_backend_v1 backend1, backend2;
    elpis_refinement_backend_init(&backend1);
    snprintf(backend1.backend_name, sizeof(backend1.backend_name), "DETERMINISTIC_MRV_SOLVER");
    backend1.status = REFINEMENT_STATUS_ACTIVE_CANONICAL;
    backend1.CPU_execution_supported = 1;
    backend1.deterministic_execution_supported = 1;
    backend1.semantic_sidecar_access = 0;
    backend1.reference_solution_access = 0;
    backend1.training_required = 0;
    CHECK(elpis_write_refinement_backend(backend_path, &backend1) == SEMANTIC_OK,
          "can write backend");
    CHECK(elpis_read_refinement_backend(backend_path, &backend2) == SEMANTIC_OK,
          "can read backend");
    CHECK(strcmp(backend1.backend_name, backend2.backend_name) == 0,
          "backend round-trip: name");

    printf("\nResults: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
