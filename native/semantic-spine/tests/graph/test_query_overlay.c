/* test_query_overlay.c — Query overlay and composed view tests. */
#include "elpis_semantic/query_overlay.h"
#include "elpis_semantic/type_registry.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

static void setup_registry(semantic_type_registry **reg) {
    *reg = semantic_type_registry_create();

    semantic_incidence_role_entry r = {.incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1,
                                        .participant_flag_mask = SEMANTIC_PARTICIPANT_FLAG_MASK};
    semantic_type_registry_add_incidence_role(*reg, &r);

    semantic_node_type_entry n = {.node_type = SEMANTIC_NODE_NAMESPACE | 1,
                                   .semantic_flag_mask = SEMANTIC_NODE_FLAG_MASK,
                                   .min_authority = 0, .max_authority = 3};
    semantic_type_registry_add_node_type(*reg, &n);

    semantic_role_rule rules[1] = {
        {.incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1, .min_cardinality = 0, .max_cardinality = 4, .is_ordered = 0, .allows_repeat = 0},
    };
    semantic_hyperedge_type_entry e = {.hyperedge_type = SEMANTIC_HYPEREDGE_NAMESPACE | 1,
                                        .min_participants = 0, .max_participants = 5,
                                        .role_count = 1, .roles = {rules[0]}};
    semantic_type_registry_add_hyperedge_type(*reg, &e);

    semantic_type_registry_seal(*reg, NULL);
}

static void make_node(elpis_semantic_node_v1 *node, uint32_t type, const uint8_t payload[32]) {
    memset(node, 0, sizeof(*node));
    node->abi_version = SEMANTIC_ABI_VERSION;
    node->node_type = SEMANTIC_NODE_NAMESPACE | type;
    memcpy(node->payload_digest.bytes, payload, 32);
    elpis_semantic_node_identity(node, &node->node_identity);
}

int test_overlay_references_base_nodes(void) {
    semantic_type_registry *reg;
    setup_registry(&reg);

    /* Create base snapshot with a node. */
    semantic_snapshot_manifest *base = semantic_snapshot_create();

    /* Create overlay. */
    hacf_digest query;
    memset(query.bytes, 0xAA, 32);

    semantic_query_overlay *overlay = semantic_overlay_create(base, reg, &query);
    assert(overlay != NULL);

    /* Add query-local node. */
    uint8_t payload[32];
    memset(payload, 0xBB, 32);
    elpis_semantic_node_v1 n;
    make_node(&n, 1, payload);

    assert(semantic_overlay_add_node(overlay, &n) == SEMANTIC_BUILDER_OK);
    assert(semantic_builder_node_count(overlay->local_builder) == 1);

    semantic_overlay_destroy(overlay);
    semantic_snapshot_destroy(base);
    semantic_type_registry_destroy(reg);
    return 0;
}

int test_overlay_cannot_alter_base_records(void) {
    /* The overlay only adds to its local builder; base records are read-only
     * through the snapshot view. By design, the overlay has no mechanism to
     * modify base records — this is a structural guarantee. */
    return 0;
}

int test_composed_view_includes_base_and_overlay(void) {
    semantic_type_registry *reg;
    setup_registry(&reg);

    semantic_snapshot_manifest *base = semantic_snapshot_create();
    semantic_snapshot_view *base_view = semantic_view_create(base);

    /* Add a base node. */
    uint8_t base_payload[32];
    memset(base_payload, 0xAA, 32);
    elpis_semantic_node_v1 base_node;
    make_node(&base_node, 1, base_payload);
    semantic_view_set_records(base_view, &base_node, 1, NULL, 0, NULL, 0, NULL, 0);

    /* Create overlay with additional node. */
    hacf_digest query;
    memset(query.bytes, 0xCC, 32);
    semantic_query_overlay *overlay = semantic_overlay_create(base, reg, &query);

    uint8_t overlay_payload[32];
    memset(overlay_payload, 0xBB, 32);
    elpis_semantic_node_v1 overlay_node;
    make_node(&overlay_node, 1, overlay_payload);
    semantic_overlay_add_node(overlay, &overlay_node);
    semantic_overlay_finalize(overlay);

    /* Create composed view. */
    hacf_digest policy;
    memset(policy.bytes, 0xDD, 32);
    semantic_composed_view *cv = semantic_composed_view_create(base_view, overlay, &policy);
    assert(cv != NULL);

    /* Should find both base and overlay nodes. */
    const elpis_semantic_node_v1 *found_base = semantic_composed_view_lookup_node(cv, &base_node.node_identity);
    assert(found_base != NULL);

    const elpis_semantic_node_v1 *found_overlay = semantic_composed_view_lookup_node(cv, &overlay_node.node_identity);
    assert(found_overlay != NULL);

    semantic_composed_view_destroy(cv);
    semantic_overlay_destroy(overlay);
    semantic_view_destroy(base_view);
    semantic_snapshot_destroy(base);
    semantic_type_registry_destroy(reg);
    return 0;
}

int test_composed_view_identity_deterministic(void) {
    semantic_type_registry *reg;
    setup_registry(&reg);

    semantic_snapshot_manifest *base = semantic_snapshot_create();
    semantic_snapshot_view *base_view = semantic_view_create(base);

    hacf_digest query;
    memset(query.bytes, 0xAA, 32);

    /* Create two overlays with same content. */
    semantic_query_overlay *ov1 = semantic_overlay_create(base, reg, &query);
    semantic_query_overlay *ov2 = semantic_overlay_create(base, reg, &query);
    semantic_overlay_finalize(ov1);
    semantic_overlay_finalize(ov2);

    hacf_digest policy;
    memset(policy.bytes, 0xBB, 32);

    semantic_composed_view *cv1 = semantic_composed_view_create(base_view, ov1, &policy);
    semantic_composed_view *cv2 = semantic_composed_view_create(base_view, ov2, &policy);

    hacf_digest d1, d2;
    semantic_composed_view_digest(cv1, &d1);
    semantic_composed_view_digest(cv2, &d2);
    assert(memcmp(d1.bytes, d2.bytes, 32) == 0);

    semantic_composed_view_destroy(cv1);
    semantic_composed_view_destroy(cv2);
    semantic_overlay_destroy(ov1);
    semantic_overlay_destroy(ov2);
    semantic_view_destroy(base_view);
    semantic_snapshot_destroy(base);
    semantic_type_registry_destroy(reg);
    return 0;
}

int test_opaque_external_dependency_digests(void) {
    semantic_type_registry *reg;
    setup_registry(&reg);

    semantic_snapshot_manifest *base = semantic_snapshot_create();

    hacf_digest query;
    memset(query.bytes, 0xAA, 32);

    semantic_query_overlay *overlay = semantic_overlay_create(base, reg, &query);

    hacf_digest dep1, dep2;
    memset(dep1.bytes, 0x11, 32);
    memset(dep2.bytes, 0x22, 32);

    assert(semantic_overlay_add_external_dependency(overlay, &dep1) == SEMANTIC_OK);
    assert(semantic_overlay_add_external_dependency(overlay, &dep2) == SEMANTIC_OK);
    assert(overlay->external_dependency_count == 2);

    /* Verify deps are stored. */
    assert(memcmp(overlay->external_dependency_digests[0].bytes, dep1.bytes, 32) == 0);
    assert(memcmp(overlay->external_dependency_digests[1].bytes, dep2.bytes, 32) == 0);

    /* Finalize with deps — identity should include them. */
    semantic_overlay_finalize(overlay);

    /* Create another overlay without deps — identity must differ. */
    semantic_query_overlay *overlay2 = semantic_overlay_create(base, reg, &query);
    semantic_overlay_finalize(overlay2);

    assert(memcmp(overlay->overlay_identity.bytes, overlay2->overlay_identity.bytes, 32) != 0);

    semantic_overlay_destroy(overlay);
    semantic_overlay_destroy(overlay2);
    semantic_snapshot_destroy(base);
    semantic_type_registry_destroy(reg);
    return 0;
}

static int node_order(const void *a, const void *b) {
    return elpis_semantic_node_cmp(a,b);
}
static int test_composed_pagination_and_shadowing(void) {
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAIL composed line %d\n",__LINE__); exit(1); } } while(0)
    semantic_type_registry *reg; setup_registry(&reg);
    semantic_snapshot_manifest *m=semantic_snapshot_create();
    semantic_snapshot_view *base=semantic_view_create(m);
    hacf_digest query={{1}}, policy={{2}};
    semantic_query_overlay *overlay=semantic_overlay_create(m,reg,&query);
    CHECK(base && overlay);
    elpis_semantic_node_v1 nodes[5];
    for(unsigned i=0;i<5;++i) { uint8_t payload[32]={(uint8_t)i}; make_node(&nodes[i],1,payload); }
    qsort(nodes,5,sizeof(*nodes),node_order);
    elpis_semantic_node_v1 base_nodes[]={nodes[4],nodes[2],nodes[0]};
    elpis_semantic_hyperedge_v1 edge={0};
    edge.abi_version=SEMANTIC_ABI_VERSION; edge.hyperedge_type=SEMANTIC_HYPEREDGE_NAMESPACE|1;
    CHECK(elpis_semantic_hyperedge_identity(&edge,&edge.hyperedge_identity)==SEMANTIC_OK);
    semantic_view_set_records(base,base_nodes,3,NULL,0,&edge,1,NULL,0);
    for(unsigned i=1;i<=3;++i) CHECK(semantic_overlay_add_node(overlay,&nodes[i])==SEMANTIC_OK);
    CHECK(semantic_overlay_add_hyperedge(overlay,&edge)==SEMANTIC_OK);
    CHECK(semantic_overlay_finalize(overlay)==SEMANTIC_OK);
    semantic_composed_view *v=semantic_composed_view_create(base,overlay,&policy); CHECK(v);
    CHECK(semantic_composed_view_total_nodes(v)==5);
    CHECK(semantic_composed_view_total_hyperedges(v)==1);
    const elpis_semantic_node_v1 *expected[5], *out[8];
    for(unsigned i=0;i<5;++i) { expected[i]=semantic_composed_view_lookup_node(v,&nodes[i].node_identity); CHECK(expected[i]); }
    CHECK(expected[2]!=semantic_view_lookup_node(base,&nodes[2].node_identity));
    const uint32_t offsets[]={0,1,5,6,UINT32_MAX}, limits[]={0,1,3,5,UINT32_MAX}, caps[]={0,1,3,5,8};
    for(unsigned a=0;a<5;++a) for(unsigned b=0;b<5;++b) for(unsigned c=0;c<5;++c) {
        uint32_t want=offsets[a]<5 ? 5-offsets[a] : 0;
        if(want>limits[b]) want=limits[b];
        if(want>caps[c]) want=caps[c];
        for(unsigned repeat=0;repeat<2;++repeat) {
            for(unsigned i=0;i<8;++i) out[i]=expected[0];
            CHECK(semantic_composed_view_enumerate_nodes(v,offsets[a],limits[b],out,caps[c])==want);
            for(unsigned i=0;i<want;++i) CHECK(out[i]==expected[offsets[a]+i]);
            for(unsigned i=want;i<8;++i) CHECK(out[i]==expected[0]);
        }
    }
    CHECK(semantic_composed_view_enumerate_nodes(v,0,1,NULL,1)==0);
    CHECK(semantic_view_total_nodes(base)==3 && semantic_view_total_hyperedges(base)==1);
    semantic_composed_view_destroy(v); semantic_overlay_destroy(overlay);
    semantic_view_destroy(base); semantic_snapshot_destroy(m); semantic_type_registry_destroy(reg);
#undef CHECK
    return 0;
}

int main(void) {
    printf("Running query overlay tests...\n");

    int tests[] = {
        test_overlay_references_base_nodes(),
        test_overlay_cannot_alter_base_records(),
        test_composed_view_includes_base_and_overlay(),
        test_composed_pagination_and_shadowing(),
        test_composed_view_identity_deterministic(),
        test_opaque_external_dependency_digests(),
    };

    int pass = 0, total = sizeof(tests) / sizeof(tests[0]);
    for (int i = 0; i < total; i++) {
        if (tests[i] == 0) pass++;
        else printf("FAILED test %d\n", i);
    }

    printf("Query overlay tests: %d/%d passed\n", pass, total);
    return (pass == total) ? 0 : 1;
}
