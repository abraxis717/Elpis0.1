/* hypergraph_builder.c — Semantic hypergraph builder with canonical ordering. */
#include "elpis_semantic/hypergraph.h"
#include "builder_internal.h"
#include "elpis/sha256.h"
#include <stdlib.h>
#include <string.h>

/* struct semantic_hypergraph_builder defined in builder_internal.h */

static int ensure_capacity(void **mem, size_t elem_size, uint32_t *count, uint32_t *capacity, uint32_t needed) {
    if (*capacity >= needed) return SEMANTIC_OK;
    uint32_t new_cap = *capacity ? *capacity * 2 : 64;
    if (new_cap < needed) new_cap = needed;
    void *tmp = realloc(*mem, new_cap * elem_size);
    if (!tmp) return SEMANTIC_BUILDER_E_NOMEM;
    *mem = tmp;
    *capacity = new_cap;
    return SEMANTIC_OK;
}

static int sorted_insert_node(semantic_hypergraph_builder *b, const elpis_semantic_node_v1 *node) {
    /* Find insertion point keeping canonical order (by node digest). */
    uint32_t i;
    for (i = 0; i < b->node_count; i++) {
        int c = elpis_semantic_node_cmp(&b->nodes[i], node);
        if (c >= 0) break;
    }
    /* Check for exact duplicate (same identity = collapse). */
    if (i < b->node_count && memcmp(b->nodes[i].node_identity.bytes, node->node_identity.bytes, HACF_DIGEST_BYTES) == 0) {
        /* Exact duplicate — verify payload matches (conflict check). */
        if (memcmp(b->nodes[i].payload_digest.bytes, node->payload_digest.bytes, HACF_DIGEST_BYTES) != 0) {
            return SEMANTIC_BUILDER_E_CONFLICT;
        }
        return SEMANTIC_BUILDER_E_DUPLICATE; /* collapse silently — return dup code */
    }
    if (ensure_capacity((void **)&b->nodes, sizeof(*node), &b->node_count, &b->node_capacity, b->node_count + 1) != SEMANTIC_OK)
        return SEMANTIC_BUILDER_E_NOMEM;
    memmove(&b->nodes[i + 1], &b->nodes[i], (b->node_count - i) * sizeof(*node));
    b->nodes[i] = *node;
    b->node_count++;
    return SEMANTIC_BUILDER_OK;
}

static int sorted_insert_assertion(semantic_hypergraph_builder *b, const elpis_semantic_assertion_v1 *assertion) {
    uint32_t i;
    for (i = 0; i < b->assertion_count; i++) {
        int c = elpis_semantic_assertion_cmp(&b->assertions[i], assertion);
        if (c >= 0) break;
    }
    if (i < b->assertion_count && elpis_semantic_assertion_is_duplicate(&b->assertions[i], assertion)) {
        return SEMANTIC_BUILDER_E_DUPLICATE;
    }
    if (ensure_capacity((void **)&b->assertions, sizeof(*assertion), &b->assertion_count, &b->assertion_capacity, b->assertion_count + 1) != SEMANTIC_OK)
        return SEMANTIC_BUILDER_E_NOMEM;
    memmove(&b->assertions[i + 1], &b->assertions[i], (b->assertion_count - i) * sizeof(*assertion));
    b->assertions[i] = *assertion;
    b->assertion_count++;
    return SEMANTIC_BUILDER_OK;
}

static int sorted_insert_hyperedge(semantic_hypergraph_builder *b, const elpis_semantic_hyperedge_v1 *edge) {
    uint32_t i;
    for (i = 0; i < b->hyperedge_count; i++) {
        int c = elpis_semantic_hyperedge_cmp(&b->hyperedges[i], edge);
        if (c >= 0) break;
    }
    if (i < b->hyperedge_count && memcmp(b->hyperedges[i].hyperedge_identity.bytes, edge->hyperedge_identity.bytes, HACF_DIGEST_BYTES) == 0) {
        return SEMANTIC_BUILDER_E_DUPLICATE;
    }
    if (ensure_capacity((void **)&b->hyperedges, sizeof(*edge), &b->hyperedge_count, &b->hyperedge_capacity, b->hyperedge_count + 1) != SEMANTIC_OK)
        return SEMANTIC_BUILDER_E_NOMEM;
    memmove(&b->hyperedges[i + 1], &b->hyperedges[i], (b->hyperedge_count - i) * sizeof(*edge));
    b->hyperedges[i] = *edge;
    b->hyperedge_count++;
    return SEMANTIC_BUILDER_OK;
}

static int sorted_insert_incidence(semantic_hypergraph_builder *b, const elpis_semantic_incidence_v1 *incidence) {
    uint32_t i;
    for (i = 0; i < b->incidence_count; i++) {
        int c = elpis_semantic_incidence_cmp(&b->incidences[i], incidence);
        if (c >= 0) break;
    }
    if (i < b->incidence_count && memcmp(b->incidences[i].incidence_identity.bytes, incidence->incidence_identity.bytes, HACF_DIGEST_BYTES) == 0) {
        return SEMANTIC_BUILDER_E_DUPLICATE;
    }
    if (ensure_capacity((void **)&b->incidences, sizeof(*incidence), &b->incidence_count, &b->incidence_capacity, b->incidence_count + 1) != SEMANTIC_OK)
        return SEMANTIC_BUILDER_E_NOMEM;
    memmove(&b->incidences[i + 1], &b->incidences[i], (b->incidence_count - i) * sizeof(*incidence));
    b->incidences[i] = *incidence;
    b->incidence_count++;
    return SEMANTIC_BUILDER_OK;
}

semantic_hypergraph_builder *semantic_builder_create(const semantic_type_registry *reg) {
    if (!reg || !semantic_type_registry_is_sealed(reg)) return NULL;
    semantic_hypergraph_builder *b = calloc(1, sizeof(*b));
    if (!b) return NULL;
    b->registry = reg;
    return b;
}

void semantic_builder_destroy(semantic_hypergraph_builder *b) {
    if (!b) return;
    free(b->nodes);
    free(b->assertions);
    free(b->hyperedges);
    free(b->incidences);
    free(b);
}

int semantic_builder_add_node(semantic_hypergraph_builder *b, const elpis_semantic_node_v1 *node) {
    if (!b || !node) return SEMANTIC_BUILDER_E_INVAL;
    int v = elpis_semantic_node_validate(node);
    if (v != SEMANTIC_OK) return v;
    /* Check type exists in registry. */
    if (!semantic_type_registry_get_node_type(b->registry, node->node_type))
        return SEMANTIC_BUILDER_E_INVAL;
    /* Recompute and verify identity. */
    hacf_digest computed;
    elpis_semantic_node_identity(node, &computed);
    if (memcmp(node->node_identity.bytes, computed.bytes, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_BUILDER_E_IDENTITY;
    int r = sorted_insert_node(b, node);
    return r == SEMANTIC_BUILDER_E_DUPLICATE ? SEMANTIC_BUILDER_OK : r;
}

int semantic_builder_add_assertion(semantic_hypergraph_builder *b, const elpis_semantic_assertion_v1 *assertion) {
    if (!b || !assertion) return SEMANTIC_BUILDER_E_INVAL;
    int v = elpis_semantic_assertion_validate(assertion);
    if (v != SEMANTIC_OK) return v;
    /* Verify the asserted object exists. */
    if (assertion->asserted_object_kind == SEMANTIC_OBJECT_KIND_NODE) {
        if (!semantic_builder_has_node(b, &assertion->asserted_object_digest))
            return SEMANTIC_BUILDER_E_MISSING_NODE;
    } else if (assertion->asserted_object_kind == SEMANTIC_OBJECT_KIND_HYPEREDGE) {
        if (!semantic_builder_has_hyperedge(b, &assertion->asserted_object_digest))
            return SEMANTIC_BUILDER_E_MISSING_EDGE;
    } else {
        return SEMANTIC_BUILDER_E_INVAL;
    }
    /* Recompute and verify identity. */
    hacf_digest computed;
    elpis_semantic_assertion_identity(assertion, &computed);
    if (memcmp(assertion->assertion_identity.bytes, computed.bytes, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_BUILDER_E_IDENTITY;
    int r = sorted_insert_assertion(b, assertion);
    return r == SEMANTIC_BUILDER_E_DUPLICATE ? SEMANTIC_BUILDER_OK : r;
}

int semantic_builder_add_hyperedge(semantic_hypergraph_builder *b, const elpis_semantic_hyperedge_v1 *edge) {
    if (!b || !edge) return SEMANTIC_BUILDER_E_INVAL;
    int v = elpis_semantic_hyperedge_validate(edge);
    if (v != SEMANTIC_OK) return v;
    /* Check type exists. */
    const semantic_hyperedge_type_entry *type = semantic_type_registry_get_hyperedge_type(b->registry, edge->hyperedge_type);
    if (!type) return SEMANTIC_BUILDER_E_INVAL;
    /* Check participant count bounds. */
    if (edge->participant_count < type->min_participants)
        return SEMANTIC_BUILDER_E_PARTICIPANT;
    if (type->max_participants != 0 && edge->participant_count > type->max_participants)
        return SEMANTIC_BUILDER_E_PARTICIPANT;
    /* Validate each participant. */
    for (uint32_t i = 0; i < edge->participant_count; i++) {
        const elpis_semantic_participant_descriptor *p = &edge->participants[i];
        const semantic_role_rule *rule = semantic_type_registry_get_role_rule(b->registry, edge->hyperedge_type, p->incidence_role);
        if (!rule) return SEMANTIC_BUILDER_E_ROLE;
        /* Check node exists. */
        if (!semantic_builder_has_node(b, &p->node_identity))
            return SEMANTIC_BUILDER_E_MISSING_NODE;
    }
    /* Recompute identity (participants must be canonicalized). */
    hacf_digest computed;
    elpis_semantic_hyperedge_identity(edge, &computed);
    if (memcmp(edge->hyperedge_identity.bytes, computed.bytes, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_BUILDER_E_IDENTITY;
    int r = sorted_insert_hyperedge(b, edge);
    return r == SEMANTIC_BUILDER_E_DUPLICATE ? SEMANTIC_BUILDER_OK : r;
}

int semantic_builder_add_incidence(semantic_hypergraph_builder *b, const elpis_semantic_incidence_v1 *incidence) {
    if (!b || !incidence) return SEMANTIC_BUILDER_E_INVAL;
    int v = elpis_semantic_incidence_validate(incidence);
    if (v != SEMANTIC_OK) return v;
    /* Check hyperedge exists. */
    if (!semantic_builder_has_hyperedge(b, &incidence->hyperedge_digest))
        return SEMANTIC_BUILDER_E_MISSING_EDGE;
    /* Check node exists. */
    if (!semantic_builder_has_node(b, &incidence->node_digest))
        return SEMANTIC_BUILDER_E_MISSING_NODE;
    /* Check role is known. */
    if (!semantic_type_registry_get_incidence_role(b->registry, incidence->incidence_role))
        return SEMANTIC_BUILDER_E_ROLE;
    /* Recompute identity. */
    hacf_digest computed;
    elpis_semantic_incidence_identity(incidence, &computed);
    if (memcmp(incidence->incidence_identity.bytes, computed.bytes, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_BUILDER_E_IDENTITY;
    int r = sorted_insert_incidence(b, incidence);
    return r == SEMANTIC_BUILDER_E_DUPLICATE ? SEMANTIC_BUILDER_OK : r;
}

uint32_t semantic_builder_node_count(const semantic_hypergraph_builder *b) {
    return b ? b->node_count : 0;
}

uint32_t semantic_builder_assertion_count(const semantic_hypergraph_builder *b) {
    return b ? b->assertion_count : 0;
}

uint32_t semantic_builder_hyperedge_count(const semantic_hypergraph_builder *b) {
    return b ? b->hyperedge_count : 0;
}

uint32_t semantic_builder_incidence_count(const semantic_hypergraph_builder *b) {
    return b ? b->incidence_count : 0;
}

const elpis_semantic_node_v1 *semantic_builder_get_node(const semantic_hypergraph_builder *b, uint32_t index) {
    if (!b || index >= b->node_count) return NULL;
    return &b->nodes[index];
}

const elpis_semantic_assertion_v1 *semantic_builder_get_assertion(const semantic_hypergraph_builder *b, uint32_t index) {
    if (!b || index >= b->assertion_count) return NULL;
    return &b->assertions[index];
}

const elpis_semantic_hyperedge_v1 *semantic_builder_get_hyperedge(const semantic_hypergraph_builder *b, uint32_t index) {
    if (!b || index >= b->hyperedge_count) return NULL;
    return &b->hyperedges[index];
}

const elpis_semantic_incidence_v1 *semantic_builder_get_incidence(const semantic_hypergraph_builder *b, uint32_t index) {
    if (!b || index >= b->incidence_count) return NULL;
    return &b->incidences[index];
}

int semantic_builder_has_node(const semantic_hypergraph_builder *b, const hacf_digest *digest) {
    if (!b || !digest) return 0;
    for (uint32_t i = 0; i < b->node_count; i++) {
        if (memcmp(b->nodes[i].node_identity.bytes, digest->bytes, HACF_DIGEST_BYTES) == 0)
            return 1;
    }
    return 0;
}

int semantic_builder_has_hyperedge(const semantic_hypergraph_builder *b, const hacf_digest *digest) {
    if (!b || !digest) return 0;
    for (uint32_t i = 0; i < b->hyperedge_count; i++) {
        if (memcmp(b->hyperedges[i].hyperedge_identity.bytes, digest->bytes, HACF_DIGEST_BYTES) == 0)
            return 1;
    }
    return 0;
}
