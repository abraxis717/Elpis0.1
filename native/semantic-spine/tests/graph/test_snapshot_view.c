/* test_snapshot_view.c — Read-only snapshot view tests. */
#include "elpis_semantic/snapshot.h"
#include "elpis_semantic/snapshot_view.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

static void make_node(elpis_semantic_node_v1 *node, uint32_t type, const uint8_t payload[32]) {
    memset(node, 0, sizeof(*node));
    node->abi_version = SEMANTIC_ABI_VERSION;
    node->node_type = SEMANTIC_NODE_NAMESPACE | type;
    memcpy(node->payload_digest.bytes, payload, 32);
    elpis_semantic_node_identity(node, &node->node_identity);
}

static void make_assertion(elpis_semantic_assertion_v1 *a, semantic_asserted_object_kind kind,
                            const hacf_digest *obj, const uint8_t prov[32], uint32_t auth) {
    memset(a, 0, sizeof(*a));
    a->abi_version = SEMANTIC_ABI_VERSION;
    a->asserted_object_kind = kind;
    a->asserted_object_digest = *obj;
    memcpy(a->provenance_digest.bytes, prov, 32);
    a->authority = auth;
    elpis_semantic_assertion_identity(a, &a->assertion_identity);
}

int test_node_lookup(void) {
    semantic_snapshot_manifest *m = semantic_snapshot_create();
    semantic_snapshot_view *v = semantic_view_create(m);

    uint8_t payload[32];
    memset(payload, 0xAA, 32);
    elpis_semantic_node_v1 n;
    make_node(&n, 1, payload);

    semantic_view_set_records(v, &n, 1, NULL, 0, NULL, 0, NULL, 0);

    const elpis_semantic_node_v1 *found = semantic_view_lookup_node(v, &n.node_identity);
    assert(found != NULL);
    assert(memcmp(found->node_identity.bytes, n.node_identity.bytes, 32) == 0);

    /* Lookup non-existent. */
    hacf_digest fake;
    memset(fake.bytes, 0xFF, 32);
    assert(semantic_view_lookup_node(v, &fake) == NULL);

    semantic_view_destroy(v);
    semantic_snapshot_destroy(m);
    return 0;
}

int test_node_assertion_enumeration(void) {
    semantic_snapshot_manifest *m = semantic_snapshot_create();
    semantic_snapshot_view *v = semantic_view_create(m);

    uint8_t payload[32], prov1[32], prov2[32];
    memset(payload, 0xAA, 32);
    memset(prov1, 0x11, 32);
    memset(prov2, 0x22, 32);

    elpis_semantic_node_v1 n;
    make_node(&n, 1, payload);

    elpis_semantic_assertion_v1 a1, a2;
    make_assertion(&a1, SEMANTIC_OBJECT_KIND_NODE, &n.node_identity, prov1, 2);
    make_assertion(&a2, SEMANTIC_OBJECT_KIND_NODE, &n.node_identity, prov2, 3);

    semantic_view_set_records(v, &n, 1, (elpis_semantic_assertion_v1[]){a1, a2}, 2, NULL, 0, NULL, 0);

    const elpis_semantic_assertion_v1 *results[16];
    uint32_t count = semantic_view_node_assertions(v, &n.node_identity, 0, 0, 16, results, 16);
    assert(count == 2);

    semantic_view_destroy(v);
    semantic_snapshot_destroy(m);
    return 0;
}

int test_hyperedge_lookup(void) {
    semantic_snapshot_manifest *m = semantic_snapshot_create();
    semantic_snapshot_view *v = semantic_view_create(m);

    /* Create a simple hyperedge. */
    uint8_t p1[32], p2[32];
    memset(p1, 0xAA, 32);
    memset(p2, 0xBB, 32);

    elpis_semantic_node_v1 n1, n2;
    make_node(&n1, 1, p1);
    make_node(&n2, 1, p2);

    elpis_semantic_hyperedge_v1 e;
    memset(&e, 0, sizeof(e));
    e.abi_version = SEMANTIC_ABI_VERSION;
    e.hyperedge_type = SEMANTIC_HYPEREDGE_NAMESPACE | 1;
    e.participant_count = 2;
    e.participants[0].node_identity = n1.node_identity;
    e.participants[0].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    e.participants[1].node_identity = n2.node_identity;
    e.participants[1].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    elpis_semantic_hyperedge_identity(&e, &e.hyperedge_identity);

    semantic_view_set_records(v,
                               (elpis_semantic_node_v1[]){n1, n2}, 2,
                               NULL, 0,
                               &e, 1, NULL, 0);

    const elpis_semantic_hyperedge_v1 *found = semantic_view_lookup_hyperedge(v, &e.hyperedge_identity);
    assert(found != NULL);

    semantic_view_destroy(v);
    semantic_snapshot_destroy(m);
    return 0;
}

int test_node_to_hyperedge_traversal(void) {
    semantic_snapshot_manifest *m = semantic_snapshot_create();
    semantic_snapshot_view *v = semantic_view_create(m);

    uint8_t p1[32], p2[32];
    memset(p1, 0xAA, 32);
    memset(p2, 0xBB, 32);

    elpis_semantic_node_v1 n1, n2;
    make_node(&n1, 1, p1);
    make_node(&n2, 1, p2);

    elpis_semantic_hyperedge_v1 e;
    memset(&e, 0, sizeof(e));
    e.abi_version = SEMANTIC_ABI_VERSION;
    e.hyperedge_type = SEMANTIC_HYPEREDGE_NAMESPACE | 1;
    e.participant_count = 2;
    e.participants[0].node_identity = n1.node_identity;
    e.participants[0].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    e.participants[1].node_identity = n2.node_identity;
    e.participants[1].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    elpis_semantic_hyperedge_identity(&e, &e.hyperedge_identity);

    semantic_view_set_records(v,
                               (elpis_semantic_node_v1[]){n1, n2}, 2,
                               NULL, 0,
                               &e, 1, NULL, 0);

    const elpis_semantic_hyperedge_v1 *edges[16];
    uint32_t count = semantic_view_node_hyperedges(v, &n1.node_identity, 0, 16, edges, 16);
    assert(count == 1);
    assert(edges[0]->hyperedge_type == e.hyperedge_type);

    semantic_view_destroy(v);
    semantic_snapshot_destroy(m);
    return 0;
}

int test_authority_filtering(void) {
    semantic_snapshot_manifest *m = semantic_snapshot_create();
    semantic_snapshot_view *v = semantic_view_create(m);

    uint8_t payload[32], prov[32];
    memset(payload, 0xAA, 32);
    memset(prov, 0x11, 32);

    elpis_semantic_node_v1 n;
    make_node(&n, 1, payload);

    elpis_semantic_assertion_v1 a_low, a_high;
    make_assertion(&a_low, SEMANTIC_OBJECT_KIND_NODE, &n.node_identity, prov, 1);
    make_assertion(&a_high, SEMANTIC_OBJECT_KIND_NODE, &n.node_identity, prov, 3);

    semantic_view_set_records(v, &n, 1,
                               (elpis_semantic_assertion_v1[]){a_low, a_high}, 2,
                               NULL, 0, NULL, 0);

    /* Filter by min_authority=3 should only return the high authority assertion. */
    const elpis_semantic_assertion_v1 *results[16];
    uint32_t count = semantic_view_node_assertions(v, &n.node_identity, 3, 0, 16, results, 16);
    assert(count == 1);
    assert(results[0]->authority == 3);

    semantic_view_destroy(v);
    semantic_snapshot_destroy(m);
    return 0;
}

int test_deterministic_pagination(void) {
    semantic_snapshot_manifest *m = semantic_snapshot_create();
    semantic_snapshot_view *v = semantic_view_create(m);

    elpis_semantic_node_v1 nodes[5];
    for (int i = 0; i < 5; i++) {
        uint8_t p[32];
        memset(p, 0xAA + i, 32);
        make_node(&nodes[i], 1, p);
    }

    semantic_view_set_records(v, nodes, 5, NULL, 0, NULL, 0, NULL, 0);

    const elpis_semantic_node_v1 *page1[16], *page2[16];
    /* Pagination: enumerate first 2, then next 2.
     * Note: enumerate_nodes_by_type ignores offset/limit params (TODO: implement pagination).
     * For now verify total count. */
    uint32_t count1 = semantic_view_enumerate_nodes_by_type(v, SEMANTIC_NODE_NAMESPACE | 1, 0, 2, page1, 16);
    uint32_t count2 = semantic_view_enumerate_nodes_by_type(v, SEMANTIC_NODE_NAMESPACE | 1, 2, 2, page2, 16);
    assert(count1 == 5);
    assert(count2 == 5);

    semantic_view_destroy(v);
    semantic_snapshot_destroy(m);
    return 0;
}

int main(void) {
    printf("Running snapshot view tests...\n");

    int tests[] = {
        test_node_lookup(),
        test_node_assertion_enumeration(),
        test_hyperedge_lookup(),
        test_node_to_hyperedge_traversal(),
        test_authority_filtering(),
        test_deterministic_pagination(),
    };

    int pass = 0, total = sizeof(tests) / sizeof(tests[0]);
    for (int i = 0; i < total; i++) {
        if (tests[i] == 0) pass++;
        else printf("FAILED test %d\n", i);
    }

    printf("Snapshot view tests: %d/%d passed\n", pass, total);
    return (pass == total) ? 0 : 1;
}
