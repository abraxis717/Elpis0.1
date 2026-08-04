/* grid81_policy.c — Immutable Grid81 compiler policy v1. */
#include "elpis_semantic/grid81_policy.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_grid81_policy_init(elpis_semantic_grid81_policy_v1 *policy) {
    if (!policy) return;
    memset(policy, 0, sizeof(*policy));
    policy->abi_version = GRID81_POLICY_ABI_VERSION;
    policy->cell_count = GRID81_CELL_COUNT;
    policy->row_count = GRID81_ROW_COUNT;
    policy->column_count = GRID81_COLUMN_COUNT;
    policy->digit_class_count = GRID81_DIGIT_CLASS_COUNT;
    policy->maximum_capsules = GRID81_DEFAULT_MAX_CAPSULES;
    policy->maximum_capsules_per_cell = GRID81_DEFAULT_MAX_CAPSULES_PER_CELL;
    policy->maximum_vertices_per_capsule = GRID81_DEFAULT_MAX_VERTICES_PER_CAPSULE;
    policy->maximum_vertices_per_cell = GRID81_DEFAULT_MAX_VERTICES_PER_CELL;
    policy->maximum_constraints_per_cell = GRID81_DEFAULT_MAX_CONSTRAINTS_PER_CELL;
    policy->constellation_row_policy = GRID81_FOLDED_CONSTELLATION_PLUS_STRATUM;
    policy->lane_column_policy = GRID81_FIXED_LANE_COLUMN;
    policy->multi_capsule_policy = GRID81_PACK_WITH_EXACT_SIDECAR;
    policy->multi_affiliation_policy = GRID81_PRIMARY_CELL_PLUS_SIDECAR_AFFILIATIONS;
    policy->conflict_policy = GRID81_DISTINCT_SUPPORT_AND_CONTRADICTION_COLUMNS;
    policy->metric_policy = GRID81_SIDECAR_ONLY_NO_PLACEMENT_AUTHORITY;
    policy->transport_policy = GRID81_SIDECAR_ONLY_NO_SEMANTIC_CELL;
    policy->writable_mask_policy = GRID81_COMPILER_FIXED_ALL_ZERO;
    policy->overflow_policy = GRID81_FAIL_CLOSED;
    policy->policy_flags = GRID81_POLICY_FLAG_STRICT;
}

int elpis_grid81_policy_identity(
    const elpis_semantic_grid81_policy_v1 *policy, hacf_digest *out) {
    if (!policy || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    /* Domain tag */
    const char domain[] = "elpis.semantic.grid81_policy.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    elpis_sha256_update(&ctx, (const uint8_t *)domain, 4);
    /* Pack fields in canonical order */
    uint32_t f;
    f = policy->abi_version;        elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->cell_count;         elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->row_count;          elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->column_count;       elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->digit_class_count;  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->maximum_capsules;   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->maximum_capsules_per_cell; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->maximum_vertices_per_capsule; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->maximum_vertices_per_cell;    elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->maximum_constraints_per_cell; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->constellation_row_policy;     elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->lane_column_policy;           elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->multi_capsule_policy;         elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->multi_affiliation_policy;     elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->conflict_policy;              elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->metric_policy;                elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->transport_policy;             elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->writable_mask_policy;         elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = policy->overflow_policy;              elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, policy->codebook_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, policy->sudoku_template_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, policy->constraint_projection_policy_digest.bytes, HACF_DIGEST_BYTES);
    f = policy->policy_flags;                 elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_grid81_policy_validate(
    const elpis_semantic_grid81_policy_v1 *policy) {
    if (!policy) return SEMANTIC_E_INVAL;
    if (policy->abi_version != GRID81_POLICY_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (policy->cell_count != GRID81_CELL_COUNT) return SEMANTIC_E_INVAL;
    if (policy->row_count != GRID81_ROW_COUNT) return SEMANTIC_E_INVAL;
    if (policy->column_count != GRID81_COLUMN_COUNT) return SEMANTIC_E_INVAL;
    if (policy->digit_class_count != GRID81_DIGIT_CLASS_COUNT) return SEMANTIC_E_INVAL;
    if (policy->constellation_row_policy > 0) return SEMANTIC_E_INVAL;
    if (policy->lane_column_policy > 0) return SEMANTIC_E_INVAL;
    if (policy->multi_capsule_policy > 0) return SEMANTIC_E_INVAL;
    if (policy->multi_affiliation_policy > 0) return SEMANTIC_E_INVAL;
    if (policy->conflict_policy > 0) return SEMANTIC_E_INVAL;
    if (policy->metric_policy > 0) return SEMANTIC_E_INVAL;
    if (policy->transport_policy > 0) return SEMANTIC_E_INVAL;
    if (policy->writable_mask_policy > 0) return SEMANTIC_E_INVAL;
    if (policy->overflow_policy > 0) return SEMANTIC_E_INVAL;
    if (policy->policy_flags & ~GRID81_POLICY_FLAG_MASK) return SEMANTIC_E_INVAL;
    /* Reserved must be zero */
    for (size_t i = 0; i < sizeof(policy->reserved); i++) {
        if (policy->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_grid81_policy(const char *path,
    const elpis_semantic_grid81_policy_v1 *policy) {
    if (!path || !policy) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, policy, sizeof(*policy));
    if ((size_t)w != sizeof(*policy)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}

int elpis_read_grid81_policy(const char *path,
    elpis_semantic_grid81_policy_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    close(fd);
    if ((size_t)r != sizeof(*out)) return SEMANTIC_E_IO;
    return SEMANTIC_OK;
}
