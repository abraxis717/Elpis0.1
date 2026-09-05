#include "elpis_semantic/hypergraph.h"
#include "elpis_semantic/type_registry.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NODE_T (SEMANTIC_NODE_NAMESPACE | 1u)
#define EDGE_T (SEMANTIC_HYPEREDGE_NAMESPACE | 1u)
#define ROLE_T (SEMANTIC_INCIDENCE_NAMESPACE | 1u)

static void dtext(const char *s, hacf_digest *d) {
    elpis_sha256(s, strlen(s), d->bytes);
}

static semantic_type_registry *registry_make(void) {
    semantic_type_registry *reg = semantic_type_registry_create();
    assert(reg != NULL);

    semantic_incidence_role_entry role;
    memset(&role, 0, sizeof role);
    role.incidence_role = ROLE_T;
    role.participant_flag_mask = SEMANTIC_PARTICIPANT_FLAG_MASK;
    assert(semantic_type_registry_add_incidence_role(reg, &role) == SEMANTIC_OK);

    semantic_node_type_entry node;
    memset(&node, 0, sizeof node);
    node.node_type = NODE_T;
    node.semantic_flag_mask = SEMANTIC_NODE_FLAG_MASK;
    node.min_authority = 0;
    node.max_authority = 3;
    assert(semantic_type_registry_add_node_type(reg, &node) == SEMANTIC_OK);

    semantic_role_rule rr;
    memset(&rr, 0, sizeof rr);
    rr.incidence_role = ROLE_T;
    rr.min_cardinality = 0;
    rr.max_cardinality = 8;
    rr.is_ordered = 1;
    rr.allows_repeat = 0;

    semantic_hyperedge_type_entry edge;
    memset(&edge, 0, sizeof edge);
    edge.hyperedge_type = EDGE_T;
    edge.min_participants = 0;
    edge.max_participants = 8;
    edge.role_count = 1;
    edge.roles[0] = rr;
    assert(semantic_type_registry_add_hyperedge_type(reg, &edge) == SEMANTIC_OK);

    assert(semantic_type_registry_seal(reg, NULL) == SEMANTIC_OK);
    return reg;
}

static void node_make(const char *payload, elpis_semantic_node_v1 *n) {
    memset(n, 0, sizeof *n);
    n->abi_version = SEMANTIC_ABI_VERSION;
    n->node_type = NODE_T;
    n->semantic_flags = SEMANTIC_NODE_FLAG_EXTERNAL;
    dtext(payload, &n->payload_digest);
    assert(elpis_semantic_node_identity(n, &n->node_identity) == SEMANTIC_OK);
}

static void assertion_make(const hacf_digest *obj, const char *prov,
                           elpis_semantic_assertion_v1 *a) {
    memset(a, 0, sizeof *a);
    a->abi_version = SEMANTIC_ABI_VERSION;
    a->asserted_object_kind = SEMANTIC_OBJECT_KIND_NODE;
    a->asserted_object_digest = *obj;
    dtext(prov, &a->provenance_digest);
    a->authority = 0;
    assert(elpis_semantic_assertion_identity(a, &a->assertion_identity) == SEMANTIC_OK);
}

static void edge_make(const char *payload, elpis_semantic_hyperedge_v1 *e) {
    memset(e, 0, sizeof *e);
    e->abi_version = SEMANTIC_ABI_VERSION;
    e->hyperedge_type = EDGE_T;
    dtext(payload, &e->payload_digest);
    e->participant_count = 0;
    assert(elpis_semantic_hyperedge_identity(e, &e->hyperedge_identity) == SEMANTIC_OK);
}

static void incidence_make(const hacf_digest *edge, const hacf_digest *node,
                           uint32_t ordinal, elpis_semantic_incidence_v1 *i) {
    memset(i, 0, sizeof *i);
    i->abi_version = SEMANTIC_ABI_VERSION;
    i->hyperedge_digest = *edge;
    i->node_digest = *node;
    i->incidence_role = ROLE_T;
    i->ordinal = ordinal;
    assert(elpis_semantic_incidence_identity(i, &i->incidence_identity) == SEMANTIC_OK);
}

int main(void) {
    semantic_type_registry *reg = registry_make();
    semantic_hypergraph_builder *b = semantic_builder_create(reg);
    assert(b != NULL);

    elpis_semantic_node_v1 n1, n2;
    node_make("alpha", &n1);
    node_make("beta", &n2);

    /* Arbitrary insertion must become canonical output. */
    assert(semantic_builder_add_node(b, &n2) == SEMANTIC_BUILDER_OK);
    assert(semantic_builder_add_node(b, &n1) == SEMANTIC_BUILDER_OK);
    assert(semantic_builder_node_count(b) == 2);
    assert(elpis_semantic_node_cmp(semantic_builder_get_node(b,0),
                                   semantic_builder_get_node(b,1)) < 0);

    /* Exact duplicate collapses. */
    assert(semantic_builder_add_node(b, &n1) == SEMANTIC_BUILDER_OK);
    assert(semantic_builder_node_count(b) == 2);

    elpis_semantic_assertion_v1 a1, a2;
    assertion_make(&n1.node_identity, "prov-z", &a1);
    assertion_make(&n2.node_identity, "prov-a", &a2);
    assert(semantic_builder_add_assertion(b, &a1) == SEMANTIC_BUILDER_OK);
    assert(semantic_builder_add_assertion(b, &a2) == SEMANTIC_BUILDER_OK);
    assert(semantic_builder_assertion_count(b) == 2);
    assert(elpis_semantic_assertion_cmp(semantic_builder_get_assertion(b,0),
                                        semantic_builder_get_assertion(b,1)) < 0);

    elpis_semantic_hyperedge_v1 e1, e2;
    edge_make("edge-z", &e1);
    edge_make("edge-a", &e2);
    assert(semantic_builder_add_hyperedge(b, &e1) == SEMANTIC_BUILDER_OK);
    assert(semantic_builder_add_hyperedge(b, &e2) == SEMANTIC_BUILDER_OK);
    assert(semantic_builder_hyperedge_count(b) == 2);
    assert(elpis_semantic_hyperedge_cmp(semantic_builder_get_hyperedge(b,0),
                                        semantic_builder_get_hyperedge(b,1)) < 0);

    elpis_semantic_incidence_v1 i1, i2;
    incidence_make(&e1.hyperedge_identity, &n1.node_identity, 1, &i1);
    incidence_make(&e1.hyperedge_identity, &n2.node_identity, 0, &i2);
    assert(semantic_builder_add_incidence(b, &i1) == SEMANTIC_BUILDER_OK);
    assert(semantic_builder_add_incidence(b, &i2) == SEMANTIC_BUILDER_OK);
    assert(semantic_builder_incidence_count(b) == 2);
    assert(elpis_semantic_incidence_cmp(semantic_builder_get_incidence(b,0),
                                        semantic_builder_get_incidence(b,1)) < 0);

    puts("PASS_HYPERGRAPH_BUILDER_PUBLIC_CONTRACT");
    semantic_builder_destroy(b);
    semantic_type_registry_destroy(reg);
    return 0;
}
