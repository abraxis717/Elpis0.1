/* hacf_mapping.c — Exact mapping from semantic records to HACF graph operations.
 *
 * Mapping rules:
 *   Semantic node assertion  → HACF_GRAPH_ADD_NODE (subject=node_identity, object=zero)
 *   Semantic hyperedge assertion → HACF_GRAPH_ADD_NODE (subject=hyperedge_identity, object=zero)
 *   Incidence                → HACF_GRAPH_ADD_EDGE (subject=hyperedge_identity, object=node_identity)
 *
 * Canonical HACF operation order:
 *   1. Node ADD_NODE operations
 *   2. Hyperedge ADD_NODE operations
 *   3. Incidence ADD_EDGE operations
 *   Within each class, sorted by complete serialized operation tuple.
 */
#include "elpis_semantic/hypergraph.h"
#include "builder_internal.h"
#include "elpis/graph.h"
#include "elpis/sha256.h"
#include <stdlib.h>
#include <string.h>

#define SEMANTIC_MAX_HACF_OPS 65536u

static hacf_digest zero_digest(void) {
    hacf_digest z;
    memset(z.bytes, 0, HACF_DIGEST_BYTES);
    return z;
}

/* Compare two HACF ops for canonical ordering.
 * Order: (type, subject, object, node_or_edge_type, provenance, authority) */
static int hacf_op_cmp(const void *pa, const void *pb) {
    const hacf_graph_op *a = (const hacf_graph_op *)pa;
    const hacf_graph_op *b = (const hacf_graph_op *)pb;
    uint32_t be_a = a->type, be_b = b->type;
    int c = memcmp(&be_a, &be_b, 4);
    if (c) return c;
    c = memcmp(a->subject.bytes, b->subject.bytes, HACF_DIGEST_BYTES);
    if (c) return c;
    c = memcmp(a->object.bytes, b->object.bytes, HACF_DIGEST_BYTES);
    if (c) return c;
    be_a = a->node_or_edge_type; be_b = b->node_or_edge_type;
    c = memcmp(&be_a, &be_b, 4);
    if (c) return c;
    c = memcmp(a->provenance.bytes, b->provenance.bytes, HACF_DIGEST_BYTES);
    if (c) return c;
    be_a = a->authority; be_b = b->authority;
    return memcmp(&be_a, &be_b, 4);
}

/* Map builder records to HACF operations. Caller owns the returned array and
 * must free it. Returns SEMANTIC_OK on success.
 *
 * Provenance multiplicity policy: when a hyperedge has multiple assertions,
 * emit one incidence operation per distinct hyperedge assertion (subject to
 * segment policy). Provenance is never silently discarded. */
int semantic_map_to_hacf_ops(const semantic_hypergraph_builder *builder,
                               hacf_graph_op **ops_out, uint32_t *op_count_out) {
    if (!builder || !ops_out || !op_count_out) return SEMANTIC_E_INVAL;

    /* Calculate total ops needed:
     * Each node assertion → 1 ADD_NODE
     * Each hyperedge assertion → 1 ADD_NODE
     * Each incidence → 1 ADD_EDGE (one per assertion's provenance)
     */
    uint32_t node_assertions = 0;
    uint32_t hyperedge_assertions = 0;

    for (uint32_t i = 0; i < builder->assertion_count; i++) {
        const elpis_semantic_assertion_v1 *a = &builder->assertions[i];
        if (a->asserted_object_kind == SEMANTIC_OBJECT_KIND_NODE) node_assertions++;
        else if (a->asserted_object_kind == SEMANTIC_OBJECT_KIND_HYPEREDGE) hyperedge_assertions++;
    }

    uint32_t total_ops = node_assertions + hyperedge_assertions + builder->incidence_count;
    if (total_ops == 0) {
        *ops_out = NULL;
        *op_count_out = 0;
        return SEMANTIC_OK;
    }
    if (total_ops > SEMANTIC_MAX_HACF_OPS) return SEMANTIC_E_NOMEM;

    hacf_graph_op *ops = calloc(total_ops, sizeof(hacf_graph_op));
    if (!ops) return SEMANTIC_E_NOMEM;

    uint32_t idx = 0;
    hacf_digest zd = zero_digest();

    /* Map node assertions. */
    for (uint32_t i = 0; i < builder->assertion_count; i++) {
        const elpis_semantic_assertion_v1 *a = &builder->assertions[i];
        if (a->asserted_object_kind != SEMANTIC_OBJECT_KIND_NODE) continue;

        /* Find the node type. */
        uint32_t node_type = 0;
        for (uint32_t j = 0; j < builder->node_count; j++) {
            const elpis_semantic_node_v1 *n = &builder->nodes[j];
            if (memcmp(n->node_identity.bytes, a->asserted_object_digest.bytes, HACF_DIGEST_BYTES) == 0) {
                node_type = n->node_type;
                break;
            }
        }

        ops[idx].type = HACF_GRAPH_ADD_NODE;
        ops[idx].subject = a->asserted_object_digest;
        ops[idx].object = zd;
        ops[idx].node_or_edge_type = node_type;
        ops[idx].provenance = a->provenance_digest;
        ops[idx].authority = a->authority;
        idx++;
    }

    /* Map hyperedge assertions. */
    for (uint32_t i = 0; i < builder->assertion_count; i++) {
        const elpis_semantic_assertion_v1 *a = &builder->assertions[i];
        if (a->asserted_object_kind != SEMANTIC_OBJECT_KIND_HYPEREDGE) continue;

        uint32_t edge_type = 0;
        for (uint32_t j = 0; j < builder->hyperedge_count; j++) {
            const elpis_semantic_hyperedge_v1 *e = &builder->hyperedges[j];
            if (memcmp(e->hyperedge_identity.bytes, a->asserted_object_digest.bytes, HACF_DIGEST_BYTES) == 0) {
                edge_type = e->hyperedge_type;
                break;
            }
        }

        ops[idx].type = HACF_GRAPH_ADD_NODE;
        ops[idx].subject = a->asserted_object_digest;
        ops[idx].object = zd;
        ops[idx].node_or_edge_type = edge_type;
        ops[idx].provenance = a->provenance_digest;
        ops[idx].authority = a->authority;
        idx++;
    }

    /* Map incidences — one per incidence record, inheriting provenance from
     * the associated hyperedge assertion. For P0, use the first matching
     * hyperedge assertion's provenance. If multiple exist, emit one incidence
     * per distinct provenance (provenance multiplicity policy). */
    for (uint32_t i = 0; i < builder->incidence_count; i++) {
        const elpis_semantic_incidence_v1 *inc = &builder->incidences[i];

        /* Find the associated hyperedge assertion(s). */
        for (uint32_t a = 0; a < builder->assertion_count; a++) {
            const elpis_semantic_assertion_v1 *asrt = &builder->assertions[a];
            if (asrt->asserted_object_kind != SEMANTIC_OBJECT_KIND_HYPEREDGE) continue;
            if (memcmp(asrt->asserted_object_digest.bytes, inc->hyperedge_digest.bytes, HACF_DIGEST_BYTES) != 0)
                continue;

            /* Find the incidence role for this hyperedge. */
            uint32_t edge_type = 0;
            for (uint32_t j = 0; j < builder->hyperedge_count; j++) {
                const elpis_semantic_hyperedge_v1 *e = &builder->hyperedges[j];
                if (memcmp(e->hyperedge_identity.bytes, inc->hyperedge_digest.bytes, HACF_DIGEST_BYTES) == 0) {
                    edge_type = e->hyperedge_type;
                    break;
                }
            }

            ops[idx].type = HACF_GRAPH_ADD_EDGE;
            ops[idx].subject = inc->hyperedge_digest;
            ops[idx].object = inc->node_digest;
            ops[idx].node_or_edge_type = inc->incidence_role;
            ops[idx].provenance = asrt->provenance_digest;
            ops[idx].authority = asrt->authority;
            idx++;
        }
    }

    /* Canonical sort: within each op type class, by complete tuple. */
    qsort(ops, idx, sizeof(hacf_graph_op), hacf_op_cmp);

    *ops_out = ops;
    *op_count_out = idx;
    return SEMANTIC_OK;
}

/* Free HACF ops array. */
void semantic_free_hacf_ops(hacf_graph_op *ops) {
    free(ops);
}

/* Compute HACF graph delta and next snapshot from operations.
 * prior_snapshot: for genesis, use genesis identity. */
int semantic_compute_hacf_delta(const hacf_digest *prior_snapshot,
                                 const hacf_graph_op *ops, uint32_t op_count,
                                 hacf_digest *delta_digest_out,
                                 hacf_digest *next_snapshot_out) {
    if (!prior_snapshot) return SEMANTIC_E_INVAL;
    hacf_digest delta, next;
    int r = hacf_graph_delta_digest(prior_snapshot, ops, op_count, &delta, &next);
    if (r != 0) return SEMANTIC_E_INVAL;
    if (delta_digest_out) *delta_digest_out = delta;
    if (next_snapshot_out) *next_snapshot_out = next;
    return SEMANTIC_OK;
}
