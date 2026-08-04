/* elpis_semantic/topology_address.h — Roles, lanes, conflicts, bridges,
 *   metric hints, and topology addresses.
 *
 * Assigns abstract semantic roles and lanes. Preserves conflicts without
 * resolution. Creates bridge records. Binds metric hints as local-order
 * only. Produces abstract topology addresses (never Grid81 coordinates).
 *
 * Identity domain: "elpis.semantic.topology_address.v1"
 */
#ifndef ELPIS_SEMANTIC_TOPOLOGY_ADDRESS_H
#define ELPIS_SEMANTIC_TOPOLOGY_ADDRESS_H

#include "elpis_semantic/topology_graph.h"
#include "elpis_semantic/topology_anchor.h"
#include "elpis_semantic/topology_constellation.h"
#include "elpis_semantic/topology_registry.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TOPOLOGY_ADDRESS_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Topology role                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_role {
    TOPOLOGY_ROLE_QUERY_CORE              = 0,
    TOPOLOGY_ROLE_CONFLICT_TARGET         = 1,
    TOPOLOGY_ROLE_REQUIREMENT_TARGET      = 2,
    TOPOLOGY_ROLE_REQUIREMENT_WITNESS     = 3,
    TOPOLOGY_ROLE_SCOPE                   = 4,
    TOPOLOGY_ROLE_QUALIFIER               = 5,
    TOPOLOGY_ROLE_DEFINITION              = 6,
    TOPOLOGY_ROLE_SUPPORT_EVIDENCE        = 7,
    TOPOLOGY_ROLE_CONTRADICTION_EVIDENCE  = 8,
    TOPOLOGY_ROLE_CONTEXT                 = 9,
    TOPOLOGY_ROLE_CLAIM                   = 10,
    TOPOLOGY_ROLE_RELATION_HUB            = 11,
    TOPOLOGY_ROLE_BRIDGE                  = 12,
    TOPOLOGY_ROLE_METRIC_SATELLITE        = 13,
    TOPOLOGY_ROLE_NEUTRAL                 = 14,
} topology_role;

/* Role flags */
#define TOPOLOGY_ROLE_FLAG_NONE                0u
#define TOPOLOGY_ROLE_FLAG_ANCHOR              0x01u
#define TOPOLOGY_ROLE_FLAG_CONFLICT_TARGET     0x02u
#define TOPOLOGY_ROLE_FLAG_BRIDGE              0x04u
#define TOPOLOGY_ROLE_FLAG_SCOPE               0x08u
#define TOPOLOGY_ROLE_FLAG_QUALIFIER           0x10u
#define TOPOLOGY_ROLE_FLAG_MASK                0x1Fu

/* ──────────────────────────────────────────────────────────────────── */
/* Role assignment record                                                */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct topology_role_assignment_v1 {
    hacf_digest             vertex_digest;
    uint32_t                primary_role;      /* topology_role */
    uint32_t                role_flags;
    uint32_t                lane;              /* topology_lane */
    uint32_t                stratum;           /* semantic stratum within constellation */
    uint8_t                 reserved[32];
} topology_role_assignment_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Conflict record — UNRESOLVED_PRESERVED                                */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_conflict_status {
    TOPOLOGY_CONFLICT_UNRESOLVED_PRESERVED = 0,
} topology_conflict_status;

typedef struct topology_conflict_record_v1 {
    hacf_digest             conflict_target_vertex;
    uint32_t                support_edge_count;
    hacf_digest             support_edges[TOPOLOGY_DEFAULT_MAX_INCIDENCES / 4];
    uint32_t                contradiction_edge_count;
    hacf_digest             contradiction_edges[TOPOLOGY_DEFAULT_MAX_INCIDENCES / 4];
    uint32_t                assertion_count;
    uint32_t                conflict_status;  /* topology_conflict_status */
    uint8_t                 reserved[32];
} topology_conflict_record_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Bridge record                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_bridge_reason {
    TOPOLOGY_BRIDGE_HYPEREDGE_CROSS_CONSTELLATION = 0,
    TOPOLOGY_BRIDGE_EQUAL_BEST_AFFILIATION        = 1,
    TOPOLOGY_BRIDGE_CONFLICT_SPAN                 = 2,
} topology_bridge_reason;

typedef struct topology_bridge_record_v1 {
    hacf_digest             source_vertex_digest;
    hacf_digest             source_hyperedge_digest;
    uint32_t                bridge_reason;    /* topology_bridge_reason */
    uint32_t                constellation_count;
    uint32_t                constellation_indices[TOPOLOGY_DEFAULT_MAX_CONSTELLATIONS];
    uint8_t                 reserved[48];
} topology_bridge_record_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Metric hint record — local ordering only                              */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct topology_metric_hint_v1 {
    hacf_digest             source_vertex_digest;
    hacf_digest             neighbor_vertex_digest;
    hacf_digest             embedding_profile_digest;
    uint32_t                metric_kind;
    int64_t                 integer_score_key;
    hacf_digest             neighborhood_view_digest;
    uint8_t                 reserved[32];
} topology_metric_hint_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Topology address — abstract, not Grid81                               */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct topology_address_v1 {
    uint32_t                abi_version;
    hacf_digest             vertex_digest;
    uint32_t                constellation_index;
    uint32_t                semantic_stratum;
    uint32_t                primary_lane;        /* topology_lane */
    uint32_t                primary_role;        /* topology_role */
    uint32_t                relation_family_class; /* topology_relation_class */
    hacf_digest             cluster_key_digest;
    uint32_t                local_ordinal;
    uint32_t                flags;
    hacf_digest             address_identity;
    uint8_t                 reserved[32];
} topology_address_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Role/lane/conflict/bridge/metric/address collection                   */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_topology_roles_v1 {
    uint32_t                         abi_version;
    topology_role_assignment_v1      assignments[TOPOLOGY_DEFAULT_MAX_VERTICES];
    uint32_t                         assignment_count;
    uint8_t                          reserved[64];
} elpis_semantic_topology_roles_v1;

typedef struct elpis_semantic_topology_conflicts_v1 {
    uint32_t                         abi_version;
    topology_conflict_record_v1      conflicts[TOPOLOGY_DEFAULT_MAX_ANCHORS];
    uint32_t                         conflict_count;
    uint8_t                          reserved[64];
} elpis_semantic_topology_conflicts_v1;

typedef struct elpis_semantic_topology_bridges_v1 {
    uint32_t                         abi_version;
    topology_bridge_record_v1        bridges[TOPOLOGY_DEFAULT_MAX_BRIDGES];
    uint32_t                         bridge_count;
    uint8_t                          reserved[64];
} elpis_semantic_topology_bridges_v1;

typedef struct elpis_semantic_topology_metric_hints_v1 {
    uint32_t                         abi_version;
    topology_metric_hint_v1          hints[TOPOLOGY_DEFAULT_MAX_METRIC_HINTS];
    uint32_t                         hint_count;
    uint8_t                          reserved[64];
} elpis_semantic_topology_metric_hints_v1;

typedef struct elpis_semantic_topology_addresses_v1 {
    uint32_t                         abi_version;
    topology_address_v1              addresses[TOPOLOGY_DEFAULT_MAX_VERTICES];
    uint32_t                         address_count;
    hacf_digest                      address_plane_digest;
    uint8_t                          reserved[64];
} elpis_semantic_topology_addresses_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations — roles                                                    */
/* ──────────────────────────────────────────────────────────────────── */

void elpis_topology_roles_init(elpis_semantic_topology_roles_v1 *roles);
int elpis_topology_assign_roles(
    elpis_semantic_topology_roles_v1 *roles,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_relation_registry_v1 *registry,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_anchors_v1 *anchors,
    const elpis_semantic_bounded_semantic_view_v1 *view,
    const elpis_semantic_downstream_handoff_v1 *handoff);
int elpis_topology_roles_validate(const elpis_semantic_topology_roles_v1 *roles);

/* ──────────────────────────────────────────────────────────────────── */
/* Operations — conflicts                                                */
/* ──────────────────────────────────────────────────────────────────── */

void elpis_topology_conflicts_init(elpis_semantic_topology_conflicts_v1 *conflicts);
int elpis_topology_compile_conflicts(
    elpis_semantic_topology_conflicts_v1 *conflicts,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_relation_registry_v1 *registry,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_downstream_handoff_v1 *handoff);
int elpis_topology_conflicts_validate(
    const elpis_semantic_topology_conflicts_v1 *conflicts);

/* ──────────────────────────────────────────────────────────────────── */
/* Operations — bridges                                                  */
/* ──────────────────────────────────────────────────────────────────── */

void elpis_topology_bridges_init(elpis_semantic_topology_bridges_v1 *bridges);
int elpis_topology_compile_bridges(
    elpis_semantic_topology_bridges_v1 *bridges,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_constellations_v1 *constellations);
int elpis_topology_bridges_validate(
    const elpis_semantic_topology_bridges_v1 *bridges);

/* ──────────────────────────────────────────────────────────────────── */
/* Operations — metric hints                                             */
/* ──────────────────────────────────────────────────────────────────── */

void elpis_topology_metric_hints_init(
    elpis_semantic_topology_metric_hints_v1 *hints);
int elpis_topology_bind_metric_hints(
    elpis_semantic_topology_metric_hints_v1 *hints,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_downstream_handoff_v1 *handoff);
int elpis_topology_metric_hints_validate(
    const elpis_semantic_topology_metric_hints_v1 *hints);

/* ──────────────────────────────────────────────────────────────────── */
/* Operations — addresses                                                */
/* ──────────────────────────────────────────────────────────────────── */

void elpis_topology_addresses_init(elpis_semantic_topology_addresses_v1 *addrs);
int elpis_topology_assign_addresses(
    elpis_semantic_topology_addresses_v1 *addrs,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_constellations_v1 *constellations,
    const elpis_semantic_topology_roles_v1 *roles,
    const elpis_semantic_topology_metric_hints_v1 *hints);

/* Compute address identity. Domain: "elpis.semantic.topology_address.v1" */
int elpis_topology_address_identity(
    const topology_address_v1 *a, hacf_digest *out);

int elpis_topology_address_plane_digest(
    const elpis_semantic_topology_addresses_v1 *addrs, hacf_digest *out);
int elpis_topology_addresses_validate(
    const elpis_semantic_topology_addresses_v1 *addrs);

/* Persistence for all sub-modules */
int elpis_write_topology_roles(const char *path,
    const elpis_semantic_topology_roles_v1 *roles);
int elpis_write_topology_conflicts(const char *path,
    const elpis_semantic_topology_conflicts_v1 *conflicts);
int elpis_write_topology_bridges(const char *path,
    const elpis_semantic_topology_bridges_v1 *bridges);
int elpis_write_topology_metric_hints(const char *path,
    const elpis_semantic_topology_metric_hints_v1 *hints);
int elpis_write_topology_addresses(const char *path,
    const elpis_semantic_topology_addresses_v1 *addrs);

#ifdef __cplusplus
}
#endif
#endif
