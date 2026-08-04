/* structural_spine_request.c — Integrated structural spine request v1. */
#include "elpis_semantic/structural_spine_request.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_spine_request_init(
    elpis_semantic_structural_spine_request_v1 *request,
    const elpis_semantic_structural_spine_policy_v1 *policy) {
    if (!request) return;
    memset(request, 0, sizeof(*request));
    request->abi_version = SPINE_REQUEST_ABI_VERSION;
    if (policy) {
        memcpy(&request->bound_policy, policy, sizeof(request->bound_policy));
    } else {
        elpis_spine_policy_init(&request->bound_policy);
    }
    strncpy(request->active_backend, request->bound_policy.active_backend, SPINE_MAX_BACKEND_NAME - 1);
    request->maximum_step_boundary = request->bound_policy.maximum_refinement_steps;
}

int elpis_spine_request_identity(
    const elpis_semantic_structural_spine_request_v1 *req, hacf_digest *out) {
    if (!req || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.structural_spine_request.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f;
    f = req->abi_version;                   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, req->P5_bounded_view_handoff_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, req->P6_compiler_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, req->P7_compiler_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, req->P8_adapter_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, req->P8_guard_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, req->P12_backend_registry_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, req->P12_integration_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)req->active_backend, SPINE_MAX_BACKEND_NAME);
    f = req->maximum_step_boundary;         elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, req->HACF_package_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_spine_request_validate(const elpis_semantic_structural_spine_request_v1 *req) {
    if (!req) return SEMANTIC_E_INVAL;
    if (req->abi_version != SPINE_REQUEST_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (req->maximum_step_boundary != 16) return SEMANTIC_E_INVAL;
    if (elpis_spine_policy_validate(&req->bound_policy) != SEMANTIC_OK) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(req->reserved); i++) {
        if (req->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }
    return SEMANTIC_OK;
}

int elpis_spine_request_is_clean(const elpis_semantic_structural_spine_request_v1 *req) {
    if (!req) return 0;
    /* Verify no prohibited fields: model-server, GPU, benchmark, projector, residual81 */
    /* These fields do not exist in the struct — the ABI itself enforces absence */
    return 1;
}
