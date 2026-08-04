/* elpis_semantic/type_registry.h — Immutable type registry for semantic hypergraph.
 *
 * Defines node-type IDs, hyperedge-type IDs, incidence-role IDs, and the rules
 * that govern valid combinations. Numeric IDs are canonical; human-readable
 * names belong in the manifest, not in identity.
 *
 * Namespace layout:
 *   0x10000000 | node_type_id     — semantic node types
 *   0x20000000 | hyperedge_type_id — semantic hyperedge types
 *   0x30000000 | incidence_role_id — incidence roles
 *
 * Collision-free by construction: the high byte distinguishes namespace.
 * Zero type IDs are rejected. Values outside their assigned namespace are rejected.
 */
#ifndef ELPIS_SEMANTIC_TYPE_REGISTRY_H
#define ELPIS_SEMANTIC_TYPE_REGISTRY_H

#include "elpis_semantic/identity.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SEMANTIC_NODE_NAMESPACE      0x10000000u
#define SEMANTIC_HYPEREDGE_NAMESPACE 0x20000000u
#define SEMANTIC_INCIDENCE_NAMESPACE 0x30000000u

#define SEMANTIC_MAX_TYPES           256u
#define SEMANTIC_MAX_ROLES_PER_TYPE  16u

/* A role definition for a specific hyperedge type. */
typedef struct semantic_role_rule {
    uint32_t    incidence_role;   /* namespace-prefixed role ID */
    uint32_t    min_cardinality;  /* minimum occurrences in a hyperedge */
    uint32_t    max_cardinality;  /* 0 = unbounded */
    int         is_ordered;       /* 1 = ordinals must be unique and sequential */
    int         allows_repeat;    /* 1 = same node may fill this role multiple times */
} semantic_role_rule;

/* A hyperedge-type definition with its allowed roles. */
typedef struct semantic_hyperedge_type_entry {
    uint32_t                    hyperedge_type;  /* namespace-prefixed */
    uint32_t                    min_participants;
    uint32_t                    max_participants; /* 0 = unbounded */
    uint32_t                    role_count;
    semantic_role_rule          roles[SEMANTIC_MAX_ROLES_PER_TYPE];
} semantic_hyperedge_type_entry;

/* A node-type definition. */
typedef struct semantic_node_type_entry {
    uint32_t      node_type;   /* namespace-prefixed */
    uint32_t      semantic_flag_mask;
    uint32_t      min_authority;
    uint32_t      max_authority;
} semantic_node_type_entry;

/* An incidence-role definition. */
typedef struct semantic_incidence_role_entry {
    uint32_t      incidence_role;  /* namespace-prefixed */
    uint32_t      participant_flag_mask;
} semantic_incidence_role_entry;

/* ───────────────────────────────────────────────────────────────────── */
/* Type registry                                                         */
/* ───────────────────────────────────────────────────────────────────── */

typedef struct semantic_type_registry semantic_type_registry;

/* Create a new mutable registry (mutable during construction only). */
semantic_type_registry *semantic_type_registry_create(void);
void semantic_type_registry_destroy(semantic_type_registry *reg);

/* Add types. Returns SEMANTIC_OK or error. Zero IDs and out-of-namespace
 * values are rejected. Duplicate IDs rejected after first insertion. */
int semantic_type_registry_add_node_type(semantic_type_registry *reg,
                                          const semantic_node_type_entry *entry);
int semantic_type_registry_add_hyperedge_type(semantic_type_registry *reg,
                                               const semantic_hyperedge_type_entry *entry);
int semantic_type_registry_add_incidence_role(semantic_type_registry *reg,
                                               const semantic_incidence_role_entry *entry);

/* Seal the registry — no further mutations. Returns identity digest. */
int semantic_type_registry_seal(semantic_type_registry *reg, hacf_digest *digest_out);

/* Lookup (read-only; works on sealed registries too). */
const semantic_node_type_entry *semantic_type_registry_get_node_type(
    const semantic_type_registry *reg, uint32_t node_type);
const semantic_hyperedge_type_entry *semantic_type_registry_get_hyperedge_type(
    const semantic_type_registry *reg, uint32_t hyperedge_type);
const semantic_incidence_role_entry *semantic_type_registry_get_incidence_role(
    const semantic_type_registry *reg, uint32_t incidence_role);

/* Get the role rule for a given hyperedge type + role. Returns NULL if not allowed. */
const semantic_role_rule *semantic_type_registry_get_role_rule(
    const semantic_type_registry *reg, uint32_t hyperedge_type, uint32_t incidence_role);

/* Is the registry sealed? */
int semantic_type_registry_is_sealed(const semantic_type_registry *reg);

/* Registry identity digest (valid after seal). */
int semantic_type_registry_digest(const semantic_type_registry *reg, hacf_digest *out);

/* Count entries. */
uint32_t semantic_type_registry_node_type_count(const semantic_type_registry *reg);
uint32_t semantic_type_registry_hyperedge_type_count(const semantic_type_registry *reg);
uint32_t semantic_type_registry_role_count(const semantic_type_registry *reg);

/* Validate that a given type ID belongs to the correct namespace.
 * Returns SEMANTIC_OK or SEMANTIC_E_NAMESPACE_COLLISION. */
int semantic_type_namespace_check(uint32_t type_id, uint32_t expected_namespace);

/* Extract bare ID from namespace-prefixed type. */
uint32_t semantic_type_bare_id(uint32_t namespaced_type);
uint32_t semantic_type_namespace(uint32_t namespaced_type);

/* Check if a type ID is in a specific namespace. */
int semantic_type_in_namespace(uint32_t type_id, uint32_t namespace_prefix);

#ifdef __cplusplus
}
#endif
#endif
