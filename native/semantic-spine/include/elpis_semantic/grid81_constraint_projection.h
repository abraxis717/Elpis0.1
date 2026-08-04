/* elpis_semantic/grid81_constraint_projection.h — Constraint projection v1.
 *
 * Maps every P6 topology constraint to a P7 Grid81 projection record.
 * Each constraint receives a disposition describing how it is realized
 * in the structural layout or preserved in the sidecar.
 *
 * Identity domain: "elpis.semantic.grid81_constraint_projection.v1"
 */
#ifndef ELPIS_SEMANTIC_GRID81_CONSTRAINT_PROJECTION_H
#define ELPIS_SEMANTIC_GRID81_CONSTRAINT_PROJECTION_H

#include "elpis_semantic/topology_constraint.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GRID81_CONSTRAINT_PROJECTION_ABI_VERSION 1u
#define GRID81_MAX_SOURCE_VERTICES 16u
#define GRID81_MAX_TARGET_VERTICES 16u
#define GRID81_MAX_SOURCE_CELLS    16u
#define GRID81_MAX_TARGET_CELLS    16u

/* ──────────────────────────────────────────────────────────────────── */
/* Projection disposition                                               */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum grid81_projection_disposition {
    GRID81_PROJECTION_GEOMETRICALLY_REALIZED          = 0,
    GRID81_PROJECTION_CELL_COLOCATION_REALIZED         = 1,
    GRID81_PROJECTION_COLUMN_SEPARATION_REALIZED       = 2,
    GRID81_PROJECTION_ROW_STRATUM_REALIZED             = 3,
    GRID81_PROJECTION_SIDECAR_PRESERVED                = 4,
    GRID81_PROJECTION_TRACE_ONLY_PRESERVED             = 5,
    GRID81_PROJECTION_UNSUPPORTED_BLOCKING             = 6,
} grid81_projection_disposition;

/* ──────────────────────────────────────────────────────────────────── */
/* Projection record                                                    */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_grid81_constraint_projection_v1 {
    uint32_t              abi_version;

    /* Source constraint identity */
    hacf_digest           P6_constraint_digest;
    uint32_t              constraint_type;       /* topology_constraint_type */
    uint32_t              mandatory_constraint;  /* 0 or 1 */

    /* Vertex references */
    hacf_digest           ordered_source_topology_vertex_digests[GRID81_MAX_SOURCE_VERTICES];
    uint32_t              source_vertex_count;

    hacf_digest           ordered_target_topology_vertex_digests[GRID81_MAX_TARGET_VERTICES];
    uint32_t              target_vertex_count;

    /* Cell resolution */
    uint32_t              ordered_source_cell_indices[GRID81_MAX_SOURCE_CELLS];
    uint32_t              source_cell_count;

    uint32_t              ordered_target_cell_indices[GRID81_MAX_TARGET_CELLS];
    uint32_t              target_cell_count;

    /* Disposition and reason */
    uint32_t              projection_disposition; /* grid81_projection_disposition */
    char                  projection_reason[128];

    /* Payload and identity */
    hacf_digest           projection_payload_digest;
    hacf_digest           projection_digest;

    uint8_t               reserved[32];
} elpis_semantic_grid81_constraint_projection_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Projection collection                                                */
/* ──────────────────────────────────────────────────────────────────── */

#define GRID81_MAX_CONSTRAINT_PROJECTIONS (TOPOLOGY_DEFAULT_MAX_VERTICES * 4u)

typedef struct elpis_semantic_grid81_constraint_projections_v1 {
    uint32_t                                            abi_version;
    elpis_semantic_grid81_constraint_projection_v1      projections[GRID81_MAX_CONSTRAINT_PROJECTIONS];
    uint32_t                                            projection_count;
    hacf_digest                                         manifest_digest;
    uint8_t                                             reserved[64];
} elpis_semantic_grid81_constraint_projections_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize projection record. Sets abi_version, zeroes reserved. */
void elpis_grid81_constraint_projection_init(
    elpis_semantic_grid81_constraint_projection_v1 *proj);

/* Initialize projection collection. */
void elpis_grid81_constraint_projections_init(
    elpis_semantic_grid81_constraint_projections_v1 *projections);

/* Compute projection identity. Domain: "elpis.semantic.grid81_constraint_projection.v1" */
int elpis_grid81_constraint_projection_identity(
    const elpis_semantic_grid81_constraint_projection_v1 *proj, hacf_digest *out);

/* Validate projection fields. */
int elpis_grid81_constraint_projection_validate(
    const elpis_semantic_grid81_constraint_projection_v1 *proj);

/* Compute manifest identity. */
int elpis_grid81_constraint_projections_identity(
    const elpis_semantic_grid81_constraint_projections_v1 *projections, hacf_digest *out);

/* Validate collection: no mandatory constraint with UNSUPPORTED_BLOCKING. */
int elpis_grid81_constraint_projections_validate(
    const elpis_semantic_grid81_constraint_projections_v1 *projections);

/* Persistence */
int elpis_write_grid81_constraint_projections(const char *path,
    const elpis_semantic_grid81_constraint_projections_v1 *projections);
int elpis_read_grid81_constraint_projections(const char *path,
    elpis_semantic_grid81_constraint_projections_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
