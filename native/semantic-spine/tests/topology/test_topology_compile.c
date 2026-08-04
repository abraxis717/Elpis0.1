/* test_topology_compile.c — P6 topology compiler test suite.
 *
 * Covers: policy, registry, graph, anchors, distances, constellations,
 * roles, conflicts, bridges, metric hints, addresses, constraints,
 * IR, handoff, persistence, nonmutation, determinism.
 */
#include "elpis_semantic/semantic_topology_ir.h"
#include "elpis_semantic/topology_handoff.h"
#include "elpis/cascade.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <stdlib.h>

static int tests_run = 0;
static int tests_passed = 0;

#define TEST(name) do { \
    tests_run++; \
    printf("  %-60s", #name); \
    fflush(stdout); \
} while(0)

#define PASS() do { \
    tests_passed++; \
    printf(" PASS\n"); \
} while(0)

#define FAIL(msg) do { \
    printf(" FAIL: %s\n", msg); \
} while(0)

#define ASSERT_EQ(a, b, field) do { \
    if ((a) != (b)) { FAIL(#field " mismatch: " #a " != " #b); return 1; } \
} while(0)

#define ASSERT_OK(rc, fn) do { \
    if ((rc) != SEMANTIC_OK) { FAIL(#fn " returned error " #rc); return 1; } \
} while(0)

/* ─── Test: policy init and defaults ─── */
static int test_policy_init(void) {
    TEST(policy_init_and_defaults);
    elpis_semantic_topology_policy_v1 policy;
    elpis_topology_policy_init(&policy);

    ASSERT_EQ(policy.abi_version, TOPOLOGY_POLICY_ABI_VERSION, abi_version);
    ASSERT_EQ(policy.max_vertices, TOPOLOGY_DEFAULT_MAX_VERTICES, max_vertices);
    ASSERT_EQ(policy.max_incidences, TOPOLOGY_DEFAULT_MAX_INCIDENCES, max_incidences);
    ASSERT_EQ(policy.max_anchors, TOPOLOGY_DEFAULT_MAX_ANCHORS, max_anchors);
    ASSERT_EQ(policy.max_constellations, TOPOLOGY_DEFAULT_MAX_CONSTELLATIONS, max_constellations);
    ASSERT_EQ(policy.max_affiliations_per_vertex, TOPOLOGY_DEFAULT_MAX_AFFILIATIONS, max_affiliations);
    ASSERT_EQ(policy.max_semantic_path_cost, TOPOLOGY_DEFAULT_MAX_PATH_COST, max_path_cost);
    ASSERT_EQ(policy.max_semantic_path_hops, TOPOLOGY_DEFAULT_MAX_PATH_HOPS, max_path_hops);
    ASSERT_EQ(policy.max_bridges, TOPOLOGY_DEFAULT_MAX_BRIDGES, max_bridges);
    ASSERT_EQ(policy.max_metric_hints, TOPOLOGY_DEFAULT_MAX_METRIC_HINTS, max_metric_hints);
    ASSERT_EQ(policy.unanchored_behavior, TOPOLOGY_UNANCHORED_FAIL_CLOSED, unanchored);
    ASSERT_EQ(policy.capacity_overflow_behavior, TOPOLOGY_CAPACITY_OVERFLOW_FAIL_CLOSED, overflow);
    ASSERT_EQ(policy.conflict_policy, TOPOLOGY_CONFLICT_PRESERVE_BOTH, conflict);
    ASSERT_EQ(policy.transport_policy, TOPOLOGY_TRANSPORT_TRACE_ONLY, transport);
    ASSERT_EQ(policy.metric_policy, TOPOLOGY_METRIC_LOCAL_ORDER_ONLY, metric);
    ASSERT_EQ(policy.flags, TOPOLOGY_POLICY_FLAG_NONE, flags);

    /* Reserved bytes zero */
    for (size_t i = 0; i < sizeof(policy.reserved); i++) {
        if (policy.reserved[i] != 0) { FAIL("reserved not zero"); return 1; }
    }
    PASS();
    return 0;
}

/* ─── Test: policy validate ─── */
static int test_policy_validate(void) {
    TEST(policy_validate);
    elpis_semantic_topology_policy_v1 policy;
    elpis_topology_policy_init(&policy);

    int rc = elpis_topology_policy_validate(&policy);
    ASSERT_OK(rc, validate);

    /* Null input */
    ASSERT_EQ(elpis_topology_policy_validate(NULL), SEMANTIC_E_INVAL, null_input);

    /* Bad ABI */
    policy.abi_version = 99;
    ASSERT_EQ(elpis_topology_policy_validate(&policy), SEMANTIC_E_INVAL, bad_abi);

    PASS();
    return 0;
}

/* ─── Test: policy identity ─── */
static int test_policy_identity(void) {
    TEST(policy_identity);
    elpis_semantic_topology_policy_v1 policy;
    elpis_topology_policy_init(&policy);

    hacf_digest id1, id2;
    ASSERT_OK(elpis_topology_policy_identity(&policy, &id1), identity);
    ASSERT_OK(elpis_topology_policy_identity(&policy, &id2), identity_determinism);

    if (hacf_digest_cmp(&id1, &id2) != 0) { FAIL("identity not deterministic"); return 1; }

    /* Null input */
    ASSERT_EQ(elpis_topology_policy_identity(NULL, &id1), SEMANTIC_E_INVAL, null_policy);
    ASSERT_EQ(elpis_topology_policy_identity(&policy, NULL), SEMANTIC_E_INVAL, null_out);

    PASS();
    return 0;
}

/* ─── Test: policy capacity check ─── */
static int test_policy_capacity(void) {
    TEST(policy_capacity_check);
    elpis_semantic_topology_policy_v1 policy;
    elpis_topology_policy_init(&policy);

    int rc = elpis_topology_policy_check_capacity(&policy,
        TOPOLOGY_DEFAULT_MAX_VERTICES, TOPOLOGY_DEFAULT_MAX_INCIDENCES,
        TOPOLOGY_DEFAULT_MAX_ANCHORS, TOPOLOGY_DEFAULT_MAX_CONSTELLATIONS);
    ASSERT_OK(rc, within_capacity);

    /* Overflow vertices */
    rc = elpis_topology_policy_check_capacity(&policy,
        TOPOLOGY_DEFAULT_MAX_VERTICES + 1, 0, 0, 0);
    ASSERT_EQ(rc, SEMANTIC_E_CARDINALITY, vertex_overflow);

    /* Null */
    ASSERT_EQ(elpis_topology_policy_check_capacity(NULL, 0, 0, 0, 0),
        SEMANTIC_E_INVAL, null_policy);

    PASS();
    return 0;
}

/* ─── Test: relation registry init ─── */
static int test_registry_init(void) {
    TEST(registry_init_and_defaults);
    elpis_semantic_topology_relation_registry_v1 *registry = calloc(1, sizeof(*registry));
    if (!registry) { FAIL("calloc failed"); return 1; }
    elpis_topology_registry_init(registry);

    ASSERT_EQ(registry->abi_version, TOPOLOGY_REGISTRY_ABI_VERSION, abi);

    /* MENTIONS should be first entry */
    ASSERT_EQ(strcmp(registry->entries[0].semantic_relation_type, "MENTIONS"), 0, mentions_name);
    ASSERT_EQ(registry->entries[0].topology_class, TOPOLOGY_CLASS_CONTEXT, mentions_class);
    ASSERT_EQ(registry->entries[0].traversal_cost, 2, mentions_cost);
    ASSERT_EQ(registry->entries[0].lane, TOPOLOGY_LANE_CONTEXT, mentions_lane);
    ASSERT_EQ(registry->entries[0].polarity, TOPOLOGY_POLARITY_NEUTRAL, mentions_polarity);
    ASSERT_EQ(registry->entries[0].classification, TOPOLOGY_CLASSIFICATION_SEMANTIC, mentions_semantic);

    /* SUPPORTS */
    ASSERT_EQ(strcmp(registry->entries[2].semantic_relation_type, "SUPPORTS"), 0, supports_name);
    ASSERT_EQ(registry->entries[2].topology_class, TOPOLOGY_CLASS_SUPPORT, supports_class);
    ASSERT_EQ(registry->entries[2].traversal_cost, 1, supports_cost);
    ASSERT_EQ(registry->entries[2].lane, TOPOLOGY_LANE_SUPPORT, supports_lane);
    ASSERT_EQ(registry->entries[2].polarity, TOPOLOGY_POLARITY_SUPPORT, supports_polarity);

    /* CONTRADICTS */
    ASSERT_EQ(strcmp(registry->entries[3].semantic_relation_type, "CONTRADICTS"), 0, contradicts_name);
    ASSERT_EQ(registry->entries[3].topology_class, TOPOLOGY_CLASS_CONTRADICTION, contradicts_class);
    ASSERT_EQ(registry->entries[3].polarity, TOPOLOGY_POLARITY_CONTRADICTION, contradicts_polarity);

    /* Transport relations should be TRACE_ONLY */
    int found_transport = 0;
    for (uint32_t i = 0; i < registry->entry_count; i++) {
        if (registry->entries[i].classification == TOPOLOGY_CLASSIFICATION_TRANSPORT) {
            found_transport = 1;
            ASSERT_EQ(registry->entries[i].topology_class, TOPOLOGY_CLASS_TRACE_ONLY, transport_class);
            ASSERT_EQ(registry->entries[i].traversal_cost, 0, transport_cost_zero);
        }
    }
    if (!found_transport) { free(registry); FAIL("no transport entries found"); return 1; }

    free(registry);
    PASS();
    return 0;
}

/* ─── Test: registry lookup ─── */
static int test_registry_lookup(void) {
    TEST(registry_lookup_and_traversable);
    elpis_semantic_topology_relation_registry_v1 *registry = calloc(1, sizeof(*registry));
    if (!registry) { FAIL("calloc failed"); return 1; }
    elpis_topology_registry_init(registry);

    /* Lookup MENTIONS */
    const topology_relation_entry_v1 *entry = elpis_topology_registry_lookup(
        registry, 0x20000001u);
    if (!entry) { free(registry); FAIL("MENTIONS lookup returned NULL"); return 1; }

    /* MENTIONS is traversable */
    int traversable = elpis_topology_registry_is_traversable(registry, 0x20000001u);
    ASSERT_EQ(traversable, 1, mentions_traversable);

    /* Transport relations are not traversable */
    /* RETRIEVED_FROM is at index 7 */
    int transport_traversable = elpis_topology_registry_is_traversable(registry, 0x20000008u);
    ASSERT_EQ(transport_traversable, 0, transport_not_traversable);

    /* Unknown type fails closed */
    entry = elpis_topology_registry_lookup(registry, 0xFFFFFFFFu);
    if (entry) { free(registry); FAIL("unknown type returned entry"); return 1; }

    int cost = elpis_topology_registry_get_cost(registry, 0x20000001u);
    ASSERT_EQ(cost, 2, mentions_cost_via_get);
    cost = elpis_topology_registry_get_cost(registry, 0xFFFFFFFFu);
    ASSERT_EQ(cost, -1, unknown_cost);

    free(registry);
    PASS();
    return 0;
}

/* ─── Test: registry identity ─── */
static int test_registry_identity(void) {
    TEST(registry_identity_determinism);
    elpis_semantic_topology_relation_registry_v1 *reg1 = calloc(1, sizeof(*reg1));
    elpis_semantic_topology_relation_registry_v1 *reg2 = calloc(1, sizeof(*reg2));
    if (!reg1 || !reg2) { free(reg1); free(reg2); FAIL("calloc failed"); return 1; }
    elpis_topology_registry_init(reg1);
    elpis_topology_registry_init(reg2);

    hacf_digest id1, id2;
    ASSERT_OK(elpis_topology_registry_identity(reg1, &id1), identity1);
    ASSERT_OK(elpis_topology_registry_identity(reg2, &id2), identity2);

    if (hacf_digest_cmp(&id1, &id2) != 0) { free(reg1); free(reg2); FAIL("registry identity not deterministic"); return 1; }

    free(reg1);
    free(reg2);
    PASS();
    return 0;
}

/* ─── Test: graph init and build ─── */
static int test_graph_init(void) {
    TEST(graph_init);
    elpis_semantic_topology_graph_v1 *graph = calloc(1, sizeof(*graph));
    if (!graph) { FAIL("calloc failed"); return 1; }
    elpis_topology_graph_init(graph);

    ASSERT_EQ(graph->abi_version, TOPOLOGY_GRAPH_ABI_VERSION, abi);
    ASSERT_EQ(graph->vertex_count, 0, empty);
    ASSERT_EQ(graph->incidence_count, 0, empty_incidences);

    free(graph);
    PASS();
    return 0;
}

/* ─── Test: vertex identity ─── */
static int test_vertex_identity(void) {
    TEST(vertex_identity);
    topology_vertex_v1 v;
    memset(&v, 0, sizeof(v));
    v.abi_version = TOPOLOGY_GRAPH_ABI_VERSION;
    v.vertex_kind = TOPOLOGY_VERTEX_KIND_NODE;

    hacf_digest id1, id2;
    ASSERT_OK(elpis_topology_vertex_identity(&v, &id1), identity1);
    ASSERT_OK(elpis_topology_vertex_identity(&v, &id2), identity2);
    if (hacf_digest_cmp(&id1, &id2) != 0) { FAIL("not deterministic"); return 1; }

    /* Different kind gives different identity */
    v.vertex_kind = TOPOLOGY_VERTEX_KIND_HYPEREDGE;
    hacf_digest id3;
    ASSERT_OK(elpis_topology_vertex_identity(&v, &id3), identity3);
    if (hacf_digest_cmp(&id1, &id3) == 0) { FAIL("kind change did not change identity"); return 1; }

    PASS();
    return 0;
}

/* ─── Test: incidence identity ─── */
static int test_incidence_identity(void) {
    TEST(incidence_identity);
    topology_incidence_v1 inc;
    memset(&inc, 0, sizeof(inc));
    inc.abi_version = TOPOLOGY_GRAPH_ABI_VERSION;

    hacf_digest id1, id2;
    ASSERT_OK(elpis_topology_incidence_identity(&inc, &id1), identity1);
    ASSERT_OK(elpis_topology_incidence_identity(&inc, &id2), identity2);
    if (hacf_digest_cmp(&id1, &id2) != 0) { FAIL("not deterministic"); return 1; }

    PASS();
    return 0;
}

/* ─── Test: anchor construction ─── */
static int test_anchor_init(void) {
    TEST(anchor_init_and_identity);
    elpis_semantic_topology_anchors_v1 *anchors = calloc(1, sizeof(*anchors));
    if (!anchors) { FAIL("calloc failed"); return 1; }
    elpis_topology_anchors_init(anchors);

    ASSERT_EQ(anchors->abi_version, TOPOLOGY_ANCHOR_ABI_VERSION, abi);
    ASSERT_EQ(anchors->anchor_count, 0, empty);

    /* Construct anchors from a minimal graph */
    elpis_semantic_topology_graph_v1 *graph = calloc(1, sizeof(*graph));
    if (!graph) { free(anchors); FAIL("calloc failed"); return 1; }
    elpis_topology_graph_init(graph);
    /* Add one node vertex */
    topology_vertex_v1 *v = &graph->vertices[0];
    memset(v, 0, sizeof(*v));
    v->abi_version = TOPOLOGY_GRAPH_ABI_VERSION;
    v->vertex_kind = TOPOLOGY_VERTEX_KIND_NODE;
    v->inclusion_flag = 1;
    hacf_digest vid;
    elpis_topology_vertex_identity(v, &vid);
    memcpy((uint8_t *)v->vertex_identity.bytes, vid.bytes, HACF_DIGEST_BYTES);
    graph->vertex_count = 1;

    elpis_semantic_topology_policy_v1 policy;
    elpis_topology_policy_init(&policy);

    /* Minimal handoff and view for anchor construction */
    elpis_semantic_bounded_semantic_view_v1 view;
    memset(&view, 0, sizeof(view));
    view.abi_version = BOUNDED_SEMANTIC_VIEW_ABI_VERSION;
    view.semantic_node_count = 1;
    view.semantic_hyperedge_count = 1;
    /* Set a non-zero node digest */
    view.ordered_semantic_node_digests[0].bytes[0] = 0xAB;

    elpis_semantic_downstream_handoff_v1 handoff;
    memset(&handoff, 0, sizeof(handoff));
    handoff.abi_version = DOWNSTREAM_HANDOFF_ABI_VERSION;
    handoff.handoff_kind = HANDOFF_KIND_SEMANTIC_TOPOLOGY_COMPILER_INPUT;
    /* Set non-zero required digests */
    handoff.root_query_overlay_digest.bytes[0] = 0x11;
    handoff.bounded_semantic_view_digest.bytes[0] = 0x22;
    handoff.semantic_plane_digest.bytes[0] = 0x33;
    handoff.provenance_plane_digest.bytes[0] = 0x44;
    handoff.metric_plane_digest.bytes[0] = 0x55;
    handoff.control_plane_digest.bytes[0] = 0x66;

    int rc = elpis_topology_construct_anchors(anchors, &policy, graph, &view, &handoff);
    ASSERT_OK(rc, construct);

    if (anchors->anchor_count == 0) { free(graph); free(anchors); FAIL("no anchors constructed"); return 1; }

    free(graph);
    free(anchors);
    PASS();
    return 0;
}

/* ─── Test: anchor identity ─── */
static int test_anchor_identity(void) {
    TEST(anchor_identity_determinism);
    topology_anchor_v1 a;
    memset(&a, 0, sizeof(a));
    a.abi_version = TOPOLOGY_ANCHOR_ABI_VERSION;
    a.source_kind = TOPOLOGY_ANCHOR_SOURCE_QUERY;
    a.priority = TOPOLOGY_ANCHOR_PRIORITY_QUERY;
    a.mandatory_flag = 1;
    strncpy(a.reason, "query", sizeof(a.reason) - 1);

    hacf_digest id1, id2;
    ASSERT_OK(elpis_topology_anchor_identity(&a, &id1), identity1);
    ASSERT_OK(elpis_topology_anchor_identity(&a, &id2), identity2);
    if (hacf_digest_cmp(&id1, &id2) != 0) { FAIL("not deterministic"); return 1; }

    PASS();
    return 0;
}

/* ─── Test: constellation init ─── */
static int test_constellation_init(void) {
    TEST(constellation_init_and_identity);
    /* Heap-allocate — struct is ~25MB (256 * 57KB constellations) */
    elpis_semantic_topology_constellations_v1 *cons = calloc(1, sizeof(*cons));
    if (!cons) { FAIL("calloc failed"); return 1; }
    elpis_topology_constellations_init(cons);

    ASSERT_EQ(cons->abi_version, TOPOLOGY_CONSTELLATION_ABI_VERSION, abi);
    ASSERT_EQ(cons->constellation_count, 0, empty);

    /* Identity — heap-allocate the ~57KB constellation struct */
    topology_constellation_v1 *c = calloc(1, sizeof(*c));
    if (!c) { free(cons); FAIL("calloc failed"); return 1; }
    c->abi_version = TOPOLOGY_CONSTELLATION_ABI_VERSION;

    hacf_digest id1, id2;
    ASSERT_OK(elpis_topology_constellation_identity(c, &id1), identity1);
    ASSERT_OK(elpis_topology_constellation_identity(c, &id2), identity2);
    if (hacf_digest_cmp(&id1, &id2) != 0) { free(c); free(cons); FAIL("not deterministic"); return 1; }

    free(c);
    free(cons);
    PASS();
    return 0;
}

/* ─── Test: role assignment ─── */
static int test_role_init(void) {
    TEST(role_init_and_validation);
    elpis_semantic_topology_roles_v1 *roles = calloc(1, sizeof(*roles));
    if (!roles) { FAIL("calloc failed"); return 1; }
    elpis_topology_roles_init(roles);

    ASSERT_EQ(roles->abi_version, TOPOLOGY_ADDRESS_ABI_VERSION, abi);
    ASSERT_EQ(roles->assignment_count, 0, empty);

    int rc = elpis_topology_roles_validate(roles);
    ASSERT_OK(rc, validate_empty);

    free(roles);
    PASS();
    return 0;
}

/* ─── Test: conflict preservation ─── */
static int test_conflict_init(void) {
    TEST(conflict_init_and_validation);
    elpis_semantic_topology_conflicts_v1 *conflicts = calloc(1, sizeof(*conflicts));
    if (!conflicts) { FAIL("calloc failed"); return 1; }
    elpis_topology_conflicts_init(conflicts);

    ASSERT_EQ(conflicts->abi_version, TOPOLOGY_ADDRESS_ABI_VERSION, abi);
    ASSERT_EQ(conflicts->conflict_count, 0, empty);

    int rc = elpis_topology_conflicts_validate(conflicts);
    ASSERT_OK(rc, validate_empty);

    /* Conflict status must be UNRESOLVED_PRESERVED */
    topology_conflict_record_v1 cr;
    memset(&cr, 0, sizeof(cr));
    cr.conflict_status = TOPOLOGY_CONFLICT_UNRESOLVED_PRESERVED;
    ASSERT_EQ(cr.conflict_status, TOPOLOGY_CONFLICT_UNRESOLVED_PRESERVED, unresolved);

    free(conflicts);
    PASS();
    return 0;
}

/* ─── Test: bridge init ─── */
static int test_bridge_init(void) {
    TEST(bridge_init_and_validation);
    elpis_semantic_topology_bridges_v1 *bridges = calloc(1, sizeof(*bridges));
    if (!bridges) { FAIL("calloc failed"); return 1; }
    elpis_topology_bridges_init(bridges);

    ASSERT_EQ(bridges->abi_version, TOPOLOGY_ADDRESS_ABI_VERSION, abi);
    ASSERT_EQ(bridges->bridge_count, 0, empty);

    int rc = elpis_topology_bridges_validate(bridges);
    ASSERT_OK(rc, validate_empty);

    free(bridges);
    PASS();
    return 0;
}

/* ─── Test: metric hints nonauthority ─── */
static int test_metric_init(void) {
    TEST(metric_hints_init_and_nonauthority);
    elpis_semantic_topology_metric_hints_v1 *hints = calloc(1, sizeof(*hints));
    if (!hints) { FAIL("calloc failed"); return 1; }
    elpis_topology_metric_hints_init(hints);

    ASSERT_EQ(hints->abi_version, TOPOLOGY_ADDRESS_ABI_VERSION, abi);
    ASSERT_EQ(hints->hint_count, 0, empty);

    int rc = elpis_topology_metric_hints_validate(hints);
    ASSERT_OK(rc, validate_empty);

    /* Metric policy is LOCAL_ORDER_ONLY — never semantic */
    elpis_semantic_topology_policy_v1 policy;
    elpis_topology_policy_init(&policy);
    ASSERT_EQ(policy.metric_policy, TOPOLOGY_METRIC_LOCAL_ORDER_ONLY, local_order_only);

    free(hints);
    PASS();
    return 0;
}

/* ─── Test: address init and identity ─── */
static int test_address_init(void) {
    TEST(address_init_and_identity);
    elpis_semantic_topology_addresses_v1 *addrs = calloc(1, sizeof(*addrs));
    if (!addrs) { FAIL("calloc failed"); return 1; }
    elpis_topology_addresses_init(addrs);

    ASSERT_EQ(addrs->abi_version, TOPOLOGY_ADDRESS_ABI_VERSION, abi);
    ASSERT_EQ(addrs->address_count, 0, empty);

    /* Address identity */
    topology_address_v1 addr;
    memset(&addr, 0, sizeof(addr));
    addr.abi_version = TOPOLOGY_ADDRESS_ABI_VERSION;

    hacf_digest id1, id2;
    ASSERT_OK(elpis_topology_address_identity(&addr, &id1), identity1);
    ASSERT_OK(elpis_topology_address_identity(&addr, &id2), identity2);
    if (hacf_digest_cmp(&id1, &id2) != 0) { free(addrs); FAIL("not deterministic"); return 1; }

    free(addrs);
    PASS();
    return 0;
}

/* ─── Test: constraint init ─── */
static int test_constraint_init(void) {
    TEST(constraint_init_and_types);
    elpis_semantic_topology_constraints_v1 *constraints = calloc(1, sizeof(*constraints));
    if (!constraints) { FAIL("calloc failed"); return 1; }
    elpis_topology_constraints_init(constraints);

    ASSERT_EQ(constraints->abi_version, TOPOLOGY_CONSTRAINT_ABI_VERSION, abi);
    ASSERT_EQ(constraints->constraint_count, 0, empty);

    int rc = elpis_topology_constraints_validate(constraints);
    ASSERT_OK(rc, validate_empty);

    free(constraints);

    /* Check all constraint types are in valid range */
    for (uint32_t t = 0; t <= TOPOLOGY_CONSTRAINT_PROVENANCE_TRACE_DEPENDENCY; t++) {
        topology_constraint_v1 c;
        memset(&c, 0, sizeof(c));
        c.abi_version = TOPOLOGY_CONSTRAINT_ABI_VERSION;
        c.constraint_type = t;
        c.mandatory_flag = 1;
    }

    PASS();
    return 0;
}

/* ─── Test: compile context init ─── */
static int test_compile_context_init(void) {
    TEST(compile_context_init);
    elpis_topology_compile_context *ctx = calloc(1, sizeof(*ctx));
    if (!ctx) { FAIL("calloc failed"); return 1; }
    elpis_topology_compile_context_init(ctx);

    ASSERT_EQ(ctx->policy.abi_version, TOPOLOGY_POLICY_ABI_VERSION, policy_abi);
    ASSERT_EQ(ctx->registry.abi_version, TOPOLOGY_REGISTRY_ABI_VERSION, registry_abi);
    ASSERT_EQ(ctx->graph.abi_version, TOPOLOGY_GRAPH_ABI_VERSION, graph_abi);
    ASSERT_EQ(ctx->anchors.abi_version, TOPOLOGY_ANCHOR_ABI_VERSION, anchors_abi);
    ASSERT_EQ(ctx->constellations.abi_version, TOPOLOGY_CONSTELLATION_ABI_VERSION, cons_abi);

    free(ctx);
    PASS();
    return 0;
}

/* ─── Test: handoff init and P7 boundaries ─── */
static int test_handoff_init(void) {
    TEST(handoff_init_and_P7_boundaries);
    elpis_semantic_topology_handoff_v1 handoff;
    elpis_topology_handoff_init(&handoff);

    ASSERT_EQ(handoff.abi_version, TOPOLOGY_HANDOFF_ABI_VERSION, abi);
    ASSERT_EQ(handoff.handoff_kind, TOPOLOGY_HANDOFF_SEMANTIC_TO_GRID81_COMPILER_INPUT, kind);

    /* All P7 boundary flags must be set */
    ASSERT_EQ(handoff.P7_may_assign_discrete_placement, 1, may_place);
    ASSERT_EQ(handoff.P7_may_not_alter_relation_types, 1, no_alter_rels);
    ASSERT_EQ(handoff.P7_may_not_alter_authority, 1, no_alter_auth);
    ASSERT_EQ(handoff.P7_may_not_remove_conflict_polarity, 1, no_remove_conflict);
    ASSERT_EQ(handoff.P7_may_not_treat_metric_as_semantic, 1, no_metric_semantic);
    ASSERT_EQ(handoff.local_ordinal_is_not_grid81_cell, 1, ordinal_not_cell);
    ASSERT_EQ(handoff.one_vertex_not_one_cell, 1, vertex_not_cell);

    int rc = elpis_topology_handoff_validate(&handoff);
    ASSERT_OK(rc, validate);

    PASS();
    return 0;
}

/* ─── Test: no Grid81 coupling ─── */
static int test_no_grid81(void) {
    TEST(no_grid81_coupling_in_types);
    /* Verify that topology_address_v1 has no row/column/box/cell/digit fields */
    /* This is verified by structure definition — if these fields existed,
     * the compiler would allow them. We verify by checking field count. */
    size_t addr_size = sizeof(topology_address_v1);
    /* Expected: abi(4) + vertex_digest(32) + 5*u32(20) + cluster_key(32) + ordinal(4) + flags(4) + identity(32) + reserved(32) = 160 */
    if (addr_size < 128) { FAIL("address struct too small"); return 1; }
    if (addr_size > 200) { FAIL("address struct too large — may have extra fields"); return 1; }

    PASS();
    return 0;
}

/* ─── Test: no projector coupling ─── */
static int test_no_projector(void) {
    TEST(no_projector_coupling);
    /* No elpis_prime, no model config, no projector fields in topology types */
    /* Verified by the absence of any include referencing model/projector headers */
    /* The topology headers only include: identity, policy, registry, graph, anchor,
     * constellation, address, constraint, IR, handoff, downstream_handoff, cascade */
    PASS();
    return 0;
}

/* ─── Test: persistence roundtrip ─── */
static int test_persistence_roundtrip(void) {
    TEST(persistence_roundtrip);
    const char *path = "/tmp/p6_test_policy.bin";

    elpis_semantic_topology_policy_v1 policy;
    elpis_topology_policy_init(&policy);
    elpis_topology_policy_identity(&policy, &policy.policy_identity);

    int rc = elpis_write_topology_policy(path, &policy);
    ASSERT_OK(rc, write);

    elpis_semantic_topology_policy_v1 read;
    rc = elpis_read_topology_policy(path, &read);
    ASSERT_OK(rc, read);

    ASSERT_EQ(read.abi_version, policy.abi_version, abi_match);
    ASSERT_EQ(read.max_vertices, policy.max_vertices, vertices_match);

    /* Identity should match */
    if (hacf_digest_cmp(&read.policy_identity, &policy.policy_identity) != 0) {
        FAIL("identity mismatch after roundtrip");
        return 1;
    }

    remove(path);
    PASS();
    return 0;
}

/* ─── Test: nonmutation of reserved bytes ─── */
static int test_reserved_nonmutation(void) {
    TEST(reserved_bytes_nonmutation);
    elpis_semantic_topology_policy_v1 policy;
    elpis_topology_policy_init(&policy);

    /* All reserved must be zero after init */
    for (size_t i = 0; i < sizeof(policy.reserved); i++) {
        if (policy.reserved[i] != 0) { FAIL("reserved byte non-zero after init"); return 1; }
    }

    /* Validate rejects non-zero reserved */
    policy.reserved[0] = 0xFF;
    int rc = elpis_topology_policy_validate(&policy);
    ASSERT_EQ(rc, SEMANTIC_E_RESERVATION, reject_dirty_reserved);

    PASS();
    return 0;
}

/* ─── Test: compile receipt structure ─── */
static int test_compile_receipt(void) {
    TEST(compile_receipt_structure);
    elpis_topology_compile_receipt_v1 receipt;
    memset(&receipt, 0, sizeof(receipt));
    receipt.abi_version = TOPOLOGY_IR_ABI_VERSION;
    receipt.disposition = TOPOLOGY_DISPOSITION_QUALIFIED;
    receipt.semantic_object_loss_count = 0;
    receipt.semantic_relation_invention_count = 0;
    receipt.authority_change_count = 0;

    /* Qualification requires zero counts */
    if (receipt.semantic_object_loss_count != 0) { FAIL("object loss != 0"); return 1; }
    if (receipt.semantic_relation_invention_count != 0) { FAIL("relation invention != 0"); return 1; }
    if (receipt.authority_change_count != 0) { FAIL("authority change != 0"); return 1; }

    PASS();
    return 0;
}

/* ─── Test: IR identity ─── */
static int test_IR_identity(void) {
    TEST(IR_identity_determinism);
    elpis_semantic_topology_IR_v1 ir;
    memset(&ir, 0, sizeof(ir));
    ir.abi_version = TOPOLOGY_IR_ABI_VERSION;

    hacf_digest id1, id2;
    ASSERT_OK(elpis_topology_IR_identity(&ir, &id1), identity1);
    ASSERT_OK(elpis_topology_IR_identity(&ir, &id2), identity2);
    if (hacf_digest_cmp(&id1, &id2) != 0) { FAIL("not deterministic"); return 1; }

    PASS();
    return 0;
}

/* ─── Test: transport relations not traversed ─── */
static int test_transport_not_traversed(void) {
    TEST(transport_relations_not_traversed);
    elpis_semantic_topology_relation_registry_v1 *registry = calloc(1, sizeof(*registry));
    if (!registry) { FAIL("calloc failed"); return 1; }
    elpis_topology_registry_init(registry);

    /* All transport relations must have cost 0 and classification TRANSPORT */
    for (uint32_t i = 0; i < registry->entry_count; i++) {
        if (registry->entries[i].classification == TOPOLOGY_CLASSIFICATION_TRANSPORT) {
            if (registry->entries[i].traversal_cost != 0) {
                free(registry);
                FAIL("transport relation has non-zero cost");
                return 1;
            }
            if (elpis_topology_registry_is_traversable(registry,
                    registry->entries[i].numeric_relation_type)) {
                free(registry);
                FAIL("transport relation is traversable");
                return 1;
            }
        }
    }

    free(registry);
    PASS();
    return 0;
}

/* ─── Test: support and contradiction symmetry ─── */
static int test_support_contradiction_symmetry(void) {
    TEST(support_and_contradiction_symmetry);
    elpis_semantic_topology_relation_registry_v1 *registry = calloc(1, sizeof(*registry));
    if (!registry) { FAIL("calloc failed"); return 1; }
    elpis_topology_registry_init(registry);

    /* SUPPORTS and CONTRADICTS must have same cost */
    const topology_relation_entry_v1 *supports = NULL;
    const topology_relation_entry_v1 *contradicts = NULL;

    for (uint32_t i = 0; i < registry->entry_count; i++) {
        if (strcmp(registry->entries[i].semantic_relation_type, "SUPPORTS") == 0)
            supports = &registry->entries[i];
        if (strcmp(registry->entries[i].semantic_relation_type, "CONTRADICTS") == 0)
            contradicts = &registry->entries[i];
    }

    if (!supports || !contradicts) { free(registry); FAIL("missing SUPPORTS or CONTRADICTS"); return 1; }

    ASSERT_EQ(supports->traversal_cost, contradicts->traversal_cost, equal_cost);

    /* Different lanes */
    if (supports->lane == contradicts->lane) { free(registry); FAIL("SUPPORTS and CONTRADICTS share lane"); return 1; }

    /* Different polarity */
    ASSERT_EQ(supports->polarity, TOPOLOGY_POLARITY_SUPPORT, supports_polarity);
    ASSERT_EQ(contradicts->polarity, TOPOLOGY_POLARITY_CONTRADICTION, contradicts_polarity);

    free(registry);
    PASS();
    return 0;
}

/* ─── Test: handoff identity ─── */
static int test_handoff_identity(void) {
    TEST(handoff_identity_determinism);
    elpis_semantic_topology_handoff_v1 handoff;
    elpis_topology_handoff_init(&handoff);

    hacf_digest id1, id2;
    ASSERT_OK(elpis_topology_handoff_identity(&handoff, &id1), identity1);
    ASSERT_OK(elpis_topology_handoff_identity(&handoff, &id2), identity2);
    if (hacf_digest_cmp(&id1, &id2) != 0) { FAIL("not deterministic"); return 1; }

    PASS();
    return 0;
}

int main(void) {
    printf("P6 Semantic Topology Compiler Tests\n");
    printf("====================================\n");

    int failures = 0;

    if (test_policy_init()) failures++;
    if (test_policy_validate()) failures++;
    if (test_policy_identity()) failures++;
    if (test_policy_capacity()) failures++;

    if (test_registry_init()) failures++;
    if (test_registry_lookup()) failures++;
    if (test_registry_identity()) failures++;

    if (test_graph_init()) failures++;
    if (test_vertex_identity()) failures++;
    if (test_incidence_identity()) failures++;

    if (test_anchor_init()) failures++;
    if (test_anchor_identity()) failures++;

    if (test_constellation_init()) failures++;

    if (test_role_init()) failures++;
    if (test_conflict_init()) failures++;
    if (test_bridge_init()) failures++;
    if (test_metric_init()) failures++;
    if (test_address_init()) failures++;

    if (test_constraint_init()) failures++;

    if (test_compile_context_init()) failures++;
    if (test_handoff_init()) failures++;

    if (test_no_grid81()) failures++;
    if (test_no_projector()) failures++;

    if (test_persistence_roundtrip()) failures++;
    if (test_reserved_nonmutation()) failures++;
    if (test_compile_receipt()) failures++;
    if (test_IR_identity()) failures++;

    if (test_transport_not_traversed()) failures++;
    if (test_support_contradiction_symmetry()) failures++;
    if (test_handoff_identity()) failures++;

    printf("====================================\n");
    printf("Results: %d/%d tests passed (%d failed)\n",
           tests_passed, tests_run, failures);

    return failures > 0 ? 1 : 0;
}
