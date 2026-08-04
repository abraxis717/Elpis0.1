/* test_segment_snapshot.c — Segment and snapshot persistence tests. */
#include "elpis_semantic/segment.h"
#include "elpis_semantic/snapshot.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void setup_registry(semantic_type_registry **reg, hacf_digest *reg_digest) {
    *reg = semantic_type_registry_create();

    semantic_incidence_role_entry r1 = {.incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1,
                                         .participant_flag_mask = SEMANTIC_PARTICIPANT_FLAG_MASK};
    semantic_type_registry_add_incidence_role(*reg, &r1);

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

    semantic_type_registry_seal(*reg, reg_digest);
}

static int check(int cond, const char *label, int test_id) {
    if (!cond) { printf("FAIL %s (test %d)\n", label, test_id); return 1; }
    return 0;
}

int test_atomic_no_replace_publication(void) {
    semantic_type_registry *reg;
    hacf_digest reg_digest;
    setup_registry(&reg, &reg_digest);

    hacf_digest genesis;
    semantic_genesis_identity(&reg_digest, &genesis);

    semantic_hypergraph_builder *b = semantic_builder_create(reg);
    semantic_segment_record seg;
    semantic_segment_build(b, reg, &genesis, &seg);

    const char *path = "/tmp/test_segment_atomic.sf";
    unlink(path);

    char hex_out[65];
    int r = semantic_segment_write(&seg, b, path, hex_out);
    if (r != SEMANTIC_OK) { semantic_builder_destroy(b); semantic_type_registry_destroy(reg); return 1; }

    r = semantic_segment_write(&seg, b, path, hex_out);
    if (r != SEMANTIC_E_DUPLICATE) { unlink(path); semantic_builder_destroy(b); semantic_type_registry_destroy(reg); return 1; }

    unlink(path);
    semantic_builder_destroy(b);
    semantic_type_registry_destroy(reg);
    return 0;
}

int test_pre_existing_destination_preserved(void) {
    const char *path = "/tmp/test_segment_existing.sf";
    FILE *f = fopen(path, "w");
    if (f) { fputs("existing", f); fclose(f); }

    semantic_type_registry *reg;
    hacf_digest reg_digest;
    setup_registry(&reg, &reg_digest);

    hacf_digest genesis;
    semantic_genesis_identity(&reg_digest, &genesis);

    semantic_hypergraph_builder *b = semantic_builder_create(reg);
    semantic_segment_record seg;
    semantic_segment_build(b, reg, &genesis, &seg);

    char hex_out[65];
    int r = semantic_segment_write(&seg, b, path, hex_out);

    unlink(path);
    semantic_builder_destroy(b);
    semantic_type_registry_destroy(reg);
    return (r == SEMANTIC_E_DUPLICATE) ? 0 : 1;
}

int test_segment_read_verify(void) {
    semantic_type_registry *reg;
    hacf_digest reg_digest;
    setup_registry(&reg, &reg_digest);

    hacf_digest genesis;
    semantic_genesis_identity(&reg_digest, &genesis);

    semantic_hypergraph_builder *b = semantic_builder_create(reg);
    semantic_segment_record seg;
    semantic_segment_build(b, reg, &genesis, &seg);

    const char *path = "/tmp/test_segment_read.sf";
    unlink(path);
    char hex_out[65];
    int r = semantic_segment_write(&seg, b, path, hex_out);
    if (r != SEMANTIC_OK) { unlink(path); semantic_builder_destroy(b); semantic_type_registry_destroy(reg); return 1; }

    semantic_segment_record read_seg;
    hacf_digest read_digest;
    r = semantic_segment_read(path, &read_seg, &read_digest);
    if (r != SEMANTIC_OK) { unlink(path); semantic_builder_destroy(b); semantic_type_registry_destroy(reg); return 1; }
    if (memcmp(read_seg.segment_identity.bytes, read_digest.bytes, 32) != 0) { unlink(path); semantic_builder_destroy(b); semantic_type_registry_destroy(reg); return 1; }

    unlink(path);
    semantic_builder_destroy(b);
    semantic_type_registry_destroy(reg);
    return 0;
}

int test_corrupt_segment_rejected(void) {
    const char *path = "/tmp/test_segment_corrupt.sf";
    unlink(path);

    FILE *f = fopen(path, "w");
    if (f) { fputs("garbage data", f); fclose(f); }

    semantic_segment_record seg;
    hacf_digest digest;
    int r = semantic_segment_read(path, &seg, &digest);

    unlink(path);
    return (r != SEMANTIC_OK) ? 0 : 1;
}

int test_corrupt_manifest_rejected(void) {
    const char *path = "/tmp/test_manifest_corrupt.sf";
    unlink(path);

    FILE *f = fopen(path, "w");
    if (f) { fputs("garbage manifest", f); fclose(f); }

    semantic_snapshot_manifest m;
    int r = semantic_snapshot_read(path, &m);

    unlink(path);
    return (r != SEMANTIC_OK) ? 0 : 1;
}

int test_segment_storage_audit(void) {
    semantic_type_registry *reg;
    hacf_digest reg_digest;
    setup_registry(&reg, &reg_digest);

    hacf_digest genesis;
    semantic_genesis_identity(&reg_digest, &genesis);

    semantic_hypergraph_builder *b = semantic_builder_create(reg);
    semantic_segment_record seg;
    semantic_segment_build(b, reg, &genesis, &seg);

    const char *path = "/tmp/test_segment_audit.sf";
    unlink(path);
    char hex_out[65];
    int r = semantic_segment_write(&seg, b, path, hex_out);
    if (r != SEMANTIC_OK) { unlink(path); semantic_builder_destroy(b); semantic_type_registry_destroy(reg); return 1; }

    FILE *f = fopen(path, "rb");
    if (!f) { unlink(path); semantic_builder_destroy(b); semantic_type_registry_destroy(reg); return 1; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fclose(f);

    int ok = (sz >= (long)sizeof(semantic_segment_record));
    unlink(path);
    semantic_builder_destroy(b);
    semantic_type_registry_destroy(reg);
    return ok ? 0 : 1;
}

int main(void) {
    printf("Running segment/snapshot tests...\n");

    int results[] = {
        test_atomic_no_replace_publication(),
        test_pre_existing_destination_preserved(),
        test_segment_read_verify(),
        test_corrupt_segment_rejected(),
        test_corrupt_manifest_rejected(),
        test_segment_storage_audit(),
    };

    int pass = 0, total = sizeof(results) / sizeof(results[0]);
    for (int i = 0; i < total; i++) {
        if (results[i] == 0) pass++;
        else printf("FAILED test %d\n", i);
    }

    printf("Segment/snapshot tests: %d/%d passed\n", pass, total);
    return (pass == total) ? 0 : 1;
}