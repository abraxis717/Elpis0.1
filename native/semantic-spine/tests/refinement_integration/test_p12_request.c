/* test_p12_request.c — Integration request tests for P12. */
#include "elpis_semantic/refinement_integration_request.h"
#include "elpis_semantic/identity.h"
#include <stdio.h>
#include <string.h>

static int tests_passed = 0, tests_failed = 0;
#define CHECK(cond, msg) do { \
    if (cond) { tests_passed++; printf("  PASS: %s\n", msg); } \
    else { tests_failed++; printf("  FAIL: %s\n", msg); } \
} while(0)

int main(void) {
    printf("P12 Integration Request Tests\n");

    elpis_semantic_refinement_integration_request_v1 req;
    elpis_refinement_integration_request_init(&req);
    CHECK(req.abi_version == REFINEMENT_INTEGRATION_REQUEST_VERSION, "init sets version");

    CHECK(elpis_refinement_integration_request_validate(&req) == SEMANTIC_OK,
          "empty request validates");

    /* Identity determinism */
    hacf_digest d1, d2;
    elpis_refinement_integration_request_identity(&req, &d1);
    elpis_refinement_integration_request_identity(&req, &d2);
    CHECK(memcmp(d1.bytes, d2.bytes, 32) == 0, "identity is deterministic");

    printf("\nResults: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
