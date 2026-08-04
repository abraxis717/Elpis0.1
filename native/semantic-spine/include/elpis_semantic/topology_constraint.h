/* elpis_semantic/topology_constraint.h — Topology placement constraints.
 *
 * Generates immutable constraints for a future P7 Grid81 compiler.
 * Constraints describe invariants only — they do not specify physical
 * coordinates. No cell, row, column, box, or digit references.
 */
#ifndef ELPIS_SEMANTIC_TOPOLOGY_CONSTRAINT_H
#define ELPIS_SEMANTIC_TOPOLOGY_CONSTRAINT_H

#include "elpis_semantic/identity.h"
#include "elpis_semantic/topology_policy.h"
#include "elpis_semantic/topology_graph.h"
#include "elpis_semantic/topology_anchor.h"
#include "elpis_semantic/topology_constellation.h"
#include "elpis_semantic/topology_address.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TOPOLOGY_CONSTRAINT_ABI_VERSION 1u
#define TOPOLOGY_MAX_CONSTRAINT_FIELDS 8u
#define TOPOLOGY_MAX_CONSTRAINT_COUNT (TOPOLOGY_DEFAULT_MAX_VERTICES * 4u)

/* ──────────────────────────────────────────────────────────────────── */
/* Constraint types                                                      */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_constraint_type {
    TOPOLOGY_CONSTRAINT_ANCHOR_VERTEX                = 0,
    TOPOLOGY_CONSTRAINT_INCIDENCE_ADJACENCY           = 1,
    TOPOLOGY_CONSTRAINT_HYPEREDGE_PARTICIPANT_CLOSURE = 2,
    TOPOLOGY_CONSTRAINT_ORDERED_ROLE_SEQUENCE         = 3,
    TOPOLOGY_CONSTRAINT_CONSTELLATION_MEMBERSHIP      = 4,
    TOPOLOGY_CONSTRAINT_SECONDARY_AFFILIATION         = 5,
    TOPOLOGY_CONSTRAINT_SEMANTIC_STRATUM              = 6,
    TOPOLOGY_CONSTRAINT_LANE_MEMBERSHIP               = 7,
    TOPOLOGY_CONSTRAINT_CONFLICT_SHARED_TARGET        = 8,
    TOPOLOGY_CONSTRAINT_CONFLICT_POLARITY_SEPARATION  = 9,
    TOPOLOGY_CONSTRAINT_SCOPE_ATTACHMENT              = 10,
    TOPOLOGY_CONSTRAINT_QUALIFIER_ATTACHMENT          = 11,
    TOPOLOGY_CONSTRAINT_DEFINITION_ATTACHMENT         = 12,
    TOPOLOGY_CONSTRAINT_BRIDGE_MEMBERSHIP             = 13,
    TOPOLOGY_CONSTRAINT_METRIC_LOCAL_ORDER_HINT       = 14,
    TOPOLOGY_CONSTRAINT_TRANSPORT_TRACE_DEPENDENCY    = 15,
    TOPOLOGY_CONSTRAINT_PROVENANCE_TRACE_DEPENDENCY   = 16,
} topology_constraint_type;

/* ──────────────────────────────────────────────────────────────────── */
/* Constraint record                                                     */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct topology_constraint_v1 {
    uint32_t              abi_version;
    uint32_t              constraint_type;   /* topology_constraint_type */
    uint32_t              mandatory_flag;    /* 0 or 1: mandatory constraints must never be dropped */
    /* Variable fields — interpreted per constraint_type */
    hacf_digest           field_digests[TOPOLOGY_MAX_CONSTRAINT_FIELDS];
    uint32_t              field_count;
    uint32_t              constraint_flags;
    uint8_t               reserved[32];
} topology_constraint_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Constraint collection                                                 */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_topology_constraints_v1 {
    uint32_t                  abi_version;
    topology_constraint_v1    constraints[TOPOLOGY_MAX_CONSTRAINT_COUNT];
    uint32_t                  constraint_count;
    hacf_digest               constraint_plane_digest;
    uint8_t                   reserved[64];
} elpis_semantic_topology_constraints_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                            */
/* ──────────────────────────────────────────────────────────────────── */

void elpis_topology_constraints_init(
    elpis_semantic_topology_constraints_v1 *constraints);

/* Generate constraints from all P6 topology data. */
int elpis_topology_generate_constraints(
    elpis_semantic_topology_constraints_v1 *constraints,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_anchors_v1 *anchors,
    const elpis_semantic_topology_constellations_v1 *constellations,
    const elpis_semantic_topology_roles_v1 *roles,
    const elpis_semantic_topology_conflicts_v1 *conflicts,
    const elpis_semantic_topology_bridges_v1 *bridges,
    const elpis_semantic_topology_metric_hints_v1 *hints,
    const elpis_semantic_topology_addresses_v1 *addresses);

int elpis_topology_constraint_plane_digest(
    const elpis_semantic_topology_constraints_v1 *constraints, hacf_digest *out);

int elpis_topology_constraints_validate(
    const elpis_semantic_topology_constraints_v1 *constraints);

/* Persistence */
int elpis_write_topology_constraints(const char *path,
    const elpis_semantic_topology_constraints_v1 *constraints);
int elpis_read_topology_constraints(const char *path,
    elpis_semantic_topology_constraints_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
