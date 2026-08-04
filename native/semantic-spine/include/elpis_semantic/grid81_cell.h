/* elpis_semantic/grid81_cell.h — Grid81 cell records v1.
 *
 * One record per Grid81 cell. Tracks capsule membership, vertex counts,
 * occupied/writable masks, and trace digests.
 *
 * Identity domain: "elpis.semantic.grid81_cell.v1"
 */
#ifndef ELPIS_SEMANTIC_GRID81_CELL_H
#define ELPIS_SEMANTIC_GRID81_CELL_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GRID81_CELL_ABI_VERSION 1u
#define GRID81_CELL_MAX_CAPSULES 4096u
#define GRID81_CELL_MAX_VERTICES 65535u
#define GRID81_CELL_MAX_CONSTRAINTS 65535u

/* ──────────────────────────────────────────────────────────────────── */
/* Cell record                                                          */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_grid81_cell_v1 {
    uint32_t              abi_version;

    /* Coordinates */
    uint32_t              cell_index;   /* 0-80 */
    uint32_t              row;          /* 0-8 */
    uint32_t              column;       /* 0-8 */
    uint32_t              digit;        /* 0-9, 0=empty */

    /* Masks */
    uint32_t              occupied;           /* 1 when capsule_count > 0 */
    uint32_t              compiler_writable;  /* always 0 in P7 */

    /* Counts */
    uint32_t              capsule_count;
    uint32_t              vertex_count;
    uint32_t              constraint_count;

    /* Ordered member digests */
    hacf_digest           ordered_capsule_digests[GRID81_CELL_MAX_CAPSULES];
    hacf_digest           ordered_topology_vertex_digests[GRID81_CELL_MAX_VERTICES];
    hacf_digest           ordered_constraint_projection_digests[GRID81_CELL_MAX_CONSTRAINTS];

    /* Primary capsule (first in canonical order, or zero if empty) */
    hacf_digest           primary_capsule_digest_or_zero;

    /* Trace */
    hacf_digest           cell_trace_digest;

    /* Identity */
    hacf_digest           cell_digest;

    uint8_t               reserved[32];
} elpis_semantic_grid81_cell_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Cell collection (81 cells)                                           */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_grid81_cells_v1 {
    uint32_t                          abi_version;
    elpis_semantic_grid81_cell_v1     cells[GRID81_CELL_COUNT];
    hacf_digest                       cells_digest;
    uint8_t                           reserved[64];
} elpis_semantic_grid81_cells_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Mask arrays                                                          */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_grid81_masks_v1 {
    uint32_t                          occupied_mask81[GRID81_CELL_COUNT];
    uint32_t                          compiler_writable_mask81[GRID81_CELL_COUNT];
    uint8_t                           reserved[64];
} elpis_semantic_grid81_masks_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize cell record. Sets abi_version, zeroes reserved. */
void elpis_grid81_cell_init(elpis_semantic_grid81_cell_v1 *cell);

/* Initialize cell collection. */
void elpis_grid81_cells_init(elpis_semantic_grid81_cells_v1 *cells);

/* Initialize masks (all zero). */
void elpis_grid81_masks_init(elpis_semantic_grid81_masks_v1 *masks);

/* Compute cell identity. Domain: "elpis.semantic.grid81_cell.v1" */
int elpis_grid81_cell_identity(
    const elpis_semantic_grid81_cell_v1 *cell, hacf_digest *out);

/* Validate cell: ABI, indices, masks, reserved zeroed. */
int elpis_grid81_cell_validate(
    const elpis_semantic_grid81_cell_v1 *cell);

/* Validate masks: occupied agrees with capsule presence, writable all zero. */
int elpis_grid81_masks_validate(
    const elpis_semantic_grid81_masks_v1 *masks);

/* Persistence */
int elpis_write_grid81_masks(const char *path,
    const elpis_semantic_grid81_masks_v1 *masks);
int elpis_read_grid81_masks(const char *path,
    elpis_semantic_grid81_masks_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
