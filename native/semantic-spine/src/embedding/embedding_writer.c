/* embedding_writer.c — Immutable persistence for embedding objects.
 *
 * Atomic publication: temp write → fsync → rename (no-replace) → dir fsync.
 */
#define _DEFAULT_SOURCE
#include "elpis_semantic/embedding_storage.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <arpa/inet.h>

/* ──────────────────────────────────────────────────────────────────── */
/* File format                                                           */
/* ──────────────────────────────────────────────────────────────────── */

/* File header: magic(4) + version(4) + type(4) + record_size(4) + payload */
typedef struct embedding_file_header {
    uint32_t magic;
    uint32_t version;
    uint32_t file_type;
    uint32_t record_size;
    uint8_t  identity_digest[32];
} embedding_file_header;

/* ──────────────────────────────────────────────────────────────────── */
/* Atomic write helper                                                   */
/* ──────────────────────────────────────────────────────────────────── */

/* Write data atomically to path. Returns SEMANTIC_OK or error.
 * Never overwrites pre-existing destination. */
static int atomic_write(const char *path, const void *header, uint32_t header_size,
                         const void *payload, uint32_t payload_size,
                         const hacf_digest *identity, char hex_out[65]) {
    /* Extract directory from path */
    const char *dir = ".";
    char *dir_buf = NULL;
    int has_dir = 0;

    const char *last_slash = strrchr(path, '/');
    if (last_slash) {
        size_t dir_len = (size_t)(last_slash - path);
        dir_buf = malloc(dir_len + 1);
        if (!dir_buf) return -2;
        memcpy(dir_buf, path, dir_len);
        dir_buf[dir_len] = '\0';
        dir = dir_buf;
        has_dir = 1;
    }

    /* Check destination does not already exist */
    struct stat st;
    if (stat(path, &st) == 0) {
        if (has_dir) free(dir_buf);
        return -4; /* SEMANTIC_E_DUPLICATE */
    }

    /* Create temp file in same directory */
    char tmp_path[4096];
    int tmp_len = snprintf(tmp_path, sizeof(tmp_path), "%s/.tmp_embedding_XXXXXX", dir);
    if (tmp_len >= (int)sizeof(tmp_path)) {
        if (has_dir) free(dir_buf);
        return -1;
    }

    int fd = mkstemp(tmp_path);
    if (fd < 0) {
        if (has_dir) free(dir_buf);
        return -2;
    }

    /* Write header */
    ssize_t written = write(fd, header, header_size);
    if ((uint32_t)written != header_size) {
        close(fd);
        unlink(tmp_path);
        if (has_dir) free(dir_buf);
        return -9;
    }

    /* Write payload */
    if (payload_size > 0) {
        written = write(fd, payload, payload_size);
        if ((uint32_t)written != payload_size) {
            close(fd);
            unlink(tmp_path);
            if (has_dir) free(dir_buf);
            return -9;
        }
    }

    /* fsync file */
    if (fsync(fd) != 0) {
        close(fd);
        unlink(tmp_path);
        if (has_dir) free(dir_buf);
        return -9;
    }
    close(fd);

    /* Atomic rename — fail if destination exists */
    if (rename(tmp_path, path) != 0) {
        unlink(tmp_path);
        if (has_dir) free(dir_buf);
        return -9;
    }

    /* fsync directory */
    int dir_fd = open(dir, O_RDONLY);
    if (dir_fd >= 0) {
        fsync(dir_fd);
        close(dir_fd);
    }

    if (has_dir) free(dir_buf);

    /* Output hex identity */
    if (hex_out) {
        elpis_hex32(identity->bytes, hex_out);
    }
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Profile write/read                                                     */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_write_profile(const elpis_semantic_embedding_profile_v1 *profile,
                                   const char *path, char hex_out[65]) {
    if (!profile || !path) return -1;

    embedding_file_header hdr;
    memset(&hdr, 0, sizeof(hdr));
    hdr.magic = EMBEDDING_FILE_MAGIC;
    hdr.version = EMBEDDING_FILE_VERSION;
    hdr.file_type = EMBEDDING_FILE_PROFILE;
    hdr.record_size = sizeof(elpis_semantic_embedding_profile_v1);
    memcpy(hdr.identity_digest, profile->profile_identity.bytes, 32);

    return atomic_write(path, &hdr, sizeof(hdr),
                         profile, sizeof(elpis_semantic_embedding_profile_v1),
                         &profile->profile_identity, hex_out);
}

int elpis_embedding_read_profile(const char *path,
                                  elpis_semantic_embedding_profile_v1 *out) {
    if (!path || !out) return -1;

    FILE *f = fopen(path, "rb");
    if (!f) return -9;

    embedding_file_header hdr;
    if (fread(&hdr, 1, sizeof(hdr), f) != sizeof(hdr)) {
        fclose(f);
        return -1;
    }
    if (hdr.magic != EMBEDDING_FILE_MAGIC) { fclose(f); return -1; }
    if (hdr.version != EMBEDDING_FILE_VERSION) { fclose(f); return -1; }
    if (hdr.file_type != EMBEDDING_FILE_PROFILE) { fclose(f); return -1; }
    if (hdr.record_size != sizeof(elpis_semantic_embedding_profile_v1)) { fclose(f); return -1; }

    if (fread(out, 1, sizeof(*out), f) != sizeof(*out)) {
        fclose(f);
        return -1;
    }

    /* Check for trailing bytes */
    uint8_t extra;
    if (fread(&extra, 1, 1, f) > 0) {
        fclose(f);
        return -1; /* trailing unauthorized bytes */
    }
    fclose(f);

    /* Recalculate identity */
    hacf_digest computed;
    elpis_embedding_profile_identity(out, &computed);
    if (memcmp(&computed, &out->profile_identity, sizeof(hacf_digest)) != 0) return -1;
    if (memcmp(hdr.identity_digest, out->profile_identity.bytes, 32) != 0) return -1;

    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Vector write/read                                                      */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_write_vector(const elpis_semantic_embedding_vector_v1 *vec,
                                  const uint8_t *canonical_bytes, uint32_t byte_count,
                                  const char *path, char hex_out[65]) {
    if (!vec || !path || !canonical_bytes) return -1;

    embedding_file_header hdr;
    memset(&hdr, 0, sizeof(hdr));
    hdr.magic = EMBEDDING_FILE_MAGIC;
    hdr.version = EMBEDDING_FILE_VERSION;
    hdr.file_type = EMBEDDING_FILE_VECTOR;
    hdr.record_size = sizeof(elpis_semantic_embedding_vector_v1);
    memcpy(hdr.identity_digest, vec->vector_identity.bytes, 32);

    /* Write header + record + canonical bytes */
    /* We combine record + bytes as payload */
    size_t total_payload = sizeof(elpis_semantic_embedding_vector_v1) + byte_count;
    uint8_t *combined = malloc(total_payload);
    if (!combined) return -2;
    memcpy(combined, vec, sizeof(elpis_semantic_embedding_vector_v1));
    memcpy(combined + sizeof(elpis_semantic_embedding_vector_v1), canonical_bytes, byte_count);

    int rc = atomic_write(path, &hdr, sizeof(hdr),
                           combined, (uint32_t)total_payload,
                           &vec->vector_identity, hex_out);
    free(combined);
    return rc;
}

int elpis_embedding_read_vector(const char *path,
                                 elpis_semantic_embedding_vector_v1 *out,
                                 uint8_t **canonical_bytes_out,
                                 uint32_t *canonical_bytes_len) {
    if (!path || !out) return -1;

    FILE *f = fopen(path, "rb");
    if (!f) return -9;

    embedding_file_header hdr;
    if (fread(&hdr, 1, sizeof(hdr), f) != sizeof(hdr)) { fclose(f); return -1; }
    if (hdr.magic != EMBEDDING_FILE_MAGIC) { fclose(f); return -1; }
    if (hdr.version != EMBEDDING_FILE_VERSION) { fclose(f); return -1; }
    if (hdr.file_type != EMBEDDING_FILE_VECTOR) { fclose(f); return -1; }
    if (hdr.record_size != sizeof(elpis_semantic_embedding_vector_v1)) { fclose(f); return -1; }

    if (fread(out, 1, sizeof(*out), f) != sizeof(*out)) { fclose(f); return -1; }

    /* Read canonical bytes */
    uint32_t byte_count = out->dimensions * sizeof(float);
    uint8_t *bytes = malloc(byte_count);
    if (!bytes) { fclose(f); return -2; }
    if (fread(bytes, 1, byte_count, f) != byte_count) { free(bytes); fclose(f); return -1; }

    /* Check for trailing bytes */
    uint8_t extra;
    if (fread(&extra, 1, 1, f) > 0) { free(bytes); fclose(f); return -1; }
    fclose(f);

    /* Verify bytes digest */
    hacf_digest bytes_digest;
    elpis_embedding_vector_bytes_digest(bytes, byte_count, &bytes_digest);
    if (memcmp(&bytes_digest, &out->vector_bytes_digest, sizeof(hacf_digest)) != 0) {
        free(bytes);
        return -1;
    }

    /* Verify vector identity */
    hacf_digest computed;
    elpis_embedding_vector_identity(out, &computed);
    if (memcmp(&computed, &out->vector_identity, sizeof(hacf_digest)) != 0) {
        free(bytes);
        return -1;
    }
    if (memcmp(hdr.identity_digest, out->vector_identity.bytes, 32) != 0) {
        free(bytes);
        return -1;
    }

    *canonical_bytes_out = bytes;
    *canonical_bytes_len = byte_count;
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Collection write/read                                                  */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_write_collection(const elpis_semantic_embedding_collection_v1 *col,
                                      const char *path, char hex_out[65]) {
    if (!col || !path) return -1;

    embedding_file_header hdr;
    memset(&hdr, 0, sizeof(hdr));
    hdr.magic = EMBEDDING_FILE_MAGIC;
    hdr.version = EMBEDDING_FILE_VERSION;
    hdr.file_type = EMBEDDING_FILE_COLLECTION;
    hdr.record_size = sizeof(elpis_semantic_embedding_collection_v1);
    memcpy(hdr.identity_digest, col->collection_identity.bytes, 32);

    return atomic_write(path, &hdr, sizeof(hdr),
                         col, sizeof(elpis_semantic_embedding_collection_v1),
                         &col->collection_identity, hex_out);
}

int elpis_embedding_read_collection(const char *path,
                                     elpis_semantic_embedding_collection_v1 *out) {
    if (!path || !out) return -1;

    FILE *f = fopen(path, "rb");
    if (!f) return -9;

    embedding_file_header hdr;
    if (fread(&hdr, 1, sizeof(hdr), f) != sizeof(hdr)) { fclose(f); return -1; }
    if (hdr.magic != EMBEDDING_FILE_MAGIC) { fclose(f); return -1; }
    if (hdr.version != EMBEDDING_FILE_VERSION) { fclose(f); return -1; }
    if (hdr.file_type != EMBEDDING_FILE_COLLECTION) { fclose(f); return -1; }
    if (hdr.record_size != sizeof(elpis_semantic_embedding_collection_v1)) { fclose(f); return -1; }

    if (fread(out, 1, sizeof(*out), f) != sizeof(*out)) { fclose(f); return -1; }

    uint8_t extra;
    if (fread(&extra, 1, 1, f) > 0) { fclose(f); return -1; }
    fclose(f);

    /* Recalculate identity */
    hacf_digest computed;
    elpis_embedding_collection_finalize(out, &computed);
    if (memcmp(&computed, &out->collection_identity, sizeof(hacf_digest)) != 0) return -1;
    if (memcmp(hdr.identity_digest, out->collection_identity.bytes, 32) != 0) return -1;

    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* File package digest                                                    */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_file_package_digest(const char *path, hacf_digest *out) {
    FILE *f = fopen(path, "rb");
    if (!f) return -9;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    uint8_t buf[4096];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), f)) > 0) {
        elpis_sha256_update(&ctx, buf, n);
    }
    fclose(f);
    elpis_sha256_final(&ctx, out->bytes);
    return 0;
}
