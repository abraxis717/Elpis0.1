/* structural_spine_result.c — Integrated spine result v1. */
#include "elpis_semantic/structural_spine_result.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_spine_result_init(elpis_semantic_structural_spine_result_v1 *result) {
    if (!result) return;
    memset(result, 0, sizeof(*result));
    result->abi_version = SPINE_RESULT_ABI_VERSION;
    elpis_spine_trace_init(&result->complete_trace);
}

int elpis_spine_result_identity(
    const elpis_semantic_structural_spine_result_v1 *result, hacf_digest *out) {
    if (!result || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.structural_spine_result.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f;
    f = result->abi_version;                elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, result->request_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, result->P6_topology_ir_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, result->P7_structural_packet_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, result->P8_mutability_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, result->P12_integration_result_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, result->initial_structural_state_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, result->final_structural_state_digest.bytes, HACF_DIGEST_BYTES);
    f = result->boundary_receipt_count;     elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < result->boundary_receipt_count; i++) {
        elpis_sha256_update(&ctx, result->boundary_receipt_digests[i].bytes, HACF_DIGEST_BYTES);
    }
    f = result->committed_state_count;      elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < result->committed_state_count; i++) {
        elpis_sha256_update(&ctx, result->committed_state_digests[i].bytes, HACF_DIGEST_BYTES);
    }
    elpis_sha256_update(&ctx, result->final_observation_manifest_digest.bytes, HACF_DIGEST_BYTES);
    f = result->semantic_mutation_count;    elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = result->semantic_relation_invention_count; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = result->semantic_relation_loss_count;  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = result->authority_change_count;     elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = result->fixed_cell_mutation_count;  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = result->unguarded_committed_step_count; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = result->initial_filled_cells;       elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = result->final_filled_cells;         elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = result->backend_invocation_count;   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = result->termination_reason;         elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, result->termination_reason_str, SPINE_MAX_TERMINATION_REASON);
    elpis_sha256_update(&ctx, result->complete_trace_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, result->HACF_package_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_spine_result_validate(const elpis_semantic_structural_spine_result_v1 *result) {
    if (!result) return SEMANTIC_E_INVAL;
    if (result->abi_version != SPINE_RESULT_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (result->boundary_receipt_count > SPINE_RESULT_MAX_RECEIPTS) return SEMANTIC_E_INVAL;
    if (result->committed_state_count > SPINE_RESULT_MAX_COMMITTED) return SEMANTIC_E_INVAL;
    if (elpis_spine_trace_validate(&result->complete_trace) != SEMANTIC_OK) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(result->reserved); i++) {
        if (result->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }
    return SEMANTIC_OK;
}

int elpis_spine_result_is_qualified(const elpis_semantic_structural_spine_result_v1 *result) {
    if (!result) return 0;
    if (result->semantic_mutation_count != 0) return 0;
    if (result->semantic_relation_invention_count != 0) return 0;
    if (result->semantic_relation_loss_count != 0) return 0;
    if (result->authority_change_count != 0) return 0;
    if (result->fixed_cell_mutation_count != 0) return 0;
    if (result->unguarded_committed_step_count != 0) return 0;
    return 1;
}

int elpis_spine_result_add_committed_state(
    elpis_semantic_structural_spine_result_v1 *result,
    const hacf_digest *digest) {
    if (!result || !digest) return SEMANTIC_E_INVAL;
    if (result->committed_state_count >= SPINE_RESULT_MAX_COMMITTED) return SEMANTIC_E_REGISTRY_FULL;
    memcpy(&result->committed_state_digests[result->committed_state_count], digest, sizeof(hacf_digest));
    result->committed_state_count++;
    return SEMANTIC_OK;
}
