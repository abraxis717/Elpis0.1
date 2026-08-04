/* grid81_cell.c — Grid81 cell records v1. */
#include "elpis_semantic/grid81_cell.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

void elpis_grid81_cell_init(elpis_semantic_grid81_cell_v1 *cell) {
    if (!cell) return;
    memset(cell, 0, sizeof(*cell));
    cell->abi_version = GRID81_CELL_ABI_VERSION;
}

void elpis_grid81_cells_init(elpis_semantic_grid81_cells_v1 *cells) {
    if (!cells) return;
    memset(cells, 0, sizeof(*cells));
    cells->abi_version = GRID81_CELL_ABI_VERSION;
}

void elpis_grid81_masks_init(elpis_semantic_grid81_masks_v1 *masks) {
    if (!masks) return;
    memset(masks, 0, sizeof(*masks));
}

int elpis_grid81_cell_identity(
    const elpis_semantic_grid81_cell_v1 *cell, hacf_digest *out) {
    if (!cell || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.grid81_cell.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f;
    f = cell->abi_version;       elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = cell->cell_index;        elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = cell->row;               elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = cell->column;            elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = cell->digit;             elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = cell->occupied;          elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = cell->compiler_writable; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = cell->capsule_count;     elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = cell->vertex_count;      elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = cell->constraint_count;  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < cell->capsule_count; i++) {
        elpis_sha256_update(&ctx, cell->ordered_capsule_digests[i].bytes, 32);
    }
    f = cell->vertex_count;  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < cell->vertex_count; i++) {
        elpis_sha256_update(&ctx, cell->ordered_topology_vertex_digests[i].bytes, 32);
    }
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_grid81_cell_validate(
    const elpis_semantic_grid81_cell_v1 *cell) {
    if (!cell) return SEMANTIC_E_INVAL;
    if (cell->abi_version != GRID81_CELL_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (cell->cell_index >= GRID81_CELL_COUNT) return SEMANTIC_E_INVAL;
    if (cell->row >= 9u) return SEMANTIC_E_INVAL;
    if (cell->column >= 9u) return SEMANTIC_E_INVAL;
    if (cell->digit > 9u) return SEMANTIC_E_INVAL;
    if (cell->occupied > 1u) return SEMANTIC_E_INVAL;
    if (cell->compiler_writable != 0u) return SEMANTIC_E_INVAL;
    if (cell->capsule_count > GRID81_CELL_MAX_CAPSULES) return SEMANTIC_E_INVAL;
    if (cell->vertex_count > GRID81_CELL_MAX_VERTICES) return SEMANTIC_E_INVAL;
    if (cell->constraint_count > GRID81_CELL_MAX_CONSTRAINTS) return SEMANTIC_E_INVAL;
    /* occupied must agree with capsule presence */
    uint32_t expected_occupied = (cell->capsule_count > 0) ? 1u : 0u;
    if (cell->occupied != expected_occupied) return SEMANTIC_E_INVAL;
    /* cell_index must match row/column */
    if (cell->cell_index != cell->row * 9u + cell->column) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(cell->reserved); i++) {
        if (cell->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_grid81_masks_validate(
    const elpis_semantic_grid81_masks_v1 *masks) {
    if (!masks) return SEMANTIC_E_INVAL;
    /* compiler_writable must be all zero */
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        if (masks->compiler_writable_mask81[i] != 0u) return SEMANTIC_E_INVAL;
        if (masks->occupied_mask81[i] > 1u) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_grid81_masks(const char *path,
    const elpis_semantic_grid81_masks_v1 *masks) {
    if (!path || !masks) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, masks, sizeof(*masks));
    if ((size_t)w != sizeof(*masks)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd); close(fd);
    return SEMANTIC_OK;
}

int elpis_read_grid81_masks(const char *path,
    elpis_semantic_grid81_masks_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    close(fd);
    if ((size_t)r != sizeof(*out)) return SEMANTIC_E_IO;
    return SEMANTIC_OK;
}
