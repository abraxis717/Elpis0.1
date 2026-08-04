/* elpis_semantic/grid81_policy.h — Immutable Grid81 compiler policy v1.
 *
 * Defines capacity limits, behavioral rules, and structural constants for
 * the P7 Grid81 structural compiler. Pure policy — no execution, no TRM
 * coupling, no projector weights.
 *
 * Identity domain: "elpis.semantic.grid81_policy.v1"
 */
#ifndef ELPIS_SEMANTIC_GRID81_POLICY_H
#define ELPIS_SEMANTIC_GRID81_POLICY_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GRID81_POLICY_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Structural constants                                                 */
/* ──────────────────────────────────────────────────────────────────── */

#define GRID81_CELL_COUNT          81u
#define GRID81_ROW_COUNT           9u
#define GRID81_COLUMN_COUNT        9u
#define GRID81_DIGIT_CLASS_COUNT   10u

/* ──────────────────────────────────────────────────────────────────── */
/* Capacity limits                                                      */
/* ──────────────────────────────────────────────────────────────────── */

#define GRID81_DEFAULT_MAX_CAPSULES            4096u
#define GRID81_DEFAULT_MAX_CAPSULES_PER_CELL   4096u
#define GRID81_DEFAULT_MAX_VERTICES_PER_CAPSULE 4096u
#define GRID81_DEFAULT_MAX_VERTICES_PER_CELL   65535u
#define GRID81_DEFAULT_MAX_CONSTRAINTS_PER_CELL 65535u

/* ──────────────────────────────────────────────────────────────────── */
/* Behavioral policies                                                  */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum grid81_constellation_row_policy {
    GRID81_FOLDED_CONSTELLATION_PLUS_STRATUM = 0,
} grid81_constellation_row_policy;

typedef enum grid81_lane_column_policy {
    GRID81_FIXED_LANE_COLUMN = 0,
} grid81_lane_column_policy;

typedef enum grid81_multi_capsule_policy {
    GRID81_PACK_WITH_EXACT_SIDECAR = 0,
} grid81_multi_capsule_policy;

typedef enum grid81_multi_affiliation_policy {
    GRID81_PRIMARY_CELL_PLUS_SIDECAR_AFFILIATIONS = 0,
} grid81_multi_affiliation_policy;

typedef enum grid81_conflict_policy {
    GRID81_DISTINCT_SUPPORT_AND_CONTRADICTION_COLUMNS = 0,
} grid81_conflict_policy;

typedef enum grid81_metric_policy {
    GRID81_SIDECAR_ONLY_NO_PLACEMENT_AUTHORITY = 0,
} grid81_metric_policy;

typedef enum grid81_transport_policy {
    GRID81_SIDECAR_ONLY_NO_SEMANTIC_CELL = 0,
} grid81_transport_policy;

typedef enum grid81_writable_mask_policy {
    GRID81_COMPILER_FIXED_ALL_ZERO = 0,
} grid81_writable_mask_policy;

typedef enum grid81_overflow_policy {
    GRID81_FAIL_CLOSED = 0,
} grid81_overflow_policy;

/* ──────────────────────────────────────────────────────────────────── */
/* Policy flags                                                         */
/* ──────────────────────────────────────────────────────────────────── */

#define GRID81_POLICY_FLAG_NONE       0u
#define GRID81_POLICY_FLAG_STRICT     0x01u
#define GRID81_POLICY_FLAG_MASK       0x01u

/* ──────────────────────────────────────────────────────────────────── */
/* Policy record                                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_grid81_policy_v1 {
    uint32_t                          abi_version;

    /* Structural constants */
    uint32_t                          cell_count;
    uint32_t                          row_count;
    uint32_t                          column_count;
    uint32_t                          digit_class_count;

    /* Capacity limits */
    uint32_t                          maximum_capsules;
    uint32_t                          maximum_capsules_per_cell;
    uint32_t                          maximum_vertices_per_capsule;
    uint32_t                          maximum_vertices_per_cell;
    uint32_t                          maximum_constraints_per_cell;

    /* Behavioral rules */
    uint32_t                          constellation_row_policy;  /* grid81_constellation_row_policy */
    uint32_t                          lane_column_policy;        /* grid81_lane_column_policy */
    uint32_t                          multi_capsule_policy;      /* grid81_multi_capsule_policy */
    uint32_t                          multi_affiliation_policy;  /* grid81_multi_affiliation_policy */
    uint32_t                          conflict_policy;           /* grid81_conflict_policy */
    uint32_t                          metric_policy;             /* grid81_metric_policy */
    uint32_t                          transport_policy;          /* grid81_transport_policy */
    uint32_t                          writable_mask_policy;      /* grid81_writable_mask_policy */
    uint32_t                          overflow_policy;           /* grid81_overflow_policy */

    /* Sub-policy identity digests */
    hacf_digest                       codebook_digest;
    hacf_digest                       sudoku_template_digest;
    hacf_digest                       constraint_projection_policy_digest;

    /* Flags and identity */
    uint32_t                          policy_flags;
    hacf_digest                       policy_digest;

    uint8_t                           reserved[64];
} elpis_semantic_grid81_policy_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize with P7 v1 defaults. Sets all fields, zeroes reserved. */
void elpis_grid81_policy_init(elpis_semantic_grid81_policy_v1 *policy);

/* Compute identity digest. Domain: "elpis.semantic.grid81_policy.v1" */
int elpis_grid81_policy_identity(
    const elpis_semantic_grid81_policy_v1 *policy, hacf_digest *out);

/* Validate: ABI version, structural constants match spec, enum values known,
 * reserved zeroed, capacity in range. */
int elpis_grid81_policy_validate(
    const elpis_semantic_grid81_policy_v1 *policy);

/* Persistence */
int elpis_write_grid81_policy(const char *path,
    const elpis_semantic_grid81_policy_v1 *policy);
int elpis_read_grid81_policy(const char *path,
    elpis_semantic_grid81_policy_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
