/* elpis_semantic/topology_anchor.h — Topology anchors from P5 control records.
 *
 * Constructs anchors only from explicit P5 control records. Never derives
 * anchors from payload text, degree, embeddings, retrieval rank, or model
 * confidence.
 *
 * Identity domain: "elpis.semantic.topology_anchor.v1"
 */
#ifndef ELPIS_SEMANTIC_TOPOLOGY_ANCHOR_H
#define ELPIS_SEMANTIC_TOPOLOGY_ANCHOR_H

#include "elpis_semantic/topology_graph.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TOPOLOGY_ANCHOR_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Anchor source kind                                                    */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_anchor_source_kind {
    TOPOLOGY_ANCHOR_SOURCE_QUERY              = 0,
    TOPOLOGY_ANCHOR_SOURCE_REQUIREMENT_TARGET = 1,
    TOPOLOGY_ANCHOR_SOURCE_REQUIREMENT_WITNESS= 2,
    TOPOLOGY_ANCHOR_SOURCE_CONFLICT_TARGET    = 3,
    TOPOLOGY_ANCHOR_SOURCE_PREFERRED_TARGET   = 4,
} topology_anchor_source_kind;

/* Priority levels (lower = higher priority) */
#define TOPOLOGY_ANCHOR_PRIORITY_QUERY           0u
#define TOPOLOGY_ANCHOR_PRIORITY_MANDATORY       1u
#define TOPOLOGY_ANCHOR_PRIORITY_PREFERRED       2u
#define TOPOLOGY_ANCHOR_PRIORITY_CONFLICT        3u

/* ──────────────────────────────────────────────────────────────────── */
/* Requirement level                                                     */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_requirement_level {
    TOPOLOGY_REQUIREMENT_NONE     = 0u,
    TOPOLOGY_REQUIREMENT_MANDATORY= 1u,
    TOPOLOGY_REQUIREMENT_PREFERRED= 2u,
    TOPOLOGY_REQUIREMENT_DIAGNOSTIC=3u,
} topology_requirement_level;

/* ──────────────────────────────────────────────────────────────────── */
/* Anchor record                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct topology_anchor_v1 {
    uint32_t                  abi_version;
    hacf_digest               anchor_vertex_digest;   /* topology vertex digest */
    uint32_t                  source_kind;            /* topology_anchor_source_kind */
    hacf_digest               source_digest;          /* originating control record */
    char                      reason[128];            /* human-readable reason */
    hacf_digest               originating_requirement; /* zero if none */
    uint32_t                  requirement_level;      /* topology_requirement_level */
    uint32_t                  priority;
    uint32_t                  mandatory_flag;         /* 0 or 1 */
    hacf_digest               anchor_identity;
    uint8_t                   reserved[32];
} topology_anchor_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Anchor collection                                                     */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_topology_anchors_v1 {
    uint32_t                 abi_version;
    topology_anchor_v1       anchors[TOPOLOGY_DEFAULT_MAX_ANCHORS];
    uint32_t                 anchor_count;
    hacf_digest              anchor_plane_digest;
    uint8_t                  reserved[64];
} elpis_semantic_topology_anchors_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                            */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize empty anchor collection. */
void elpis_topology_anchors_init(elpis_semantic_topology_anchors_v1 *anchors);

/* Construct anchors from P5 control records and topology graph. */
int elpis_topology_construct_anchors(
    elpis_semantic_topology_anchors_v1 *anchors,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_bounded_semantic_view_v1 *view,
    const elpis_semantic_downstream_handoff_v1 *handoff);

/* Compute anchor identity. Domain: "elpis.semantic.topology_anchor.v1" */
int elpis_topology_anchor_identity(
    const topology_anchor_v1 *a, hacf_digest *out);

/* Compute anchor plane digest. */
int elpis_topology_anchor_plane_digest(
    const elpis_semantic_topology_anchors_v1 *anchors, hacf_digest *out);

/* Validate anchors: priority ordering, mandatory flags, unique vertices. */
int elpis_topology_anchors_validate(
    const elpis_semantic_topology_anchors_v1 *anchors);

/* Find anchor for a topology vertex. Returns NULL if none. */
const topology_anchor_v1 *elpis_topology_find_anchor(
    const elpis_semantic_topology_anchors_v1 *anchors,
    const hacf_digest *vertex_digest);

/* Persistence */
int elpis_write_topology_anchors(const char *path,
                                  const elpis_semantic_topology_anchors_v1 *anchors);
int elpis_read_topology_anchors(const char *path,
                                 elpis_semantic_topology_anchors_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
