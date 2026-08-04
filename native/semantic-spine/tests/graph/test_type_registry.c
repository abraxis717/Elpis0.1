/* test_type_registry.c — Type registry and validation tests. */
#include "elpis_semantic/type_registry.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

static void setup_registry(semantic_type_registry **reg) {
    *reg = semantic_type_registry_create();

    /* Add incidence roles. */
    semantic_incidence_role_entry role1 = {
        .incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1,
        .participant_flag_mask = SEMANTIC_PARTICIPANT_FLAG_MASK
    };
    semantic_incidence_role_entry role2 = {
        .incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 2,
        .participant_flag_mask = SEMANTIC_PARTICIPANT_FLAG_MASK
    };
    semantic_type_registry_add_incidence_role(*reg, &role1);
    semantic_type_registry_add_incidence_role(*reg, &role2);

    /* Add node types. */
    semantic_node_type_entry node1 = {
        .node_type = SEMANTIC_NODE_NAMESPACE | 1,
        .semantic_flag_mask = SEMANTIC_NODE_FLAG_MASK,
        .min_authority = 0,
        .max_authority = 3
    };
    semantic_type_registry_add_node_type(*reg, &node1);

    /* Add hyperedge types. */
    semantic_role_rule rules[] = {
        {.incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1,
         .min_cardinality = 1, .max_cardinality = 1, .is_ordered = 0, .allows_repeat = 0},
        {.incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 2,
         .min_cardinality = 1, .max_cardinality = 4, .is_ordered = 1, .allows_repeat = 0},
    };
    semantic_hyperedge_type_entry edge1 = {
        .hyperedge_type = SEMANTIC_HYPEREDGE_NAMESPACE | 1,
        .min_participants = 2,
        .max_participants = 5,
        .role_count = 2,
        .roles = {rules[0], rules[1]}
    };
    semantic_type_registry_add_hyperedge_type(*reg, &edge1);
}

int test_unknown_node_type_rejected(void) {
    semantic_type_registry *reg = semantic_type_registry_create();
    semantic_node_type_entry bad = {
        .node_type = SEMANTIC_NODE_NAMESPACE | 999,
        .semantic_flag_mask = 0, .min_authority = 0, .max_authority = 0
    };
    /* Adding is fine, but looking up unknown type should fail. */
    semantic_type_registry_add_node_type(reg, &bad);
    const semantic_node_type_entry *found = semantic_type_registry_get_node_type(reg, SEMANTIC_NODE_NAMESPACE | 42);
    assert(found == NULL);
    semantic_type_registry_destroy(reg);
    return 0;
}

int test_unknown_hyperedge_type_rejected(void) {
    semantic_type_registry *reg = semantic_type_registry_create();
    const semantic_hyperedge_type_entry *found =
        semantic_type_registry_get_hyperedge_type(reg, SEMANTIC_HYPEREDGE_NAMESPACE | 99);
    assert(found == NULL);
    semantic_type_registry_destroy(reg);
    return 0;
}

int test_unknown_incidence_role_rejected(void) {
    semantic_type_registry *reg = semantic_type_registry_create();
    const semantic_incidence_role_entry *found =
        semantic_type_registry_get_incidence_role(reg, SEMANTIC_INCIDENCE_NAMESPACE | 99);
    assert(found == NULL);
    semantic_type_registry_destroy(reg);
    return 0;
}

int test_zero_type_id_rejected(void) {
    semantic_type_registry *reg = semantic_type_registry_create();
    semantic_node_type_entry bad = {
        .node_type = 0, .semantic_flag_mask = 0, .min_authority = 0, .max_authority = 0
    };
    int r = semantic_type_registry_add_node_type(reg, &bad);
    assert(r != SEMANTIC_OK);
    semantic_type_registry_destroy(reg);
    return 0;
}

int test_namespace_collision_rejected(void) {
    semantic_type_registry *reg = semantic_type_registry_create();
    /* Try to add a node type with hyperedge namespace. */
    semantic_node_type_entry bad = {
        .node_type = SEMANTIC_HYPEREDGE_NAMESPACE | 1,
        .semantic_flag_mask = 0, .min_authority = 0, .max_authority = 0
    };
    int r = semantic_type_registry_add_node_type(reg, &bad);
    assert(r != SEMANTIC_OK);
    semantic_type_registry_destroy(reg);
    return 0;
}

int test_duplicate_type_rejected(void) {
    semantic_type_registry *reg = semantic_type_registry_create();
    semantic_node_type_entry n = {
        .node_type = SEMANTIC_NODE_NAMESPACE | 1,
        .semantic_flag_mask = SEMANTIC_NODE_FLAG_MASK, .min_authority = 0, .max_authority = 3
    };
    assert(semantic_type_registry_add_node_type(reg, &n) == SEMANTIC_OK);
    assert(semantic_type_registry_add_node_type(reg, &n) == SEMANTIC_E_DUPLICATE);
    semantic_type_registry_destroy(reg);
    return 0;
}

int test_sealed_registry_no_mutation(void) {
    semantic_type_registry *reg = semantic_type_registry_create();
    semantic_node_type_entry n = {
        .node_type = SEMANTIC_NODE_NAMESPACE | 1,
        .semantic_flag_mask = SEMANTIC_NODE_FLAG_MASK, .min_authority = 0, .max_authority = 3
    };
    semantic_type_registry_add_node_type(reg, &n);
    hacf_digest d;
    semantic_type_registry_seal(reg, &d);
    assert(semantic_type_registry_is_sealed(reg));

    semantic_node_type_entry n2 = {
        .node_type = SEMANTIC_NODE_NAMESPACE | 2,
        .semantic_flag_mask = SEMANTIC_NODE_FLAG_MASK, .min_authority = 0, .max_authority = 3
    };
    assert(semantic_type_registry_add_node_type(reg, &n2) != SEMANTIC_OK);
    semantic_type_registry_destroy(reg);
    return 0;
}

int test_registry_digest_deterministic(void) {
    semantic_type_registry *reg1 = semantic_type_registry_create();
    semantic_type_registry *reg2 = semantic_type_registry_create();

    semantic_node_type_entry n = {
        .node_type = SEMANTIC_NODE_NAMESPACE | 1,
        .semantic_flag_mask = SEMANTIC_NODE_FLAG_MASK, .min_authority = 0, .max_authority = 3
    };
    semantic_type_registry_add_node_type(reg1, &n);
    semantic_type_registry_add_node_type(reg2, &n);

    hacf_digest d1, d2;
    semantic_type_registry_seal(reg1, &d1);
    semantic_type_registry_seal(reg2, &d2);

    assert(memcmp(d1.bytes, d2.bytes, 32) == 0);
    semantic_type_registry_destroy(reg1);
    semantic_type_registry_destroy(reg2);
    return 0;
}

int test_namespace_check_helpers(void) {
    assert(semantic_type_namespace_check(SEMANTIC_NODE_NAMESPACE | 1, SEMANTIC_NODE_NAMESPACE) == SEMANTIC_OK);
    assert(semantic_type_namespace_check(SEMANTIC_HYPEREDGE_NAMESPACE | 1, SEMANTIC_HYPEREDGE_NAMESPACE) == SEMANTIC_OK);
    assert(semantic_type_namespace_check(SEMANTIC_INCIDENCE_NAMESPACE | 1, SEMANTIC_INCIDENCE_NAMESPACE) == SEMANTIC_OK);
    assert(semantic_type_namespace_check(SEMANTIC_NODE_NAMESPACE | 1, SEMANTIC_HYPEREDGE_NAMESPACE) == SEMANTIC_E_NAMESPACE_COLLISION);
    assert(semantic_type_in_namespace(SEMANTIC_NODE_NAMESPACE | 1, SEMANTIC_NODE_NAMESPACE));
    assert(!semantic_type_in_namespace(SEMANTIC_NODE_NAMESPACE | 1, SEMANTIC_HYPEREDGE_NAMESPACE));
    return 0;
}

int main(void) {
    printf("Running type registry tests...\n");

    int tests[] = {
        test_unknown_node_type_rejected(),
        test_unknown_hyperedge_type_rejected(),
        test_unknown_incidence_role_rejected(),
        test_zero_type_id_rejected(),
        test_namespace_collision_rejected(),
        test_duplicate_type_rejected(),
        test_sealed_registry_no_mutation(),
        test_registry_digest_deterministic(),
        test_namespace_check_helpers(),
    };

    int pass = 0, total = sizeof(tests) / sizeof(tests[0]);
    for (int i = 0; i < total; i++) {
        if (tests[i] == 0) pass++;
        else printf("FAILED test %d\n", i);
    }

    printf("Type registry tests: %d/%d passed\n", pass, total);
    return (pass == total) ? 0 : 1;
}
