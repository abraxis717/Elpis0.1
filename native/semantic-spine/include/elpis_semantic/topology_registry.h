/* elpis_semantic/topology_registry.h — Relation registry for topology compiler.
 *
 * Binds qualified semantic relation types to topology class, traversal cost,
 * lane, polarity, classification, and bridge eligibility.
 *
 * Identity domain: "elpis.semantic.topology_relation_registry.v1"
 */
#ifndef ELPIS_SEMANTIC_TOPOLOGY_REGISTRY_H
#define ELPIS_SEMANTIC_TOPOLOGY_REGISTRY_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TOPOLOGY_REGISTRY_ABI_VERSION 1u
#define TOPOLOGY_REGISTRY_MAX_ENTRIES 64u

/* ──────────────────────────────────────────────────────────────────── */
/* Topology relation class                                               */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_relation_class {
    TOPOLOGY_CLASS_CONTEXT        = 0,
    TOPOLOGY_CLASS_DEFINITION     = 1,
    TOPOLOGY_CLASS_SUPPORT        = 2,
    TOPOLOGY_CLASS_CONTRADICTION  = 3,
    TOPOLOGY_CLASS_QUALIFIER      = 4,
    TOPOLOGY_CLASS_SCOPE_LIMIT    = 5,
    TOPOLOGY_CLASS_TRACE_ONLY     = 6,  /* transport/provenance, not traversable */
} topology_relation_class;

/* ──────────────────────────────────────────────────────────────────── */
/* Polarity                                                              */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_polarity {
    TOPOLOGY_POLARITY_NEUTRAL         = 0,
    TOPOLOGY_POLARITY_SUPPORT         = 1,
    TOPOLOGY_POLARITY_CONTRADICTION   = 2,
} topology_polarity;

/* ──────────────────────────────────────────────────────────────────── */
/* Semantic vs transport classification                                  */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_relation_classification {
    TOPOLOGY_CLASSIFICATION_SEMANTIC   = 0,
    TOPOLOGY_CLASSIFICATION_TRANSPORT  = 1,  /* trace only */
} topology_relation_classification;

/* ──────────────────────────────────────────────────────────────────── */
/* Lane                                                                  */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_lane {
    TOPOLOGY_LANE_CORE           = 0,
    TOPOLOGY_LANE_DEFINITION     = 1,
    TOPOLOGY_LANE_SUPPORT        = 2,
    TOPOLOGY_LANE_CONTRADICTION  = 3,
    TOPOLOGY_LANE_QUALIFIER      = 4,
    TOPOLOGY_LANE_SCOPE          = 5,
    TOPOLOGY_LANE_CONTEXT        = 6,
    TOPOLOGY_LANE_BRIDGE         = 7,
    TOPOLOGY_LANE_METRIC         = 8,
    TOPOLOGY_LANE_NEUTRAL        = 9,
} topology_lane;

/* ──────────────────────────────────────────────────────────────────── */
/* Registry entry                                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct topology_relation_entry_v1 {
    char                      semantic_relation_type[64];  /* qualified type name */
    uint32_t                  numeric_relation_type;       /* numeric ID from type registry */
    uint32_t                  topology_class;              /* topology_relation_class */
    uint32_t                  traversal_cost;              /* integer cost per hyperedge */
    uint32_t                  lane;                        /* topology_lane */
    uint32_t                  polarity;                    /* topology_polarity */
    uint32_t                  classification;              /* semantic or transport */
    uint32_t                  bridge_eligible;             /* 0 or 1 */
    uint8_t                   reserved[32];
} topology_relation_entry_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Registry                                                              */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_topology_relation_registry_v1 {
    uint32_t                          abi_version;
    topology_relation_entry_v1        entries[TOPOLOGY_REGISTRY_MAX_ENTRIES];
    uint32_t                          entry_count;
    hacf_digest                       registry_identity;
    uint8_t                           reserved[64];
} elpis_semantic_topology_relation_registry_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                            */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize with default entries (MENTIONS, DEFINES, SUPPORTS, etc.). */
void elpis_topology_registry_init(
    elpis_semantic_topology_relation_registry_v1 *registry);

/* Compute identity digest. Domain: "elpis.semantic.topology_relation_registry.v1" */
int elpis_topology_registry_identity(
    const elpis_semantic_topology_relation_registry_v1 *registry, hacf_digest *out);

/* Validate: known ABI, zero reserved, valid enums, unique types. */
int elpis_topology_registry_validate(
    const elpis_semantic_topology_relation_registry_v1 *registry);

/* Lookup by numeric relation type. Returns pointer or NULL. */
const topology_relation_entry_v1 *elpis_topology_registry_lookup(
    const elpis_semantic_topology_relation_registry_v1 *registry,
    uint32_t numeric_relation_type);

/* Check if a relation type is traversable (semantic, not transport). */
int elpis_topology_registry_is_traversable(
    const elpis_semantic_topology_relation_registry_v1 *registry,
    uint32_t numeric_relation_type);

/* Get traversal cost for a relation type. Returns -1 if unknown. */
int elpis_topology_registry_get_cost(
    const elpis_semantic_topology_relation_registry_v1 *registry,
    uint32_t numeric_relation_type);

/* Persistence */
int elpis_write_topology_registry(const char *path,
                                   const elpis_semantic_topology_relation_registry_v1 *registry);
int elpis_read_topology_registry(const char *path,
                                  elpis_semantic_topology_relation_registry_v1 *out);

#ifdef __cplusplus
}
#endif
#endif