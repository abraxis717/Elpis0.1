/* segment_writer.c — Immutable semantic segment construction and atomic storage.
 *
 * Segment identity: SHA-256("elpis.semantic.segment.v1" || canonical_payload).
 * Canonical payload: ABI version, type_registry_digest, prior_snapshot,
 * canonical records serialized in builder order, HACF ops, HACF digests.
 *
 * Genesis: SHA-256("elpis.semantic.genesis.v1" || type_registry_digest).
 *
 * Publication: same-dir temp → write → fsync → rename → dir fsync. O_EXCL.
 */
#define _DEFAULT_SOURCE
#include "elpis_semantic/segment.h"
#include "elpis_semantic/hacf_mapping.h"
#include "builder_internal.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <errno.h>
#include <arpa/inet.h>

int semantic_genesis_identity(const hacf_digest *type_registry_digest, hacf_digest *genesis_out) {
    if (!type_registry_digest || !genesis_out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char *domain = "elpis.semantic.genesis.v1";
    uint32_t be_len = htonl((uint32_t)strlen(domain));
    elpis_sha256_update(&ctx, &be_len, 4);
    elpis_sha256_update(&ctx, domain, strlen(domain));
    elpis_sha256_update(&ctx, type_registry_digest->bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, genesis_out->bytes);
    return SEMANTIC_OK;
}

int semantic_segment_build(const semantic_hypergraph_builder *builder,
                            const semantic_type_registry *registry,
                            const hacf_digest *prior_snapshot,
                            semantic_segment_record *segment_out) {
    if (!builder || !registry || !prior_snapshot || !segment_out) return SEMANTIC_E_INVAL;

    memset(segment_out, 0, sizeof(*segment_out));
    segment_out->abi_version = SEMANTIC_SEGMENT_ABI_VERSION;

    /* Get registry digest. */
    hacf_digest reg_digest;
    if (semantic_type_registry_digest(registry, &reg_digest) != SEMANTIC_OK)
        return SEMANTIC_E_INVAL;
    segment_out->type_registry_digest = reg_digest;
    segment_out->prior_snapshot_digest = *prior_snapshot;

    segment_out->node_count = semantic_builder_node_count(builder);
    segment_out->assertion_count = semantic_builder_assertion_count(builder);
    segment_out->hyperedge_count = semantic_builder_hyperedge_count(builder);
    segment_out->incidence_count = semantic_builder_incidence_count(builder);

    /* Map to HACF ops. */
    hacf_graph_op *ops = NULL;
    uint32_t op_count = 0;
    int r = semantic_map_to_hacf_ops(builder, &ops, &op_count);
    if (r != SEMANTIC_OK) return r;
    segment_out->hacf_op_count = op_count;

    /* Compute HACF delta and next snapshot. */
    if (semantic_compute_hacf_delta(prior_snapshot, ops, op_count,
                                    &segment_out->hacf_delta_digest,
                                    &segment_out->hacf_next_snapshot) != SEMANTIC_OK) {
        semantic_free_hacf_ops(ops);
        return SEMANTIC_E_INVAL;
    }

    /* Compute segment identity. */
    r = semantic_segment_identity(segment_out, &segment_out->segment_identity);
    if (r != SEMANTIC_OK) {
        semantic_free_hacf_ops(ops);
        return r;
    }

    /* HACF package digest = segment identity for P0. */
    segment_out->hacf_package_digest = segment_out->segment_identity;

    semantic_free_hacf_ops(ops);
    return SEMANTIC_OK;
}

int semantic_segment_identity(const semantic_segment_record *segment, hacf_digest *out) {
    if (!segment || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    const char *domain = "elpis.semantic.segment.v1";
    uint32_t be_len = htonl((uint32_t)strlen(domain));
    elpis_sha256_update(&ctx, &be_len, 4);
    elpis_sha256_update(&ctx, domain, strlen(domain));

    uint32_t be = htonl(segment->abi_version);
    elpis_sha256_update(&ctx, &be, 4);
    elpis_sha256_update(&ctx, segment->type_registry_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, segment->prior_snapshot_digest.bytes, HACF_DIGEST_BYTES);
    be = htonl(segment->node_count);
    elpis_sha256_update(&ctx, &be, 4);
    be = htonl(segment->assertion_count);
    elpis_sha256_update(&ctx, &be, 4);
    be = htonl(segment->hyperedge_count);
    elpis_sha256_update(&ctx, &be, 4);
    be = htonl(segment->incidence_count);
    elpis_sha256_update(&ctx, &be, 4);
    be = htonl(segment->hacf_op_count);
    elpis_sha256_update(&ctx, &be, 4);
    elpis_sha256_update(&ctx, segment->hacf_delta_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, segment->hacf_next_snapshot.bytes, HACF_DIGEST_BYTES);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

/* Atomic write: temp → write → fsync → rename → dir fsync. O_EXCL on destination. */
int semantic_segment_write(const semantic_segment_record *segment,
                            const semantic_hypergraph_builder *builder,
                            const char *path,
                            char segment_hex_out[65]) {
    if (!segment || !path) return SEMANTIC_E_INVAL;

    /* Create temp file in same directory. */
    char dir[4096];
    strncpy(dir, path, sizeof(dir) - 1);
    dir[sizeof(dir) - 1] = '\0';
    char *last_slash = strrchr(dir, '/');
    if (last_slash) *(last_slash + 1) = '\0';
    else strcpy(dir, ".");

    char tmp_path[4096];
    snprintf(tmp_path, sizeof(tmp_path), "%s.tmp_segment_XXXXXX", dir);
    int fd = mkstemp(tmp_path);
    if (fd < 0) return SEMANTIC_E_IO;

    /* Write segment record. */
    ssize_t written = write(fd, segment, sizeof(*segment));
    if ((uint32_t)written != sizeof(*segment)) {
        close(fd);
        unlink(tmp_path);
        return SEMANTIC_E_IO;
    }

    /* Write builder records after the segment header. */
    for (uint32_t i = 0; i < builder->node_count; i++) {
        const elpis_semantic_node_v1 *n = semantic_builder_get_node(builder, i);
        written = write(fd, n, sizeof(*n));
        if ((uint32_t)written != sizeof(*n)) { close(fd); unlink(tmp_path); return SEMANTIC_E_IO; }
    }
    for (uint32_t i = 0; i < builder->assertion_count; i++) {
        const elpis_semantic_assertion_v1 *a = semantic_builder_get_assertion(builder, i);
        written = write(fd, a, sizeof(*a));
        if ((uint32_t)written != sizeof(*a)) { close(fd); unlink(tmp_path); return SEMANTIC_E_IO; }
    }
    for (uint32_t i = 0; i < builder->hyperedge_count; i++) {
        const elpis_semantic_hyperedge_v1 *e = semantic_builder_get_hyperedge(builder, i);
        written = write(fd, e, sizeof(*e));
        if ((uint32_t)written != sizeof(*e)) { close(fd); unlink(tmp_path); return SEMANTIC_E_IO; }
    }
    for (uint32_t i = 0; i < builder->incidence_count; i++) {
        const elpis_semantic_incidence_v1 *inc = semantic_builder_get_incidence(builder, i);
        written = write(fd, inc, sizeof(*inc));
        if ((uint32_t)written != sizeof(*inc)) { close(fd); unlink(tmp_path); return SEMANTIC_E_IO; }
    }

    /* fsync file. */
    if (fsync(fd) != 0) { close(fd); unlink(tmp_path); return SEMANTIC_E_IO; }
    close(fd);

    /* Check destination doesn't exist (no-replace). */
    struct stat st;
    if (stat(path, &st) == 0) {
        unlink(tmp_path);
        return SEMANTIC_E_DUPLICATE;
    }

    /* Atomic rename. */
    if (rename(tmp_path, path) != 0) {
        unlink(tmp_path);
        return SEMANTIC_E_IO;
    }

    /* fsync directory. */
    int dir_fd = open(dir, O_RDONLY);
    if (dir_fd >= 0) { fsync(dir_fd); close(dir_fd); }

    /* Output hex digest. */
    if (segment_hex_out) {
        char hex[65];
        elpis_hex32(segment->segment_identity.bytes, hex);
        strcpy(segment_hex_out, hex);
    }

    return SEMANTIC_OK;
}

int semantic_segment_validate(const semantic_segment_record *segment,
                               const hacf_digest *expected_segment_digest) {
    if (!segment || !expected_segment_digest) return 0;
    hacf_digest computed;
    if (semantic_segment_identity(segment, &computed) != SEMANTIC_OK) return 0;
    return memcmp(computed.bytes, expected_segment_digest->bytes, HACF_DIGEST_BYTES) == 0;
}
