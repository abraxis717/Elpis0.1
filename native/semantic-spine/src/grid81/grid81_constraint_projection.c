/* grid81_constraint_projection.c — Constraint projection v1. */
#include "elpis_semantic/grid81_constraint_projection.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

void elpis_grid81_constraint_projection_init(
    elpis_semantic_grid81_constraint_projection_v1 *proj) {
    if (!proj) return;
    memset(proj, 0, sizeof(*proj));
    proj->abi_version = GRID81_CONSTRAINT_PROJECTION_ABI_VERSION;
}

void elpis_grid81_constraint_projections_init(
    elpis_semantic_grid81_constraint_projections_v1 *projections) {
    if (!projections) return;
    memset(projections, 0, sizeof(*projections));
    projections->abi_version = GRID81_CONSTRAINT_PROJECTION_ABI_VERSION;
}

int elpis_grid81_constraint_projection_identity(
    const elpis_semantic_grid81_constraint_projection_v1 *proj, hacf_digest *out) {
    if (!proj || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.grid81_constraint_projection.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f;
    f = proj->abi_version;             elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, proj->P6_constraint_digest.bytes, 32);
    f = proj->constraint_type;         elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = proj->mandatory_constraint;    elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = proj->source_vertex_count;     elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < proj->source_vertex_count; i++) {
        elpis_sha256_update(&ctx, proj->ordered_source_topology_vertex_digests[i].bytes, 32);
    }
    f = proj->target_vertex_count;     elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < proj->target_vertex_count; i++) {
        elpis_sha256_update(&ctx, proj->ordered_target_topology_vertex_digests[i].bytes, 32);
    }
    f = proj->source_cell_count;       elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < proj->source_cell_count; i++) {
        f = proj->ordered_source_cell_indices[i]; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    }
    f = proj->target_cell_count;       elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < proj->target_cell_count; i++) {
        f = proj->ordered_target_cell_indices[i]; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    }
    f = proj->projection_disposition;  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    size_t reason_len = strlen(proj->projection_reason);
    if (reason_len > 0) {
        elpis_sha256_update(&ctx, (const uint8_t *)proj->projection_reason, reason_len);
    }
    elpis_sha256_update(&ctx, proj->projection_payload_digest.bytes, 32);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_grid81_constraint_projection_validate(
    const elpis_semantic_grid81_constraint_projection_v1 *proj) {
    if (!proj) return SEMANTIC_E_INVAL;
    if (proj->abi_version != GRID81_CONSTRAINT_PROJECTION_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (proj->projection_disposition > 6u) return SEMANTIC_E_INVAL;
    if (proj->source_vertex_count > GRID81_MAX_SOURCE_VERTICES) return SEMANTIC_E_INVAL;
    if (proj->target_vertex_count > GRID81_MAX_TARGET_VERTICES) return SEMANTIC_E_INVAL;
    if (proj->source_cell_count > GRID81_MAX_SOURCE_CELLS) return SEMANTIC_E_INVAL;
    if (proj->target_cell_count > GRID81_MAX_TARGET_CELLS) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(proj->reserved); i++) {
        if (proj->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_grid81_constraint_projections_identity(
    const elpis_semantic_grid81_constraint_projections_v1 *projections, hacf_digest *out) {
    if (!projections || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.grid81_constraint_projection_manifest.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f = projections->abi_version;  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = projections->projection_count;      elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < projections->projection_count; i++) {
        hacf_digest d;
        elpis_grid81_constraint_projection_identity(&projections->projections[i], &d);
        elpis_sha256_update(&ctx, d.bytes, 32);
    }
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_grid81_constraint_projections_validate(
    const elpis_semantic_grid81_constraint_projections_v1 *projections) {
    if (!projections) return SEMANTIC_E_INVAL;
    if (projections->abi_version != GRID81_CONSTRAINT_PROJECTION_ABI_VERSION) return SEMANTIC_E_INVAL;
    for (uint32_t i = 0; i < projections->projection_count; i++) {
        if (projections->projections[i].mandatory_constraint &&
            projections->projections[i].projection_disposition == GRID81_PROJECTION_UNSUPPORTED_BLOCKING) {
            return SEMANTIC_E_INVAL;
        }
        int rc = elpis_grid81_constraint_projection_validate(&projections->projections[i]);
        if (rc != SEMANTIC_OK) return rc;
    }
    for (size_t i = 0; i < sizeof(projections->reserved); i++) {
        if (projections->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_grid81_constraint_projections(const char *path,
    const elpis_semantic_grid81_constraint_projections_v1 *projections) {
    if (!path || !projections) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, projections, sizeof(*projections));
    if ((size_t)w != sizeof(*projections)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd); close(fd);
    return SEMANTIC_OK;
}

int elpis_read_grid81_constraint_projections(const char *path,
    elpis_semantic_grid81_constraint_projections_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    close(fd);
    if ((size_t)r != sizeof(*out)) return SEMANTIC_E_IO;
    return SEMANTIC_OK;
}
