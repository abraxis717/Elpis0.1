/* grid81_handoff.c — P8 TRM adapter handoff ABI v1. */
#include "elpis_semantic/grid81_handoff.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

void elpis_grid81_handoff_init(elpis_semantic_grid81_handoff_v1 *handoff) {
    if (!handoff) return;
    memset(handoff, 0, sizeof(*handoff));
    handoff->abi_version = GRID81_HANDOFF_ABI_VERSION;
    handoff->handoff_kind = GRID81_TO_TRM_ADAPTER_INPUT;
    /* P8 boundary flags */
    handoff->digits_are_sudoku_structural = 1;
    handoff->writable_mask_is_compiler_fixed = 1;
    handoff->P8_may_derive_nonzero_writable = 1;
    handoff->P8_may_adapt_digit_classes = 1;
    handoff->P8_may_not_change_relation_id = 1;
    handoff->P8_may_not_change_authority = 1;
    handoff->P8_may_not_discard_conflict = 1;
    handoff->P8_may_not_use_adjacency_as_proof = 1;
    handoff->P8_may_not_invent_residual81 = 1;
    handoff->P8_needs_separate_projector_qual = 1;
}

int elpis_grid81_handoff_identity(
    const elpis_semantic_grid81_handoff_v1 *handoff, hacf_digest *out) {
    if (!handoff || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.grid81_handoff.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f;
    f = handoff->abi_version;              elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = handoff->handoff_kind;             elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, handoff->root_query_overlay_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->P6_topology_handoff_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->P7_structural_packet_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->P7_compile_receipt_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->grid81_policy_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->grid81_codebook_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->sudoku_template_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->digit_array_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->digit_class_tensor_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->occupied_mask_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->compiler_writable_mask_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->capsule_manifest_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->trace_sidecar_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->constraint_projection_manifest_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->type_registry_chain_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->authority_registry_digest.bytes, 32);
    elpis_sha256_update(&ctx, handoff->handoff_policy_digest.bytes, 32);
    f = handoff->digits_are_sudoku_structural;      elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = handoff->writable_mask_is_compiler_fixed;   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = handoff->P8_may_derive_nonzero_writable;    elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = handoff->P8_may_adapt_digit_classes;        elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = handoff->P8_may_not_change_relation_id;     elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = handoff->P8_may_not_change_authority;       elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = handoff->P8_may_not_discard_conflict;       elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = handoff->P8_may_not_use_adjacency_as_proof; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = handoff->P8_may_not_invent_residual81;      elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = handoff->P8_needs_separate_projector_qual;  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_grid81_handoff_validate(
    const elpis_semantic_grid81_handoff_v1 *handoff) {
    if (!handoff) return SEMANTIC_E_INVAL;
    if (handoff->abi_version != GRID81_HANDOFF_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (handoff->handoff_kind != GRID81_TO_TRM_ADAPTER_INPUT) return SEMANTIC_E_INVAL;
    /* All P8 boundary flags must be set */
    if (!handoff->digits_are_sudoku_structural) return SEMANTIC_E_INVAL;
    if (!handoff->writable_mask_is_compiler_fixed) return SEMANTIC_E_INVAL;
    if (!handoff->P8_may_not_change_relation_id) return SEMANTIC_E_INVAL;
    if (!handoff->P8_may_not_change_authority) return SEMANTIC_E_INVAL;
    if (!handoff->P8_may_not_discard_conflict) return SEMANTIC_E_INVAL;
    if (!handoff->P8_may_not_use_adjacency_as_proof) return SEMANTIC_E_INVAL;
    if (!handoff->P8_may_not_invent_residual81) return SEMANTIC_E_INVAL;
    if (!handoff->P8_needs_separate_projector_qual) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(handoff->reserved); i++) {
        if (handoff->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_grid81_handoff(const char *path,
    const elpis_semantic_grid81_handoff_v1 *handoff) {
    if (!path || !handoff) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, handoff, sizeof(*handoff));
    if ((size_t)w != sizeof(*handoff)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd); close(fd);
    return SEMANTIC_OK;
}

int elpis_read_grid81_handoff(const char *path,
    elpis_semantic_grid81_handoff_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    close(fd);
    if ((size_t)r != sizeof(*out)) return SEMANTIC_E_IO;
    return SEMANTIC_OK;
}
