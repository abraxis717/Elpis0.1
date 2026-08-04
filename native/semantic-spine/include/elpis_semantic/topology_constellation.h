/* elpis_semantic/topology_constellation.h — Constellations, distances, affiliations.
 *
 * Integer shortest paths over semantic relations only. Deterministic
 * multi-source Dijkstra. One constellation per anchor. Primary and
 * equal-best secondary affiliations.
 *
 * Identity domain: "elpis.semantic.topology_constellation.v1"
 */
#ifndef ELPIS_SEMANTIC_TOPOLOGY_CONSTELLATION_H
#define ELPIS_SEMANTIC_TOPOLOGY_CONSTELLATION_H

#include "elpis_semantic/topology_graph.h"
#include "elpis_semantic/topology_anchor.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TOPOLOGY_CONSTELLATION_ABI_VERSION 1u
#define TOPOLOGY_MAX_AFFILIATIONS_PER_VERTEX TOPOLOGY_DEFAULT_MAX_AFFILIATIONS

/* ──────────────────────────────────────────────────────────────────── */
/* Distance record — per vertex, per anchor                              */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct topology_distance_record_v1 {
    hacf_digest             target_vertex_digest;
    hacf_digest             anchor_digest;
    uint32_t                semantic_cost;     /* integer shortest path cost */
    uint32_t                hop_count;
    uint32_t                is_equal_best;     /* 0 or 1: ties with primary */
    hacf_digest             predecessor_vertex;
    hacf_digest             predecessor_incidence;
    uint8_t                 reserved[32];
} topology_distance_record_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Affiliation record — vertex to anchor binding                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_affiliation_kind {
    TOPOLOGY_AFFILIATION_PRIMARY   = 0,
    TOPOLOGY_AFFILIATION_SECONDARY = 1,
    TOPOLOGY_AFFILIATION_BRIDGE    = 2,
} topology_affiliation_kind;

typedef struct topology_affiliation_v1 {
    hacf_digest             vertex_digest;
    hacf_digest             anchor_digest;
    uint32_t                affiliation_kind;   /* topology_affiliation_kind */
    uint32_t                semantic_cost;
    uint32_t                hop_count;
    uint8_t                 reserved[32];
} topology_affiliation_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Constellation — one per anchor                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct topology_constellation_v1 {
    uint32_t                abi_version;
    hacf_digest             anchor_digest;
    hacf_digest             anchor_vertex_digest;
    uint32_t                primary_member_count;
    hacf_digest             primary_members[TOPOLOGY_DEFAULT_MAX_VERTICES];
    uint32_t                secondary_member_count;
    hacf_digest             secondary_members[TOPOLOGY_DEFAULT_MAX_VERTICES];
    uint32_t                bridge_member_count;
    hacf_digest             bridge_members[TOPOLOGY_DEFAULT_MAX_VERTICES];
    uint32_t                min_stratum;
    uint32_t                max_stratum;
    hacf_digest             constellation_identity;
    uint8_t                 reserved[48];
} topology_constellation_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Constellation collection                                              */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_topology_constellations_v1 {
    uint32_t                             abi_version;
    topology_constellation_v1            constellations[TOPOLOGY_DEFAULT_MAX_CONSTELLATIONS];
    uint32_t                             constellation_count;

    /* Distance records */
    topology_distance_record_v1          distance_records[TOPOLOGY_DEFAULT_MAX_VERTICES];
    uint32_t                             distance_record_count;

    /* Affiliations */
    topology_affiliation_v1              affiliations[TOPOLOGY_DEFAULT_MAX_VERTICES * TOPOLOGY_DEFAULT_MAX_AFFILIATIONS];
    uint32_t                             affiliation_count;

    hacf_digest                          constellation_plane_digest;
    uint8_t                              reserved[64];
} elpis_semantic_topology_constellations_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                            */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize empty constellations. */
void elpis_topology_constellations_init(
    elpis_semantic_topology_constellations_v1 *constellations);

/* Compute integer shortest paths using deterministic multi-source Dijkstra. */
int elpis_topology_compute_distances(
    elpis_semantic_topology_constellations_v1 *constellations,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_relation_registry_v1 *registry,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_anchors_v1 *anchors);

/* Construct constellations and affiliations from distance results. */
int elpis_topology_construct_constellations(
    elpis_semantic_topology_constellations_v1 *constellations,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_anchors_v1 *anchors);

/* Compute constellation identity. Domain: "elpis.semantic.topology_constellation.v1" */
int elpis_topology_constellation_identity(
    const topology_constellation_v1 *c, hacf_digest *out);

/* Compute constellation plane digest. */
int elpis_topology_constellation_plane_digest(
    const elpis_semantic_topology_constellations_v1 *constellations, hacf_digest *out);

/* Validate: no duplicate primary membership, valid affiliations. */
int elpis_topology_constellations_validate(
    const elpis_semantic_topology_constellations_v1 *constellations);

/* Find primary constellation index for a vertex. Returns -1 if none. */
int elpis_topology_find_constellation(
    const elpis_semantic_topology_constellations_v1 *constellations,
    const hacf_digest *vertex_digest);

/* Persistence */
int elpis_write_topology_constellations(const char *path,
    const elpis_semantic_topology_constellations_v1 *constellations);
int elpis_read_topology_constellations(const char *path,
    elpis_semantic_topology_constellations_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
