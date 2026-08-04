/* grid81_compile_receipt.c — Compilation receipt v1. */
#include "elpis_semantic/grid81_compile_receipt.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

void elpis_grid81_compile_receipt_init(
    elpis_semantic_grid81_compile_receipt_v1 *receipt) {
    if (!receipt) return;
    memset(receipt, 0, sizeof(*receipt));
    receipt->abi_version = GRID81_COMPILE_RECEIPT_ABI_VERSION;
}

int elpis_grid81_compile_receipt_identity(
    const elpis_semantic_grid81_compile_receipt_v1 *receipt, hacf_digest *out) {
    if (!receipt || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.grid81_compile_receipt.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f;
    f = receipt->abi_version;              elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, receipt->P6_handoff_digest.bytes, 32);
    elpis_sha256_update(&ctx, receipt->P6_topology_IR_digest.bytes, 32);
    elpis_sha256_update(&ctx, receipt->grid81_policy_digest.bytes, 32);
    elpis_sha256_update(&ctx, receipt->grid81_codebook_digest.bytes, 32);
    elpis_sha256_update(&ctx, receipt->sudoku_template_digest.bytes, 32);
    f = receipt->input_topology_vertex_count;     elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = receipt->input_topology_incidence_count;  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = receipt->input_constraint_count;          elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = receipt->capsule_count;                   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = receipt->occupied_cell_count;             elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = receipt->empty_cell_count;                elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = receipt->packed_collision_count;          elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = receipt->projected_constraint_count;      elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = receipt->unmapped_vertex_count;           elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = receipt->untraceable_incidence_count;     elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = receipt->unprojected_constraint_count;    elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = receipt->semantic_relation_invention_count; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = receipt->semantic_relation_loss_count;    elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = receipt->authority_change_count;          elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, receipt->structural_packet_digest.bytes, 32);
    elpis_sha256_update(&ctx, receipt->compiler_trace_digest.bytes, 32);
    f = receipt->compile_disposition;             elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_grid81_compile_receipt_validate(
    const elpis_semantic_grid81_compile_receipt_v1 *receipt) {
    if (!receipt) return SEMANTIC_E_INVAL;
    if (receipt->abi_version != GRID81_COMPILE_RECEIPT_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (receipt->compile_disposition > GRID81_COMPILE_BLOCKED_INTERNAL) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(receipt->reserved); i++) {
        if (receipt->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_grid81_compile_receipt_is_qualified(
    const elpis_semantic_grid81_compile_receipt_v1 *receipt) {
    if (!receipt) return SEMANTIC_E_INVAL;
    if (receipt->compile_disposition != GRID81_COMPILE_COMPLETE) return SEMANTIC_E_INVAL;
    if (receipt->unmapped_vertex_count != 0) return SEMANTIC_E_INVAL;
    if (receipt->untraceable_incidence_count != 0) return SEMANTIC_E_INVAL;
    if (receipt->unprojected_constraint_count != 0) return SEMANTIC_E_INVAL;
    if (receipt->semantic_relation_invention_count != 0) return SEMANTIC_E_INVAL;
    if (receipt->semantic_relation_loss_count != 0) return SEMANTIC_E_INVAL;
    if (receipt->authority_change_count != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_write_grid81_compile_receipt(const char *path,
    const elpis_semantic_grid81_compile_receipt_v1 *receipt) {
    if (!path || !receipt) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, receipt, sizeof(*receipt));
    if ((size_t)w != sizeof(*receipt)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd); close(fd);
    return SEMANTIC_OK;
}

int elpis_read_grid81_compile_receipt(const char *path,
    elpis_semantic_grid81_compile_receipt_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    close(fd);
    if ((size_t)r != sizeof(*out)) return SEMANTIC_E_IO;
    return SEMANTIC_OK;
}
