/* structural_spine_closure.c — Structural spine closure v1. */
#include "elpis_semantic/structural_spine_closure.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_spine_closure_init(elpis_semantic_structural_spine_closure_v1 *closure) {
    if (!closure) return;
    memset(closure, 0, sizeof(*closure));
    closure->abi_version = SPINE_CLOSURE_ABI_VERSION;
    closure->closure_kind = SPINE_CLOSURE_ELPIS_SEMANTIC_STRUCTURAL_SPINE_V1;
    closure->runtime_admission = 0;
}

int elpis_spine_closure_identity(
    const elpis_semantic_structural_spine_closure_v1 *closure, hacf_digest *out) {
    if (!closure || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.structural_spine_closure.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f;
    f = closure->abi_version;               elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = closure->closure_kind;              elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, closure->P5_root_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->P6_topology_ir_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->P7_structural_packet_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->P8_mutability_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->P12_integration_handoff_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->spine_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->integrated_request_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->integrated_result_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->production_replay_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->sidecar_roundtrip_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->invariant_receipt_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->P10_regression_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->determinism_receipt_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->sanitizer_receipt_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, closure->nonregression_receipt_digest.bytes, HACF_DIGEST_BYTES);
    f = closure->semantic_mutation_count;   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = closure->semantic_relation_invention_count; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = closure->semantic_relation_loss_count; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = closure->authority_change_count;    elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = closure->fixed_cell_mutation_count; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = closure->unguarded_commit_count;    elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, (const uint8_t *)&closure->runtime_admission, 4);
    f = closure->closure_disposition;       elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, closure->HACF_package_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_spine_closure_validate(const elpis_semantic_structural_spine_closure_v1 *closure) {
    if (!closure) return SEMANTIC_E_INVAL;
    if (closure->abi_version != SPINE_CLOSURE_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (closure->closure_kind != SPINE_CLOSURE_ELPIS_SEMANTIC_STRUCTURAL_SPINE_V1) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(closure->reserved); i++) {
        if (closure->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }
    return SEMANTIC_OK;
}

int elpis_spine_closure_is_qualified(const elpis_semantic_structural_spine_closure_v1 *closure) {
    if (!closure) return 0;
    if (closure->semantic_mutation_count != 0) return 0;
    if (closure->semantic_relation_invention_count != 0) return 0;
    if (closure->semantic_relation_loss_count != 0) return 0;
    if (closure->authority_change_count != 0) return 0;
    if (closure->fixed_cell_mutation_count != 0) return 0;
    if (closure->unguarded_commit_count != 0) return 0;
    if (closure->runtime_admission != 0) return 0;
    return 1;
}
