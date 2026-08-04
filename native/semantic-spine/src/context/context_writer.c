#define _POSIX_C_SOURCE 200809L
/* context_writer.c — Atomic persistence for P2 context objects.
 *
 * Publication: same-dir temp → full write → fsync → atomic rename → dir fsync.
 * Pre-existing destination is never overwritten.
 */
#include "elpis_semantic/context_requirement_set.h"
#include "elpis_semantic/context_deficit_policy.h"
#include "elpis_semantic/context_deficit_report.h"
#include "elpis_semantic/retrieval_requirement.h"
#include "elpis_semantic/retrieval_requirement_bundle.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <errno.h>

/* ──────────────────────────────────────────────────────────────────── */
/* Internal wire-format helpers                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum context_wire_magic {
    MAGIC_REQUIREMENT_SET    = 0x52515300u, /* "RQS\0" */
    MAGIC_DEFICIT_POLICY     = 0x44504C00u, /* "DPL\0" */
    MAGIC_DEFICIT_REPORT     = 0x44525000u, /* "DRP\0" */
    MAGIC_RETRIEVAL_REQ      = 0x52525100u, /* "RRQ\0" */
    MAGIC_RETRIEVAL_BUNDLE   = 0x52424E00u  /* "RBN\0" */
} context_wire_magic;

/* Write a magic + size header + payload atomically.
 * Returns SEMANTIC_OK or SEMANTIC_E_IO. */
static int atomic_publish(const char *dest_path,
                          uint32_t magic,
                          const uint8_t *data, size_t data_len) {
    /* Check destination doesn't already exist */
    if (access(dest_path, F_OK) == 0) {
        return SEMANTIC_E_IO; /* pre-existing — never overwrite */
    }

    /* Derive temp path in same directory */
    const char *dir_sep = strrchr(dest_path, '/');
    if (!dir_sep) return SEMANTIC_E_IO;
    size_t dir_len = (size_t)(dir_sep - dest_path);

    char *tmp_path = malloc(dir_len + 32); /* "/dir/XXXXXX" */
    if (!tmp_path) return SEMANTIC_E_NOMEM;
    memcpy(tmp_path, dest_path, dir_len);
    memcpy(tmp_path + dir_len, "/XXXXXX", 8);
    tmp_path[dir_len + 8] = '\0';

    int fd = mkstemp(tmp_path);
    if (fd < 0) {
        free(tmp_path);
        return SEMANTIC_E_IO;
    }

    /* Write magic + total record size (header + payload) */
    uint32_t record_size = (uint32_t)(4 + 4 + data_len); /* magic + data_len + data */
    ssize_t n;

    n = write(fd, &magic, 4);
    if ((size_t)n != 4) goto fail;
    n = write(fd, &record_size, 4);
    if ((size_t)n != 4) goto fail;
    n = write(fd, data, data_len);
    if ((size_t)n != data_len) goto fail;

    /* Compute on-disk hash of the record (magic+size+data) */
    hacf_digest disk_hash;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, &magic, 4);
    elpis_sha256_update(&ctx, &record_size, 4);
    elpis_sha256_update(&ctx, data, data_len);
    elpis_sha256_final(&ctx, disk_hash.bytes);

    /* Write hash at end */
    n = write(fd, disk_hash.bytes, HACF_DIGEST_BYTES);
    if ((size_t)n != HACF_DIGEST_BYTES) goto fail;

    /* fsync file */
    if (fsync(fd) != 0) goto fail;
    close(fd);

    /* Atomic rename */
    if (rename(tmp_path, dest_path) != 0) {
        unlink(tmp_path);
        free(tmp_path);
        return SEMANTIC_E_IO;
    }

    /* fsync directory */
    {
        char *dir_only = malloc(dir_len + 1);
        if (dir_only) {
            memcpy(dir_only, dest_path, dir_len);
            dir_only[dir_len] = '\0';
            int dfd = open(dir_only, O_RDONLY);
            if (dfd >= 0) {
                fsync(dfd);
                close(dfd);
            }
            free(dir_only);
        }
    }

    free(tmp_path);
    return SEMANTIC_OK;

fail:
    close(fd);
    unlink(tmp_path);
    free(tmp_path);
    return SEMANTIC_E_IO;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Public write functions                                              */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_write_requirement_set(const char *path,
                                 const elpis_semantic_context_requirement_set_v1 *set) {
    if (!path || !set) return SEMANTIC_E_INVAL;
    return atomic_publish(path, MAGIC_REQUIREMENT_SET,
                          (const uint8_t *)set, sizeof(*set));
}

int elpis_write_deficit_policy(const char *path,
                                const elpis_semantic_context_deficit_policy_v1 *policy) {
    if (!path || !policy) return SEMANTIC_E_INVAL;
    return atomic_publish(path, MAGIC_DEFICIT_POLICY,
                          (const uint8_t *)policy, sizeof(*policy));
}

int elpis_write_deficit_report(const char *path,
                                const elpis_semantic_context_deficit_report_v1 *report) {
    if (!path || !report) return SEMANTIC_E_INVAL;
    return atomic_publish(path, MAGIC_DEFICIT_REPORT,
                          (const uint8_t *)report, sizeof(*report));
}

int elpis_write_retrieval_requirement(const char *path,
                                       const elpis_semantic_retrieval_requirement_v1 *req) {
    if (!path || !req) return SEMANTIC_E_INVAL;
    return atomic_publish(path, MAGIC_RETRIEVAL_REQ,
                          (const uint8_t *)req, sizeof(*req));
}

int elpis_write_retrieval_bundle(const char *path,
                                  const elpis_semantic_retrieval_requirement_bundle_v1 *bundle) {
    if (!path || !bundle) return SEMANTIC_E_INVAL;
    return atomic_publish(path, MAGIC_RETRIEVAL_BUNDLE,
                          (const uint8_t *)bundle, sizeof(*bundle));
}
