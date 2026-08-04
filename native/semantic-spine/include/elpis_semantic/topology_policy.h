/* elpis_semantic/topology_policy.h — Immutable topology policy v1.
 *
 * Defines capacity limits and behavioral rules for the topology compiler.
 * No Grid81 coordinates, no projector coupling, no model invocation.
 *
 * Identity domain: "elpis.semantic.topology_policy.v1"
 */
#ifndef ELPIS_SEMANTIC_TOPOLOGY_POLICY_H
#define ELPIS_SEMANTIC_TOPOLOGY_POLICY_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TOPOLOGY_POLICY_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Default capacity limits                                               */
/* ──────────────────────────────────────────────────────────────────── */

#define TOPOLOGY_DEFAULT_MAX_VERTICES          768u
#define TOPOLOGY_DEFAULT_MAX_INCIDENCES        2048u
#define TOPOLOGY_DEFAULT_MAX_ANCHORS           256u
#define TOPOLOGY_DEFAULT_MAX_CONSTELLATIONS    256u
#define TOPOLOGY_DEFAULT_MAX_AFFILIATIONS      16u
#define TOPOLOGY_DEFAULT_MAX_PATH_COST         65535u
#define TOPOLOGY_DEFAULT_MAX_PATH_HOPS         32u
#define TOPOLOGY_DEFAULT_MAX_BRIDGES           256u
#define TOPOLOGY_DEFAULT_MAX_METRIC_HINTS      512u

/* ──────────────────────────────────────────────────────────────────── */
/* Behavioral enum values                                                */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_unanchored_behavior {
    TOPOLOGY_UNANCHORED_FAIL_CLOSED = 0,  /* default: reject unanchored objects */
} topology_unanchored_behavior;

typedef enum topology_capacity_overflow_behavior {
    TOPOLOGY_CAPACITY_OVERFLOW_FAIL_CLOSED = 0,  /* default: reject on overflow */
} topology_capacity_overflow_behavior;

typedef enum topology_conflict_policy {
    TOPOLOGY_CONFLICT_PRESERVE_BOTH = 0,  /* default: preserve both branches */
} topology_conflict_policy;

typedef enum topology_transport_policy {
    TOPOLOGY_TRANSPORT_TRACE_ONLY = 0,  /* default: trace only, not semantic */
} topology_transport_policy;

typedef enum topology_metric_policy {
    TOPOLOGY_METRIC_LOCAL_ORDER_ONLY = 0,  /* default: local ordering only */
} topology_metric_policy;

/* ──────────────────────────────────────────────────────────────────── */
/* Policy flags                                                          */
/* ──────────────────────────────────────────────────────────────────── */

#define TOPOLOGY_POLICY_FLAG_NONE        0u
#define TOPOLOGY_POLICY_FLAG_STRICT      0x01u
#define TOPOLOGY_POLICY_FLAG_MASK        0x01u

/* ──────────────────────────────────────────────────────────────────── */
/* Policy record                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_topology_policy_v1 {
    uint32_t                abi_version;

    /* Capacity limits */
    uint32_t                max_vertices;
    uint32_t                max_incidences;
    uint32_t                max_anchors;
    uint32_t                max_constellations;
    uint32_t                max_affiliations_per_vertex;
    uint32_t                max_semantic_path_cost;
    uint32_t                max_semantic_path_hops;
    uint32_t                max_bridges;
    uint32_t                max_metric_hints;

    /* Behavioral rules */
    uint32_t                unanchored_behavior;        /* topology_unanchored_behavior */
    uint32_t                capacity_overflow_behavior; /* topology_capacity_overflow_behavior */
    uint32_t                conflict_policy;            /* topology_conflict_policy */
    uint32_t                transport_policy;           /* topology_transport_policy */
    uint32_t                metric_policy;              /* topology_metric_policy */

    /* Identity digests for sub-policies */
    hacf_digest             address_policy_digest;
    hacf_digest             constraint_policy_digest;

    /* Flags and reserved */
    uint32_t                flags;
    uint8_t                 reserved[128];

    /* Identity */
    hacf_digest             policy_identity;
} elpis_semantic_topology_policy_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                            */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize with defaults. Sets abi_version, all defaults, zeroed reserved. */
void elpis_topology_policy_init(elpis_semantic_topology_policy_v1 *policy);

/* Compute identity digest. Domain: "elpis.semantic.topology_policy.v1" */
int elpis_topology_policy_identity(
    const elpis_semantic_topology_policy_v1 *policy, hacf_digest *out);

/* Validate: known ABI, limits in range, zero reserved, valid enum values. */
int elpis_topology_policy_validate(
    const elpis_semantic_topology_policy_v1 *policy);

/* Check capacity: returns SEMANTIC_OK or SEMANTIC_E_CARDINALITY. */
int elpis_topology_policy_check_capacity(
    const elpis_semantic_topology_policy_v1 *policy,
    uint32_t vertex_count, uint32_t incidence_count,
    uint32_t anchor_count, uint32_t constellation_count);

/* Persistence */
int elpis_write_topology_policy(const char *path,
                                 const elpis_semantic_topology_policy_v1 *policy);
int elpis_read_topology_policy(const char *path,
                                elpis_semantic_topology_policy_v1 *out);

#ifdef __cplusplus
}
#endif
#endif