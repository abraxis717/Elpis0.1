/* test_p12_result.c — Integration result tests for P12. */
#include "elpis_semantic/refinement_integration_result.h"
#include "elpis_semantic/refinement_integration_request.h"
#include "elpis_semantic/refinement_integration_policy.h"
#include "elpis_semantic/refinement_integration_receipt.h"
#include "elpis_semantic/identity.h"
#include <stdio.h>
#include <string.h>

int elpis_integration_build_receipt(
    const elpis_semantic_refinement_integration_request_v1 *request,
    const elpis_semantic_refinement_integration_policy_v1 *policy,
    const elpis_semantic_refinement_integration_result_v1 *result,
    elpis_semantic_refinement_integration_receipt_v1 *receipt);

static void set_digest(hacf_digest *d, uint8_t v) {
    memset(d, v, sizeof(*d));
}

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

    elpis_semantic_refinement_integration_request_v1 req;
    elpis_semantic_refinement_integration_policy_v1 pol;
    elpis_semantic_refinement_integration_result_v1 bound_result;
    elpis_semantic_refinement_integration_receipt_v1 receipt;
    elpis_refinement_integration_request_init(&req);
    elpis_refinement_integration_policy_init(&pol);
    elpis_refinement_integration_result_init(&bound_result);

    pol.maximum_steps = 16;
    pol.sidecar_isolation_enforced = 1;
    pol.reference_isolation_enforced = 1;
    set_digest(&pol.backend_registry_digest, 0x11);
    set_digest(&pol.active_backend_digest, 0x22);
    set_digest(&pol.active_adapter_digest, 0x33);
    elpis_refinement_integration_policy_identity(&pol, &pol.integration_policy_digest);

    req.backend_registry_digest = pol.backend_registry_digest;
    req.active_backend_digest = pol.active_backend_digest;
    req.active_adapter_digest = pol.active_adapter_digest;
    req.integration_policy_digest = pol.integration_policy_digest;
    elpis_refinement_integration_request_identity(&req, &req.request_digest);

    bound_result.integration_request_digest = req.request_digest;
    bound_result.backend_registry_digest = req.backend_registry_digest;
    bound_result.active_backend_digest = req.active_backend_digest;
    bound_result.active_adapter_digest = req.active_adapter_digest;
    bound_result.integration_policy_digest = pol.integration_policy_digest;
    bound_result.all_sudoku_valid = 1;
    bound_result.fixed_clues_unchanged = 1;
    elpis_refinement_integration_result_identity(
        &bound_result, &bound_result.integration_result_digest);

    CHECK(elpis_integration_build_receipt(&req, &pol, &bound_result, &receipt) == SEMANTIC_OK,
          "receipt accepts exact request-policy-result binding");
    CHECK(memcmp(receipt.adapter_digest.bytes, req.active_adapter_digest.bytes, 32) == 0,
          "receipt binds active adapter");

    elpis_semantic_refinement_integration_request_v1 wrong_req = req;
    wrong_req.P7_structural_packet_digest.bytes[0] ^= 0x01u;
    elpis_refinement_integration_request_identity(&wrong_req, &wrong_req.request_digest);
    CHECK(elpis_integration_build_receipt(&wrong_req, &pol, &bound_result, &receipt) != SEMANTIC_OK,
          "receipt rejects mismatched request/result binding");

    printf("\nResults: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
