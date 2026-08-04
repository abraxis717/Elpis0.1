/* grid81_packet.c — Grid81 structural packet v1. */
#include "elpis_semantic/grid81_structural_packet.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

void elpis_grid81_structural_packet_init(
    elpis_semantic_grid81_structural_packet_v1 *packet) {
    if (!packet) return;
    memset(packet, 0, sizeof(*packet));
    packet->abi_version = GRID81_STRUCTURAL_PACKET_ABI_VERSION;
}

int elpis_grid81_structural_packet_identity(
    const elpis_semantic_grid81_structural_packet_v1 *packet, hacf_digest *out) {
    if (!packet || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.grid81.structural_packet.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f;
    f = packet->abi_version;                elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, packet->P6_topology_handoff_digest.bytes, 32);
    elpis_sha256_update(&ctx, packet->P6_topology_IR_digest.bytes, 32);
    elpis_sha256_update(&ctx, packet->P6_compile_receipt_digest.bytes, 32);
    elpis_sha256_update(&ctx, packet->grid81_policy_digest.bytes, 32);
    elpis_sha256_update(&ctx, packet->grid81_codebook_digest.bytes, 32);
    elpis_sha256_update(&ctx, packet->sudoku_template_digest.bytes, 32);
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        f = packet->grid81_digits[i];       elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    }
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        f = packet->occupied_mask81[i];     elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    }
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        f = packet->compiler_writable_mask81[i]; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    }
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        for (uint32_t j = 0; j < GRID81_DIGIT_CLASS_COUNT; j++) {
            f = packet->grid81_digit_classes[i][j]; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
        }
    }
    elpis_sha256_update(&ctx, packet->capsule_manifest_digest.bytes, 32);
    elpis_sha256_update(&ctx, packet->trace_sidecar_digest.bytes, 32);
    elpis_sha256_update(&ctx, packet->digit_array_digest.bytes, 32);
    elpis_sha256_update(&ctx, packet->digit_class_tensor_digest.bytes, 32);
    elpis_sha256_update(&ctx, packet->occupied_mask_digest.bytes, 32);
    elpis_sha256_update(&ctx, packet->writable_mask_digest.bytes, 32);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_grid81_structural_packet_validate(
    const elpis_semantic_grid81_structural_packet_v1 *packet) {
    if (!packet) return SEMANTIC_E_INVAL;
    if (packet->abi_version != GRID81_STRUCTURAL_PACKET_ABI_VERSION) return SEMANTIC_E_INVAL;
    /* Digits 0-9 */
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        if (packet->grid81_digits[i] > 9u) return SEMANTIC_E_INVAL;
        if (packet->occupied_mask81[i] > 1u) return SEMANTIC_E_INVAL;
        if (packet->compiler_writable_mask81[i] != 0u) return SEMANTIC_E_INVAL;
    }
    /* Digit-class tensor: binary, one active class per cell */
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        uint32_t active_count = 0;
        for (uint32_t j = 0; j < GRID81_DIGIT_CLASS_COUNT; j++) {
            if (packet->grid81_digit_classes[i][j] > 1u) return SEMANTIC_E_INVAL;
            if (packet->grid81_digit_classes[i][j] == 1u) active_count++;
        }
        if (active_count != 1u) return SEMANTIC_E_INVAL;
        /* argmax must equal digit */
        uint32_t active_class = packet->grid81_digits[i];
        if (packet->grid81_digit_classes[i][active_class] != 1u) return SEMANTIC_E_INVAL;
    }
    /* Occupied mask agrees with digit nonzero */
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        uint32_t expected = (packet->grid81_digits[i] > 0) ? 1u : 0u;
        if (packet->occupied_mask81[i] != expected) return SEMANTIC_E_INVAL;
    }
    /* Sudoku constraints on partial board */
    for (uint32_t r = 0; r < 9; r++) {
        uint8_t seen[10] = {0};
        for (uint32_t c = 0; c < 9; c++) {
            uint32_t d = packet->grid81_digits[r * 9u + c];
            if (d > 0 && d <= 9) {
                if (seen[d]) return SEMANTIC_E_INVAL;
                seen[d] = 1;
            }
        }
    }
    for (size_t i = 0; i < sizeof(packet->reserved); i++) {
        if (packet->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_grid81_structural_packet(const char *path,
    const elpis_semantic_grid81_structural_packet_v1 *packet) {
    if (!path || !packet) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, packet, sizeof(*packet));
    if ((size_t)w != sizeof(*packet)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd); close(fd);
    return SEMANTIC_OK;
}

int elpis_read_grid81_structural_packet(const char *path,
    elpis_semantic_grid81_structural_packet_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    close(fd);
    if ((size_t)r != sizeof(*out)) return SEMANTIC_E_IO;
    return SEMANTIC_OK;
}
