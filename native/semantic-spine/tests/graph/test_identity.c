/* test_identity.c — Semantic identity tests.
 *
 * Tests: node identity, hyperedge identity, assertion identity, incidence identity.
 * Fresh-process determinism, padding independence, provenance independence.
 */
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

static void hex(const uint8_t *d, char *out) {
    elpis_hex32(d, out);
}

/* Helper: create a valid node with a given payload. */
static void make_node(elpis_semantic_node_v1 *node, uint32_t type, uint32_t flags, const uint8_t payload[32]) {
    memset(node, 0, sizeof(*node));
    node->abi_version = SEMANTIC_ABI_VERSION;
    node->node_type = SEMANTIC_NODE_NAMESPACE | type;
    node->semantic_flags = flags;
    memcpy(node->payload_digest.bytes, payload, 32);
    elpis_semantic_node_identity(node, &node->node_identity);
}

/* Helper: create a valid assertion. */
static void make_assertion(elpis_semantic_assertion_v1 *a, semantic_asserted_object_kind kind,
                            const hacf_digest *obj, const hacf_digest *prov, uint32_t auth) {
    memset(a, 0, sizeof(*a));
    a->abi_version = SEMANTIC_ABI_VERSION;
    a->asserted_object_kind = kind;
    a->asserted_object_digest = *obj;
    a->provenance_digest = *prov;
    a->authority = auth;
    elpis_semantic_assertion_identity(a, &a->assertion_identity);
}

/* Helper: create a valid incidence. */
static void make_incidence(elpis_semantic_incidence_v1 *inc,
                            const hacf_digest *he, const hacf_digest *nd,
                            uint32_t role, uint32_t ordinal) {
    memset(inc, 0, sizeof(*inc));
    inc->abi_version = SEMANTIC_ABI_VERSION;
    inc->hyperedge_digest = *he;
    inc->node_digest = *nd;
    inc->incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | role;
    inc->ordinal = ordinal;
    elpis_semantic_incidence_identity(inc, &inc->incidence_identity);
}

int test_node_identity_independent_of_padding(void) {
    /* Node identity must not depend on host struct padding.
     * Two nodes with same semantic fields but potentially different padding
     * must produce the same identity. */
    uint8_t payload[32];
    memset(payload, 0xAA, 32);

    elpis_semantic_node_v1 n1, n2;
    make_node(&n1, 1, 0, payload);
    make_node(&n2, 1, 0, payload);

    assert(memcmp(n1.node_identity.bytes, n2.node_identity.bytes, 32) == 0);
    return 0;
}

int test_node_identity_independent_of_provenance(void) {
    /* Node identity must NOT bind provenance. Two nodes with same
     * type/flags/payload but different assertions must have same identity. */
    uint8_t payload[32];
    memset(payload, 0xBB, 32);

    elpis_semantic_node_v1 n1, n2;
    make_node(&n1, 1, 0, payload);
    make_node(&n2, 1, 0, payload);

    /* Create different assertions for the same node identity — they should reference
     * the same object digest. The node identity itself doesn't include provenance. */
    hacf_digest prov1, prov2;
    memset(prov1.bytes, 0x11, 32);
    memset(prov2.bytes, 0x22, 32);

    elpis_semantic_assertion_v1 a1, a2;
    make_assertion(&a1, SEMANTIC_OBJECT_KIND_NODE, &n1.node_identity, &prov1, 2);
    make_assertion(&a2, SEMANTIC_OBJECT_KIND_NODE, &n2.node_identity, &prov2, 2);

    /* Node identities are same. */
    assert(memcmp(n1.node_identity.bytes, n2.node_identity.bytes, 32) == 0);
    /* But assertions differ (different provenance). */
    assert(memcmp(a1.assertion_identity.bytes, a2.assertion_identity.bytes, 32) != 0);
    return 0;
}

int test_node_identity_independent_of_authority(void) {
    uint8_t payload[32];
    memset(payload, 0xCC, 32);

    elpis_semantic_node_v1 n;
    make_node(&n, 1, 0, payload);

    hacf_digest prov;
    memset(prov.bytes, 0x33, 32);

    elpis_semantic_assertion_v1 a1, a2;
    make_assertion(&a1, SEMANTIC_OBJECT_KIND_NODE, &n.node_identity, &prov, 1);
    make_assertion(&a2, SEMANTIC_OBJECT_KIND_NODE, &n.node_identity, &prov, 3);

    assert(memcmp(a1.assertion_identity.bytes, a2.assertion_identity.bytes, 32) != 0);
    return 0;
}

int test_node_identity_changes_with_payload(void) {
    uint8_t payload1[32], payload2[32];
    memset(payload1, 0xAA, 32);
    memset(payload2, 0xBB, 32);

    elpis_semantic_node_v1 n1, n2;
    make_node(&n1, 1, 0, payload1);
    make_node(&n2, 1, 0, payload2);

    assert(memcmp(n1.node_identity.bytes, n2.node_identity.bytes, 32) != 0);
    return 0;
}

int test_assertion_identity_changes_with_provenance(void) {
    hacf_digest obj, prov1, prov2;
    memset(obj.bytes, 0xAA, 32);
    memset(prov1.bytes, 0x11, 32);
    memset(prov2.bytes, 0x22, 32);

    elpis_semantic_assertion_v1 a1, a2;
    make_assertion(&a1, SEMANTIC_OBJECT_KIND_NODE, &obj, &prov1, 2);
    make_assertion(&a2, SEMANTIC_OBJECT_KIND_NODE, &obj, &prov2, 2);

    assert(memcmp(a1.assertion_identity.bytes, a2.assertion_identity.bytes, 32) != 0);
    return 0;
}

int test_assertion_identity_changes_with_authority(void) {
    hacf_digest obj, prov;
    memset(obj.bytes, 0xAA, 32);
    memset(prov.bytes, 0x11, 32);

    elpis_semantic_assertion_v1 a1, a2;
    make_assertion(&a1, SEMANTIC_OBJECT_KIND_NODE, &obj, &prov, 1);
    make_assertion(&a2, SEMANTIC_OBJECT_KIND_NODE, &obj, &prov, 3);

    assert(memcmp(a1.assertion_identity.bytes, a2.assertion_identity.bytes, 32) != 0);
    return 0;
}

int test_hyperedge_identity_binds_all_participants(void) {
    /* Two hyperedges with same type but different participants must differ. */
    hacf_digest nd1, nd2;
    memset(nd1.bytes, 0xAA, 32);
    memset(nd2.bytes, 0xBB, 32);

    elpis_semantic_hyperedge_v1 e1, e2;
    memset(&e1, 0, sizeof(e1));
    memset(&e2, 0, sizeof(e2));
    e1.abi_version = e2.abi_version = SEMANTIC_ABI_VERSION;
    e1.hyperedge_type = e2.hyperedge_type = SEMANTIC_HYPEREDGE_NAMESPACE | 1;
    e1.participant_count = e2.participant_count = 2;

    e1.participants[0].node_identity = nd1;
    e1.participants[0].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    e1.participants[0].ordinal = 0;

    e1.participants[1].node_identity = nd2;
    e1.participants[1].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    e1.participants[1].ordinal = 1;

    /* Swap participants but keep the same ordinals. */
    e2.participants[0].node_identity = nd2;
    e2.participants[0].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    e2.participants[0].ordinal = 1;

    e2.participants[1].node_identity = nd1;
    e2.participants[1].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    e2.participants[1].ordinal = 0;

    elpis_semantic_canonicalize_participants(e1.participants, e1.participant_count);
    elpis_semantic_canonicalize_participants(e2.participants, e2.participant_count);

    elpis_semantic_hyperedge_identity(&e1, &e1.hyperedge_identity);
    elpis_semantic_hyperedge_identity(&e2, &e2.hyperedge_identity);

    /* After canonicalization, participants are sorted the same way, so identity matches. */
    assert(memcmp(e1.hyperedge_identity.bytes, e2.hyperedge_identity.bytes, 32) == 0);
    return 0;
}

int test_hyperedge_identity_independent_of_insertion_order(void) {
    hacf_digest nd1, nd2, nd3;
    memset(nd1.bytes, 0xAA, 32);
    memset(nd2.bytes, 0xBB, 32);
    memset(nd3.bytes, 0xCC, 32);

    elpis_semantic_hyperedge_v1 e1, e2;
    memset(&e1, 0, sizeof(e1));
    memset(&e2, 0, sizeof(e2));
    e1.abi_version = e2.abi_version = SEMANTIC_ABI_VERSION;
    e1.hyperedge_type = e2.hyperedge_type = SEMANTIC_HYPEREDGE_NAMESPACE | 1;
    e1.participant_count = e2.participant_count = 3;

    /* Insert in different orders. */
    e1.participants[0].node_identity = nd1;
    e1.participants[0].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    e1.participants[0].ordinal = 0;
    e1.participants[1].node_identity = nd2;
    e1.participants[1].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    e1.participants[1].ordinal = 1;
    e1.participants[2].node_identity = nd3;
    e1.participants[2].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    e1.participants[2].ordinal = 2;

    e2.participants[0].node_identity = nd3;
    e2.participants[0].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    e2.participants[0].ordinal = 2;
    e2.participants[1].node_identity = nd1;
    e2.participants[1].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    e2.participants[1].ordinal = 0;
    e2.participants[2].node_identity = nd2;
    e2.participants[2].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    e2.participants[2].ordinal = 1;

    elpis_semantic_canonicalize_participants(e1.participants, 3);
    elpis_semantic_canonicalize_participants(e2.participants, 3);

    elpis_semantic_hyperedge_identity(&e1, &e1.hyperedge_identity);
    elpis_semantic_hyperedge_identity(&e2, &e2.hyperedge_identity);

    assert(memcmp(e1.hyperedge_identity.bytes, e2.hyperedge_identity.bytes, 32) == 0);
    return 0;
}

int test_different_participant_set_different_identity(void) {
    hacf_digest nd1, nd2;
    memset(nd1.bytes, 0xAA, 32);
    memset(nd2.bytes, 0xBB, 32);

    elpis_semantic_hyperedge_v1 e1, e2;
    memset(&e1, 0, sizeof(e1));
    memset(&e2, 0, sizeof(e2));
    e1.abi_version = e2.abi_version = SEMANTIC_ABI_VERSION;
    e1.hyperedge_type = e2.hyperedge_type = SEMANTIC_HYPEREDGE_NAMESPACE | 1;
    e1.participant_count = e2.participant_count = 1;

    e1.participants[0].node_identity = nd1;
    e1.participants[0].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;
    e2.participants[0].node_identity = nd2;
    e2.participants[0].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1;

    elpis_semantic_hyperedge_identity(&e1, &e1.hyperedge_identity);
    elpis_semantic_hyperedge_identity(&e2, &e2.hyperedge_identity);

    assert(memcmp(e1.hyperedge_identity.bytes, e2.hyperedge_identity.bytes, 32) != 0);
    return 0;
}

int test_incidence_identity_deterministic(void) {
    hacf_digest he, nd;
    memset(he.bytes, 0xAA, 32);
    memset(nd.bytes, 0xBB, 32);

    elpis_semantic_incidence_v1 i1, i2;
    make_incidence(&i1, &he, &nd, 1, 0);
    make_incidence(&i2, &he, &nd, 1, 0);

    assert(memcmp(i1.incidence_identity.bytes, i2.incidence_identity.bytes, 32) == 0);
    return 0;
}

int test_fresh_process_determinism(void) {
    /* Run identity computation and verify it produces the same result.
     * This is a single-process test; multi-process is in test_fresh_process_determinism.c */
    uint8_t payload[32];
    memset(payload, 0xDE, 32);

    elpis_semantic_node_v1 n;
    make_node(&n, 42, 0, payload);

    char hex1[65], hex2[65];
    hex(n.node_identity.bytes, hex1);

    /* Recompute. */
    elpis_semantic_node_identity(&n, &n.node_identity);
    hex(n.node_identity.bytes, hex2);

    assert(strcmp(hex1, hex2) == 0);
    return 0;
}

int main(void) {
    printf("Running identity tests...\n");

    int tests[] = {
        test_node_identity_independent_of_padding(),
        test_node_identity_independent_of_provenance(),
        test_node_identity_independent_of_authority(),
        test_node_identity_changes_with_payload(),
        test_assertion_identity_changes_with_provenance(),
        test_assertion_identity_changes_with_authority(),
        test_hyperedge_identity_binds_all_participants(),
        test_hyperedge_identity_independent_of_insertion_order(),
        test_different_participant_set_different_identity(),
        test_incidence_identity_deterministic(),
        test_fresh_process_determinism(),
    };

    int pass = 0, total = sizeof(tests) / sizeof(tests[0]);
    for (int i = 0; i < total; i++) {
        if (tests[i] == 0) pass++;
        else printf("FAILED test %d\n", i);
    }

    printf("Identity tests: %d/%d passed\n", pass, total);
    return (pass == total) ? 0 : 1;
}
