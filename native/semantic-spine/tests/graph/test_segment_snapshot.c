#define _POSIX_C_SOURCE 200809L
/* test_segment_snapshot.c — Segment and snapshot persistence tests. */
#include "elpis_semantic/segment.h"
#include "elpis_semantic/snapshot.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>

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

static int test_manifest_count_boundaries(void) {
    semantic_snapshot_manifest *m = semantic_snapshot_create();
    if (!m) return 1;
    const uint32_t counts[] = {0, 1, SEMANTIC_MAX_SEGMENTS - 1,
        SEMANTIC_MAX_SEGMENTS, SEMANTIC_MAX_SEGMENTS + 1, UINT32_MAX};
    int failed = 0;
    for (size_t i = 0; i < sizeof(counts) / sizeof(counts[0]); ++i) {
        m->segment_count = counts[i];
        hacf_digest before = m->manifest_digest;
        int valid = counts[i] > 0 && counts[i] <= SEMANTIC_MAX_SEGMENTS;
        int rc = semantic_snapshot_finalize(m);
        failed |= check(rc == (valid ? SEMANTIC_OK : SEMANTIC_E_INVAL),
                        "finalize count boundary", (int)i);
        if (!valid)
            failed |= check(memcmp(&before, &m->manifest_digest, sizeof(before)) == 0,
                            "invalid finalize preserves identity", (int)i);
        failed |= check(semantic_snapshot_validate(m) ==
                        (valid ? SEMANTIC_OK : SEMANTIC_E_INVAL),
                        "validate count boundary", (int)i);
    }
    /* Exercise serialized input through the public persistence reader too. */
    char path[128];
    snprintf(path, sizeof(path), "/tmp/elpis-h02-%ld.sf", (long)getpid());
    m->segment_count = SEMANTIC_MAX_SEGMENTS + 1;
    FILE *f = fopen(path, "wb");
    if (!f) { semantic_snapshot_destroy(m); return 1; }
    failed |= fwrite(m, sizeof(*m), 1, f) != 1;
    failed |= fclose(f) != 0;
    failed |= check(semantic_snapshot_read(path, m) == SEMANTIC_E_INVAL,
                    "out-of-range persisted count rejected", 6);
    unlink(path);
    semantic_snapshot_destroy(m);
    return failed;
}

static int test_manifest_read_transaction(void) {
    semantic_snapshot_manifest *valid = semantic_snapshot_create();
    semantic_snapshot_manifest *out = semantic_snapshot_create();
    semantic_snapshot_manifest *before = semantic_snapshot_create();
    if (!valid || !out || !before) {
        free(valid); free(out); free(before);
        return 1;
    }
    valid->segment_count = 1;
    int failed = check(semantic_snapshot_finalize(valid) == SEMANTIC_OK,
                       "prepare manifest", 0);
    char path[128];
    snprintf(path, sizeof(path), "/tmp/elpis-read-%ld.sf", (long)getpid());
    /* Valid, truncated, trailing bytes, and digest-corrupted records. */
    for (int kind = 0; kind < 4; ++kind) {
        memset(out, 0xa5, sizeof(*out));
        *before = *out;
        semantic_snapshot_manifest record = *valid;
        if (kind == 3) record.manifest_digest.bytes[0] ^= 1;
        FILE *f = fopen(path, "wb");
        if (!f) { failed = 1; break; }
        size_t size = sizeof(record) - (kind == 1 ? 1 : 0);
        failed |= fwrite(&record, 1, size, f) != size;
        if (kind == 2) failed |= fputc(0, f) == EOF;
        failed |= fclose(f) != 0;
        int expected[] = {SEMANTIC_OK, SEMANTIC_E_IO,
                          SEMANTIC_E_INVAL, SEMANTIC_E_DIGEST};
        failed |= check(semantic_snapshot_read(path, out) == expected[kind],
                        "read status", kind);
        failed |= check(memcmp(out, kind == 0 ? valid : before, sizeof(*out)) == 0,
                        "read publishes only complete validated state", kind);
    }
    unlink(path);
    failed |= check(semantic_snapshot_read(path, out) == SEMANTIC_E_IO,
                    "missing file", 4);
    failed |= check(memcmp(out, before, sizeof(*out)) == 0,
                    "open failure preserves state", 4);
    free(valid); free(out); free(before);
    return failed;
}

static int test_segment_publication_ownership(void) {
    char dir[] = "./segment-publish-XXXXXX";
    if (!mkdtemp(dir)) return 1;
    char path[128];
    snprintf(path, sizeof(path), "%s/segment.sf", dir);
    semantic_type_registry *reg;
    hacf_digest registry_digest, genesis;
    setup_registry(&reg, &registry_digest);
    semantic_genesis_identity(&registry_digest, &genesis);
    semantic_hypergraph_builder *builder = semantic_builder_create(reg);
    semantic_segment_record segment;
    int failed = check(semantic_segment_build(builder, reg, &genesis, &segment) ==
                       SEMANTIC_OK, "build publication fixture", 0);
    char hex[65], sentinel[65];
    memset(hex, 'z', sizeof(hex));
    memcpy(sentinel, hex, sizeof(hex));
    failed |= check(symlink("missing-target", path) == 0, "create dangling destination", 0);
    failed |= check(semantic_segment_write(&segment, builder, path, hex) ==
                    SEMANTIC_E_DUPLICATE, "dangling destination preserved", 0);
    char target[64] = {0};
    failed |= check(readlink(path, target, sizeof(target)) == 14 &&
                    memcmp(target, "missing-target", 14) == 0,
                    "destination remains original symlink", 0);
    failed |= check(memcmp(hex, sentinel, sizeof(hex)) == 0,
                    "rejected publication preserves output", 0);
    unlink(path);
    failed |= check(semantic_segment_write(&segment, NULL, path, hex) ==
                    SEMANTIC_E_INVAL, "null builder rejected", 0);

    int gate[2];
    if (pipe(gate) != 0) { failed = 1; goto cleanup; }
    pid_t children[8];
    unsigned count = 0;
    for (; count < 8; ++count) {
        children[count] = fork();
        if (children[count] < 0) { failed = 1; break; }
        if (children[count] == 0) {
            close(gate[1]);
            char token;
            if (read(gate[0], &token, 1) < 0) _exit(3);
            close(gate[0]);
            int rc = semantic_segment_write(&segment, builder, path, hex);
            if (rc == SEMANTIC_OK) {
                char expected[65];
                elpis_hex32(segment.segment_identity.bytes, expected);
                _exit(strcmp(hex, expected) == 0 ? 0 : 3);
            }
            _exit(rc == SEMANTIC_E_DUPLICATE &&
                  memcmp(hex, sentinel, sizeof(hex)) == 0 ? 2 : 3);
        }
    }
    close(gate[0]);
    close(gate[1]); /* EOF releases every publisher. */
    unsigned winners = 0;
    for (unsigned i = 0; i < count; ++i) {
        int status;
        if (waitpid(children[i], &status, 0) != children[i] || !WIFEXITED(status)) {
            failed = 1; continue;
        }
        winners += WEXITSTATUS(status) == 0;
        failed |= WEXITSTATUS(status) != 0 && WEXITSTATUS(status) != 2;
    }
    failed |= check(winners == 1, "exactly one publisher wins", 0);
    semantic_segment_record published;
    failed |= check(semantic_segment_read(path, &published, NULL) == SEMANTIC_OK,
                    "published file verifies", 0);
    failed |= check(memcmp(&segment, &published, sizeof(segment)) == 0,
                    "published identity and content preserved", 0);
    unlink(path);
cleanup:
    semantic_builder_destroy(builder);
    semantic_type_registry_destroy(reg);
    failed |= check(rmdir(dir) == 0, "temporary files cleaned", 0);
    return failed;
}

static int test_manifest_write_validation(void) {
    char dir[] = "./snapshot-publish-XXXXXX";
    if (!mkdtemp(dir)) return 1;
    char path[128];
    snprintf(path, sizeof(path), "%s/snapshot.sf", dir);
    semantic_snapshot_manifest *m = semantic_snapshot_create();
    semantic_snapshot_manifest *published = semantic_snapshot_create();
    semantic_snapshot_manifest *readback = semantic_snapshot_create();
    if (!m || !published || !readback) {
        free(m); free(published); free(readback); rmdir(dir); return 1;
    }
    m->segment_count = 1;
    int failed = check(semantic_snapshot_finalize(m) == SEMANTIC_OK,
                       "prepare writable manifest", 0);
    *published = *m;
    char hex[65], expected[65];
    elpis_hex32(m->manifest_digest.bytes, expected);
    failed |= check(semantic_snapshot_write(m, path, hex) == SEMANTIC_OK,
                    "publish valid manifest", 0);
    failed |= check(strcmp(hex, expected) == 0, "published digest", 0);
    for (unsigned kind = 0; kind < 4; ++kind) {
        *m = *published;
        if (kind == 0) m->segment_count = 0;
        if (kind == 1) m->segment_count = SEMANTIC_MAX_SEGMENTS + 1;
        if (kind == 2) m->manifest_digest.bytes[0] ^= 1;
        if (kind == 3) m->reserved[0] = 1;
        const int errors[] = {SEMANTIC_E_INVAL, SEMANTIC_E_INVAL,
                              SEMANTIC_E_DIGEST, SEMANTIC_E_RESERVATION};
        failed |= check(semantic_snapshot_write(m, path, hex) == errors[kind],
                        "invalid manifest cannot publish", kind);
        failed |= check(strcmp(hex, expected) == 0, "rejected write preserves digest", kind);
        failed |= check(semantic_snapshot_read(path, readback) == SEMANTIC_OK &&
                        memcmp(readback, published, sizeof(*published)) == 0,
                        "rejected write preserves destination", kind);
    }
    /* Valid successor publication still replaces the manifest atomically. */
    *m = *published;
    m->assertion_count++;
    failed |= check(semantic_snapshot_finalize(m) == SEMANTIC_OK &&
                    semantic_snapshot_write(m, path, hex) == SEMANTIC_OK &&
                    semantic_snapshot_read(path, readback) == SEMANTIC_OK &&
                    memcmp(readback, m, sizeof(*m)) == 0,
                    "valid successor replaces manifest", 4);
    unlink(path);
    failed |= check(semantic_snapshot_write(published, "./missing-snapshot-dir/file", hex) ==
                    SEMANTIC_E_IO, "publication IO failure", 5);
    failed |= check(rmdir(dir) == 0, "snapshot temporary files cleaned", 5);
    free(m); free(published); free(readback);
    return failed;
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
        test_manifest_count_boundaries(),
        test_manifest_read_transaction(),
        test_segment_publication_ownership(),
        test_manifest_write_validation(),
    };

    int pass = 0, total = sizeof(results) / sizeof(results[0]);
    for (int i = 0; i < total; i++) {
        if (results[i] == 0) pass++;
        else printf("FAILED test %d\n", i);
    }

    printf("Segment/snapshot tests: %d/%d passed\n", pass, total);
    return (pass == total) ? 0 : 1;
}