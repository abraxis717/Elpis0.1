/* type_registry.c — Immutable type registry implementation. */
#include "elpis_semantic/type_registry.h"
#include "elpis/sha256.h"
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>

struct semantic_type_registry {
    int sealed;
    hacf_digest digest;
    uint32_t node_type_count;
    uint32_t hyperedge_type_count;
    uint32_t role_count;
    semantic_node_type_entry     nodes[SEMANTIC_MAX_TYPES];
    semantic_hyperedge_type_entry edges[SEMANTIC_MAX_TYPES];
    semantic_incidence_role_entry roles[SEMANTIC_MAX_TYPES];
};

semantic_type_registry *semantic_type_registry_create(void) {
    semantic_type_registry *reg = calloc(1, sizeof(*reg));
    return reg;
}

void semantic_type_registry_destroy(semantic_type_registry *reg) {
    free(reg);
}

int semantic_type_namespace_check(uint32_t type_id, uint32_t expected_namespace) {
    if (type_id == 0) return SEMANTIC_E_INVAL;
    if ((type_id & 0xFF000000u) != expected_namespace) return SEMANTIC_E_NAMESPACE_COLLISION;
    return SEMANTIC_OK;
}

uint32_t semantic_type_bare_id(uint32_t namespaced_type) {
    return namespaced_type & 0x00FFFFFFu;
}

uint32_t semantic_type_namespace(uint32_t namespaced_type) {
    return namespaced_type & 0xFF000000u;
}

int semantic_type_in_namespace(uint32_t type_id, uint32_t namespace_prefix) {
    return (type_id & 0xFF000000u) == namespace_prefix;
}

static int find_node_type(const semantic_type_registry *reg, uint32_t node_type) {
    for (uint32_t i = 0; i < reg->node_type_count; i++) {
        if (reg->nodes[i].node_type == node_type) return (int)i;
    }
    return -1;
}

static int find_hyperedge_type(const semantic_type_registry *reg, uint32_t hyperedge_type) {
    for (uint32_t i = 0; i < reg->hyperedge_type_count; i++) {
        if (reg->edges[i].hyperedge_type == hyperedge_type) return (int)i;
    }
    return -1;
}

static int find_role(const semantic_type_registry *reg, uint32_t incidence_role) {
    for (uint32_t i = 0; i < reg->role_count; i++) {
        if (reg->roles[i].incidence_role == incidence_role) return (int)i;
    }
    return -1;
}

int semantic_type_registry_add_node_type(semantic_type_registry *reg,
                                          const semantic_node_type_entry *entry) {
    if (!reg || !entry || reg->sealed) return SEMANTIC_E_INVAL;
    if (semantic_type_namespace_check(entry->node_type, SEMANTIC_NODE_NAMESPACE) != SEMANTIC_OK)
        return SEMANTIC_E_NAMESPACE_COLLISION;
    if (find_node_type(reg, entry->node_type) >= 0) return SEMANTIC_E_DUPLICATE;
    if (reg->node_type_count >= SEMANTIC_MAX_TYPES) return SEMANTIC_E_REGISTRY_FULL;
    if (entry->max_authority > 3) return SEMANTIC_E_INVAL;
    if (entry->min_authority > entry->max_authority) return SEMANTIC_E_INVAL;
    reg->nodes[reg->node_type_count++] = *entry;
    return SEMANTIC_OK;
}

int semantic_type_registry_add_hyperedge_type(semantic_type_registry *reg,
                                               const semantic_hyperedge_type_entry *entry) {
    if (!reg || !entry || reg->sealed) return SEMANTIC_E_INVAL;
    if (semantic_type_namespace_check(entry->hyperedge_type, SEMANTIC_HYPEREDGE_NAMESPACE) != SEMANTIC_OK)
        return SEMANTIC_E_NAMESPACE_COLLISION;
    if (find_hyperedge_type(reg, entry->hyperedge_type) >= 0) return SEMANTIC_E_DUPLICATE;
    if (reg->hyperedge_type_count >= SEMANTIC_MAX_TYPES) return SEMANTIC_E_REGISTRY_FULL;
    if (entry->min_participants > entry->max_participants && entry->max_participants != 0)
        return SEMANTIC_E_CARDINALITY;
    if (entry->role_count > SEMANTIC_MAX_ROLES_PER_TYPE) return SEMANTIC_E_INVAL;
    for (uint32_t i = 0; i < entry->role_count; i++) {
        if (semantic_type_namespace_check(entry->roles[i].incidence_role, SEMANTIC_INCIDENCE_NAMESPACE) != SEMANTIC_OK)
            return SEMANTIC_E_NAMESPACE_COLLISION;
    }
    reg->edges[reg->hyperedge_type_count++] = *entry;
    return SEMANTIC_OK;
}

int semantic_type_registry_add_incidence_role(semantic_type_registry *reg,
                                               const semantic_incidence_role_entry *entry) {
    if (!reg || !entry || reg->sealed) return SEMANTIC_E_INVAL;
    if (semantic_type_namespace_check(entry->incidence_role, SEMANTIC_INCIDENCE_NAMESPACE) != SEMANTIC_OK)
        return SEMANTIC_E_NAMESPACE_COLLISION;
    if (find_role(reg, entry->incidence_role) >= 0) return SEMANTIC_E_DUPLICATE;
    if (reg->role_count >= SEMANTIC_MAX_TYPES) return SEMANTIC_E_REGISTRY_FULL;
    reg->roles[reg->role_count++] = *entry;
    return SEMANTIC_OK;
}

int semantic_type_registry_seal(semantic_type_registry *reg, hacf_digest *digest_out) {
    if (!reg || reg->sealed) return SEMANTIC_E_INVAL;
    reg->sealed = 1;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    /* Domain tag */
    size_t domain_len = strlen("elpis.semantic.type_registry.v1");
    uint32_t be_len = htonl((uint32_t)domain_len);
    elpis_sha256_update(&ctx, &be_len, 4);
    elpis_sha256_update(&ctx, "elpis.semantic.type_registry.v1", domain_len);

    /* Node types in insertion order (canonical for sealed registry) */
    uint32_t be_count = htonl(reg->node_type_count);
    elpis_sha256_update(&ctx, &be_count, 4);
    for (uint32_t i = 0; i < reg->node_type_count; i++) {
        be_count = htonl(reg->nodes[i].node_type);
        elpis_sha256_update(&ctx, &be_count, 4);
        be_count = htonl(reg->nodes[i].semantic_flag_mask);
        elpis_sha256_update(&ctx, &be_count, 4);
        be_count = htonl(reg->nodes[i].min_authority);
        elpis_sha256_update(&ctx, &be_count, 4);
        be_count = htonl(reg->nodes[i].max_authority);
        elpis_sha256_update(&ctx, &be_count, 4);
    }

    /* Hyperedge types */
    be_count = htonl(reg->hyperedge_type_count);
    elpis_sha256_update(&ctx, &be_count, 4);
    for (uint32_t i = 0; i < reg->hyperedge_type_count; i++) {
        be_count = htonl(reg->edges[i].hyperedge_type);
        elpis_sha256_update(&ctx, &be_count, 4);
        be_count = htonl(reg->edges[i].min_participants);
        elpis_sha256_update(&ctx, &be_count, 4);
        be_count = htonl(reg->edges[i].max_participants);
        elpis_sha256_update(&ctx, &be_count, 4);
        be_count = htonl(reg->edges[i].role_count);
        elpis_sha256_update(&ctx, &be_count, 4);
        for (uint32_t j = 0; j < reg->edges[i].role_count; j++) {
            const semantic_role_rule *r = &reg->edges[i].roles[j];
            be_count = htonl(r->incidence_role);
            elpis_sha256_update(&ctx, &be_count, 4);
            be_count = htonl(r->min_cardinality);
            elpis_sha256_update(&ctx, &be_count, 4);
            be_count = htonl(r->max_cardinality);
            elpis_sha256_update(&ctx, &be_count, 4);
            be_count = htonl(r->is_ordered);
            elpis_sha256_update(&ctx, &be_count, 4);
            be_count = htonl(r->allows_repeat);
            elpis_sha256_update(&ctx, &be_count, 4);
        }
    }

    /* Incidence roles */
    be_count = htonl(reg->role_count);
    elpis_sha256_update(&ctx, &be_count, 4);
    for (uint32_t i = 0; i < reg->role_count; i++) {
        be_count = htonl(reg->roles[i].incidence_role);
        elpis_sha256_update(&ctx, &be_count, 4);
        be_count = htonl(reg->roles[i].participant_flag_mask);
        elpis_sha256_update(&ctx, &be_count, 4);
    }

    elpis_sha256_final(&ctx, reg->digest.bytes);
    if (digest_out) *digest_out = reg->digest;
    return SEMANTIC_OK;
}

const semantic_node_type_entry *semantic_type_registry_get_node_type(
    const semantic_type_registry *reg, uint32_t node_type) {
    if (!reg) return NULL;
    int idx = find_node_type(reg, node_type);
    return idx >= 0 ? &reg->nodes[idx] : NULL;
}

const semantic_hyperedge_type_entry *semantic_type_registry_get_hyperedge_type(
    const semantic_type_registry *reg, uint32_t hyperedge_type) {
    if (!reg) return NULL;
    int idx = find_hyperedge_type(reg, hyperedge_type);
    return idx >= 0 ? &reg->edges[idx] : NULL;
}

const semantic_incidence_role_entry *semantic_type_registry_get_incidence_role(
    const semantic_type_registry *reg, uint32_t incidence_role) {
    if (!reg) return NULL;
    int idx = find_role(reg, incidence_role);
    return idx >= 0 ? &reg->roles[idx] : NULL;
}

const semantic_role_rule *semantic_type_registry_get_role_rule(
    const semantic_type_registry *reg, uint32_t hyperedge_type, uint32_t incidence_role) {
    if (!reg) return NULL;
    int idx = find_hyperedge_type(reg, hyperedge_type);
    if (idx < 0) return NULL;
    const semantic_hyperedge_type_entry *entry = &reg->edges[idx];
    for (uint32_t i = 0; i < entry->role_count; i++) {
        if (entry->roles[i].incidence_role == incidence_role)
            return &entry->roles[i];
    }
    return NULL;
}

int semantic_type_registry_is_sealed(const semantic_type_registry *reg) {
    return reg ? reg->sealed : 0;
}

int semantic_type_registry_digest(const semantic_type_registry *reg, hacf_digest *out) {
    if (!reg || !reg->sealed) return SEMANTIC_E_INVAL;
    *out = reg->digest;
    return SEMANTIC_OK;
}

uint32_t semantic_type_registry_node_type_count(const semantic_type_registry *reg) {
    return reg ? reg->node_type_count : 0;
}

uint32_t semantic_type_registry_hyperedge_type_count(const semantic_type_registry *reg) {
    return reg ? reg->hyperedge_type_count : 0;
}

uint32_t semantic_type_registry_role_count(const semantic_type_registry *reg) {
    return reg ? reg->role_count : 0;
}
