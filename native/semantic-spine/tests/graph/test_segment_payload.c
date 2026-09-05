/* Production writer/reader contract: native header, nodes, assertions,
 * hyperedges, incidences. Checks remain active in Release builds too. */
#define _POSIX_C_SOURCE 200809L
#include "elpis_semantic/segment.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/wait.h>

#define REQUIRE(expr) do { if (!(expr)) { \
    fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #expr); exit(1); \
} } while (0)

static void rejected(const char *path) {
    semantic_segment_record out, before;
    hacf_digest digest, digest_before;
    memset(&out, 0xa5, sizeof(out));
    memset(&digest, 0x5a, sizeof(digest));
    before = out;
    digest_before = digest;
    REQUIRE(semantic_segment_read(path, &out, &digest) != SEMANTIC_OK);
    REQUIRE(memcmp(&out, &before, sizeof(out)) == 0);
    REQUIRE(memcmp(&digest, &digest_before, sizeof(digest)) == 0);
}

static void write_bytes(const char *path, const void *bytes, size_t size) {
    FILE *f = fopen(path, "wb");
    REQUIRE(f);
    REQUIRE(fwrite(bytes, 1, size, f) == size);
    REQUIRE(fclose(f) == 0);
}

static void retag(semantic_segment_record *s) {
    REQUIRE(semantic_segment_identity(s, &s->segment_identity) == SEMANTIC_OK);
    s->hacf_package_digest = s->segment_identity;
}

static void stream_case(const char *path, const void *bytes, size_t size,
                        const semantic_segment_record *expected) {
    REQUIRE(mkfifo(path, 0600) == 0);
    pid_t child = fork();
    REQUIRE(child >= 0);
    if (child == 0) { write_bytes(path, bytes, size); _exit(0); }
    if (expected) {
        semantic_segment_record out;
        hacf_digest digest;
        REQUIRE(semantic_segment_read(path, &out, &digest) == SEMANTIC_OK);
        REQUIRE(memcmp(&out, expected, sizeof(out)) == 0);
        REQUIRE(memcmp(&digest, &expected->segment_identity, sizeof(digest)) == 0);
    } else rejected(path);
    int status;
    REQUIRE(waitpid(child, &status, 0) == child);
    REQUIRE(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    REQUIRE(unlink(path) == 0);
}

int main(void) {
    char dir[] = "./segment-payload-XXXXXX";
    REQUIRE(mkdtemp(dir));
    char path[128], bad[128], fifo[128];
    snprintf(path, sizeof(path), "%s/valid.sf", dir);
    snprintf(bad, sizeof(bad), "%s/invalid.sf", dir);
    snprintf(fifo, sizeof(fifo), "%s/stream", dir);
    semantic_type_registry *reg = semantic_type_registry_create();
    REQUIRE(reg);
    semantic_node_type_entry nt = {.node_type = SEMANTIC_NODE_NAMESPACE | 1,
        .semantic_flag_mask = SEMANTIC_NODE_FLAG_MASK, .min_authority = 0, .max_authority = 3};
    semantic_incidence_role_entry role = {.incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1,
        .participant_flag_mask = SEMANTIC_PARTICIPANT_FLAG_MASK};
    semantic_hyperedge_type_entry et = {.hyperedge_type = SEMANTIC_HYPEREDGE_NAMESPACE | 1,
        .min_participants = 2, .max_participants = 2, .role_count = 1,
        .roles = {{.incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 1,
                   .min_cardinality = 2, .max_cardinality = 2, .is_ordered = 1}}};
    REQUIRE(semantic_type_registry_add_node_type(reg, &nt) == SEMANTIC_OK);
    REQUIRE(semantic_type_registry_add_incidence_role(reg, &role) == SEMANTIC_OK);
    REQUIRE(semantic_type_registry_add_hyperedge_type(reg, &et) == SEMANTIC_OK);
    hacf_digest registry_digest, genesis;
    REQUIRE(semantic_type_registry_seal(reg, &registry_digest) == SEMANTIC_OK);
    REQUIRE(semantic_genesis_identity(&registry_digest, &genesis) == SEMANTIC_OK);
    semantic_hypergraph_builder *b = semantic_builder_create(reg);
    REQUIRE(b);
    elpis_semantic_node_v1 nodes[2] = {{0}};
    for (unsigned i = 0; i < 2; ++i) {
        nodes[i].abi_version = SEMANTIC_ABI_VERSION;
        nodes[i].node_type = nt.node_type;
        nodes[i].payload_digest.bytes[0] = (uint8_t)(i + 1);
        REQUIRE(elpis_semantic_node_identity(&nodes[i], &nodes[i].node_identity) == SEMANTIC_OK);
        REQUIRE(semantic_builder_add_node(b, &nodes[i]) == SEMANTIC_OK);
        elpis_semantic_assertion_v1 a = {0};
        a.abi_version = SEMANTIC_ABI_VERSION;
        a.asserted_object_kind = SEMANTIC_OBJECT_KIND_NODE;
        a.asserted_object_digest = nodes[i].node_identity;
        a.provenance_digest.bytes[0] = 9;
        a.authority = 1;
        REQUIRE(elpis_semantic_assertion_identity(&a, &a.assertion_identity) == SEMANTIC_OK);
        REQUIRE(semantic_builder_add_assertion(b, &a) == SEMANTIC_OK);
    }
    elpis_semantic_hyperedge_v1 edge = {0};
    edge.abi_version = SEMANTIC_ABI_VERSION;
    edge.hyperedge_type = et.hyperedge_type;
    edge.participant_count = 2;
    for (unsigned i = 0; i < 2; ++i) {
        edge.participants[i].node_identity = nodes[i].node_identity;
        edge.participants[i].incidence_role = role.incidence_role;
        edge.participants[i].ordinal = i;
    }
    REQUIRE(elpis_semantic_canonicalize_participants(edge.participants, 2) == SEMANTIC_OK);
    REQUIRE(elpis_semantic_hyperedge_identity(&edge, &edge.hyperedge_identity) == SEMANTIC_OK);
    REQUIRE(semantic_builder_add_hyperedge(b, &edge) == SEMANTIC_OK);
    for (unsigned i = 0; i < 2; ++i) {
        elpis_semantic_assertion_v1 a = {0};
        a.abi_version = SEMANTIC_ABI_VERSION;
        a.asserted_object_kind = SEMANTIC_OBJECT_KIND_HYPEREDGE;
        a.asserted_object_digest = edge.hyperedge_identity;
        a.provenance_digest.bytes[0] = (uint8_t)(i + 1);
        a.authority = i + 1;
        REQUIRE(elpis_semantic_assertion_identity(&a, &a.assertion_identity) == SEMANTIC_OK);
        REQUIRE(semantic_builder_add_assertion(b, &a) == SEMANTIC_OK);
        elpis_semantic_incidence_v1 inc = {0};
        inc.abi_version = SEMANTIC_ABI_VERSION;
        inc.hyperedge_digest = edge.hyperedge_identity;
        inc.node_digest = nodes[i].node_identity;
        inc.incidence_role = role.incidence_role;
        inc.ordinal = i;
        REQUIRE(elpis_semantic_incidence_identity(&inc, &inc.incidence_identity) == SEMANTIC_OK);
        REQUIRE(semantic_builder_add_incidence(b, &inc) == SEMANTIC_OK);
    }
    semantic_segment_record segment, out;
    hacf_digest digest;
    REQUIRE(semantic_segment_build(b, reg, &genesis, &segment) == SEMANTIC_OK);
    REQUIRE(segment.hacf_op_count == 8);
    REQUIRE(semantic_segment_write(&segment, b, path, NULL) == SEMANTIC_OK);
    REQUIRE(semantic_segment_read(path, &out, &digest) == SEMANTIC_OK);
    REQUIRE(memcmp(&out, &segment, sizeof(out)) == 0);
    REQUIRE(memcmp(&digest, &segment.segment_identity, sizeof(digest)) == 0);
    REQUIRE(semantic_segment_read(path, &out, NULL) == SEMANTIC_OK);

    const size_t node_offset = sizeof(segment);
    const size_t assertion_offset = node_offset + 2 * sizeof(elpis_semantic_node_v1);
    const size_t edge_offset = assertion_offset + 4 * sizeof(elpis_semantic_assertion_v1);
    const size_t incidence_offset = edge_offset + sizeof(elpis_semantic_hyperedge_v1);
    const size_t size = incidence_offset + 2 * sizeof(elpis_semantic_incidence_v1);
    struct stat st;
    REQUIRE(stat(path, &st) == 0 && (size_t)st.st_size == size);
    unsigned char *bytes = malloc(size + 1), *copy = malloc(size + 1);
    REQUIRE(bytes && copy);
    FILE *f = fopen(path, "rb");
    REQUIRE(f && fread(bytes, 1, size, f) == size);
    REQUIRE(fclose(f) == 0);
    bytes[size] = 0;

    const size_t cuts[] = {0, sizeof(segment) - 1, node_offset,
        assertion_offset - 1, edge_offset - 1, incidence_offset - 1, size - 1};
    for (unsigned i = 0; i < sizeof(cuts) / sizeof(cuts[0]); ++i) {
        write_bytes(bad, bytes, cuts[i]);
        rejected(bad);
    }
    write_bytes(bad, bytes, size + 1);
    rejected(bad);

    const size_t corruptions[] = {
        offsetof(semantic_segment_record, reserved),
        offsetof(semantic_segment_record, hacf_package_digest),
        node_offset + offsetof(elpis_semantic_node_v1, payload_digest),
        node_offset + offsetof(elpis_semantic_node_v1, reserved),
        assertion_offset + offsetof(elpis_semantic_assertion_v1, provenance_digest),
        assertion_offset + offsetof(elpis_semantic_assertion_v1, reserved),
        edge_offset + offsetof(elpis_semantic_hyperedge_v1, payload_digest),
        edge_offset + offsetof(elpis_semantic_hyperedge_v1, reserved),
        edge_offset + offsetof(elpis_semantic_hyperedge_v1, participants) +
                      offsetof(elpis_semantic_participant_descriptor, reserved),
        incidence_offset + offsetof(elpis_semantic_incidence_v1, node_digest),
        incidence_offset + offsetof(elpis_semantic_incidence_v1, reserved)
    };
    for (unsigned i = 0; i < sizeof(corruptions) / sizeof(corruptions[0]); ++i) {
        memcpy(copy, bytes, size);
        copy[corruptions[i]] ^= 1;
        write_bytes(bad, copy, size);
        rejected(bad);
    }
    /* Self-consistent header edits still cannot contradict the actual payload. */
    const size_t counts[] = {offsetof(semantic_segment_record, node_count),
        offsetof(semantic_segment_record, assertion_count),
        offsetof(semantic_segment_record, hyperedge_count),
        offsetof(semantic_segment_record, incidence_count)};
    for (unsigned i = 0; i < 4; ++i) {
        memcpy(copy, bytes, size);
        uint32_t extreme = UINT32_MAX;
        memcpy(copy + counts[i], &extreme, sizeof(extreme));
        retag((semantic_segment_record *)copy);
        write_bytes(bad, copy, size);
        rejected(bad);
    }
    for (unsigned kind = 0; kind < 10; ++kind) {
        memcpy(copy, bytes, size);
        semantic_segment_record *header = (semantic_segment_record *)copy;
        elpis_semantic_node_v1 *n = (elpis_semantic_node_v1 *)(copy + node_offset);
        elpis_semantic_assertion_v1 *a = (elpis_semantic_assertion_v1 *)(copy + assertion_offset);
        elpis_semantic_hyperedge_v1 *e = (elpis_semantic_hyperedge_v1 *)(copy + edge_offset);
        elpis_semantic_incidence_v1 *inc = (elpis_semantic_incidence_v1 *)(copy + incidence_offset);
        switch (kind) {
        case 0: header->hacf_op_count++; retag(header); break;
        case 1: header->hacf_delta_digest.bytes[0] ^= 1; retag(header); break;
        case 2: header->hacf_next_snapshot.bytes[0] ^= 1; retag(header); break;
        case 3: { elpis_semantic_node_v1 tmp = n[0]; n[0] = n[1]; n[1] = tmp; break; }
        case 4: n[1] = n[0]; break;
        case 5: e->participant_count = SEMANTIC_MAX_PARTICIPANTS + 1; break;
        case 6: a->provenance_digest.bytes[0] ^= 0x80;
            REQUIRE(elpis_semantic_assertion_identity(a, &a->assertion_identity) == SEMANTIC_OK); break;
        case 7: memset(&a->asserted_object_digest, 0, sizeof(hacf_digest));
            REQUIRE(elpis_semantic_assertion_identity(a, &a->assertion_identity) == SEMANTIC_OK); break;
        case 8: memset(&inc->node_digest, 0, sizeof(hacf_digest));
            REQUIRE(elpis_semantic_incidence_identity(inc, &inc->incidence_identity) == SEMANTIC_OK); break;
        case 9: memset(&e->participants[0].node_identity, 0, sizeof(hacf_digest));
            REQUIRE(elpis_semantic_hyperedge_identity(e, &e->hyperedge_identity) == SEMANTIC_OK); break;
        }
        write_bytes(bad, copy, size);
        rejected(bad);
    }
    /* FIFO cases exercise actual short reads and EOF independently of fstat. */
    stream_case(fifo, bytes, size, &segment);
    for (unsigned i = 1; i < sizeof(cuts) / sizeof(cuts[0]); ++i)
        stream_case(fifo, bytes, cuts[i], NULL);
    stream_case(fifo, bytes, size + 1, NULL);
    REQUIRE(unlink(bad) == 0);
    rejected(bad); /* open failure also preserves outputs */
    REQUIRE(unlink(path) == 0);
    REQUIRE(rmdir(dir) == 0);
    free(bytes); free(copy);
    semantic_builder_destroy(b);
    semantic_type_registry_destroy(reg);
    puts("PASS: complete segment payload validation");
    return 0;
}
