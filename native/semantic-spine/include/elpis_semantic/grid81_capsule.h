/* elpis_semantic/grid81_capsule.h — Topology capsule v1.
 *
 * A capsule is the exact structural unit packed into one Grid81 cell.
 * Capsules group topology vertices that share an identical capsule key.
 *
 * Identity domain: "elpis.semantic.grid81_capsule.v1"
 */
#ifndef ELPIS_SEMANTIC_GRID81_CAPSULE_H
#define ELPIS_SEMANTIC_GRID81_CAPSULE_H

#include "elpis_semantic/identity.h"
#include "elpis_semantic/topology_registry.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GRID81_CAPSULE_ABI_VERSION 1u
#define GRID81_MAX_VERTICES_PER_CAPSULE 4096u
#define GRID81_MAX_ADDRESSES_PER_CAPSULE 4096u
#define GRID81_MAX_AFFILIATIONS_PER_CAPSULE 16u
#define GRID81_MAX_CONSTRAINTS_PER_CAPSULE 64u

/* ──────────────────────────────────────────────────────────────────── */
/* Capsule key — determines grouping                                    */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct grid81_capsule_key_v1 {
    uint32_t              primary_constellation_index;
    uint32_t              semantic_stratum;
    uint32_t              primary_lane;       /* topology_lane */
    uint32_t              primary_role;       /* topology_role */
    uint32_t              relation_family_class; /* topology_relation_class */
    hacf_digest           cluster_key_digest;
    uint32_t              mandatory_flag;     /* 0 or 1 */
    uint32_t              conflict_branch_class; /* 0=none, 1=support, 2=contradiction */
    uint32_t              bridge_membership;  /* 0 or 1 */
    uint8_t               reserved[32];
} grid81_capsule_key_v1;

/* Compare two capsule keys for equality. Returns 0 if equal. */
int elpis_grid81_capsule_key_cmp(
    const grid81_capsule_key_v1 *a, const grid81_capsule_key_v1 *b);

/* Canonical comparison for sorting. Returns <0, 0, >0. */
int elpis_grid81_capsule_key_cmp_order(
    const grid81_capsule_key_v1 *a, const grid81_capsule_key_v1 *b);

/* ──────────────────────────────────────────────────────────────────── */
/* Capsule record                                                       */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_grid81_capsule_v1 {
    uint32_t              abi_version;

    /* P6 binding */
    hacf_digest           P6_topology_IR_digest;
    hacf_digest           P6_topology_handoff_digest;

    /* Primary placement key */
    uint32_t              primary_constellation_index;
    hacf_digest           primary_constellation_digest;
    hacf_digest           primary_anchor_digest;
    uint32_t              semantic_stratum;

    /* Lane, role, classification */
    uint32_t              primary_lane;           /* topology_lane */
    uint32_t              primary_role;           /* topology_role */
    uint32_t              relation_family_class;  /* topology_relation_class */

    /* Cluster and membership */
    hacf_digest           cluster_key_digest;
    uint32_t              mandatory_capsule;      /* 0 or 1 */
    uint32_t              conflict_membership;    /* 0=none, 1=support, 2=contradiction */
    uint32_t              bridge_membership;      /* 0 or 1 */
    uint32_t              scope_membership;       /* 0 or 1 */
    uint32_t              qualifier_membership;   /* 0 or 1 */
    uint32_t              metric_only;            /* 0 or 1 */

    /* Ordered member digests */
    hacf_digest           ordered_topology_vertex_digests[GRID81_MAX_VERTICES_PER_CAPSULE];
    uint32_t              vertex_count;

    hacf_digest           ordered_topology_address_digests[GRID81_MAX_ADDRESSES_PER_CAPSULE];
    uint32_t              address_count;

    hacf_digest           ordered_affiliation_digests[GRID81_MAX_AFFILIATIONS_PER_CAPSULE];
    uint32_t              affiliation_count;

    hacf_digest           ordered_constraint_digests[GRID81_MAX_CONSTRAINTS_PER_CAPSULE];
    uint32_t              constraint_count;

    /* Identity */
    hacf_digest           capsule_digest;

    uint8_t               reserved[32];
} elpis_semantic_grid81_capsule_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Capsule collection                                                   */
/* ──────────────────────────────────────────────────────────────────── */

#define GRID81_MAX_CAPSULES 4096u

typedef struct elpis_semantic_grid81_capsule_manifest_v1 {
    uint32_t                                  abi_version;
    elpis_semantic_grid81_capsule_v1          capsules[GRID81_MAX_CAPSULES];
    uint32_t                                  capsule_count;
    hacf_digest                               manifest_digest;
    uint8_t                                   reserved[64];
} elpis_semantic_grid81_capsule_manifest_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize empty capsule. Sets abi_version, zeroes reserved. */
void elpis_grid81_capsule_init(elpis_semantic_grid81_capsule_v1 *capsule);

/* Initialize empty capsule manifest. */
void elpis_grid81_capsule_manifest_init(
    elpis_semantic_grid81_capsule_manifest_v1 *manifest);

/* Compute capsule identity. Domain: "elpis.semantic.grid81_capsule.v1" */
int elpis_grid81_capsule_identity(
    const elpis_semantic_grid81_capsule_v1 *capsule, hacf_digest *out);

/* Validate capsule fields. */
int elpis_grid81_capsule_validate(
    const elpis_semantic_grid81_capsule_v1 *capsule);

/* Compute manifest identity. */
int elpis_grid81_capsule_manifest_identity(
    const elpis_semantic_grid81_capsule_manifest_v1 *manifest, hacf_digest *out);

/* Persistence */
int elpis_write_grid81_capsule_manifest(const char *path,
    const elpis_semantic_grid81_capsule_manifest_v1 *manifest);
int elpis_read_grid81_capsule_manifest(const char *path,
    elpis_semantic_grid81_capsule_manifest_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
