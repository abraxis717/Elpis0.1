/* trm_persist.c — TRM adapter persistence utilities v1. */

#define _GNU_SOURCE
#include "elpis_semantic/trm_persist.h"
#include "elpis/cascade.h"
#include <openssl/sha.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>

static int write_all(int fd, const uint8_t *buf, uint32_t len) {
    uint32_t offset = 0;
    while (offset < len) {
        ssize_t n = write(fd, buf + offset, (size_t)(len - offset));
        if (n < 0) return -1;
        offset += (uint32_t)n;
    }
    return 0;
}

static int read_all(int fd, uint8_t *buf, uint32_t len) {
    uint32_t offset = 0;
    while (offset < len) {
        ssize_t n = read(fd, buf + offset, (size_t)(len - offset));
        if (n < 0) return -1;
        if (n == 0) return -1;
        offset += (uint32_t)n;
    }
    return 0;
}

static int fsync_file_and_dir(const char *path) {
    /* Get directory */
    char dir[4096];
    strncpy(dir, path, sizeof(dir) - 1);
    dir[sizeof(dir) - 1] = '\0';
    char *last_slash = strrchr(dir, '/');
    if (last_slash) *last_slash = '\0';
    else strcpy(dir, ".");

    int dfd = open(dir, O_RDONLY | O_DIRECTORY);
    if (dfd < 0) return -1;
    int ret = fsync(dfd);
    close(dfd);
    return ret;
}

int elpis_trm_digest_bytes(const uint8_t *data, size_t len, hacf_digest *out) {
    if (!data || !out || len == 0) return -1;
    SHA256(data, len, out->bytes);
    return 0;
}

int elpis_trm_digest_domain(const char *domain, uint32_t abi_version,
    const uint8_t *payload, size_t payload_len, hacf_digest *out) {
    if (!domain || !out) return -1;

    /* Domain tag = SHA256(domain_string) */
    hacf_digest domain_tag;
    size_t domain_len = strlen(domain);
    SHA256((const uint8_t *)domain, domain_len, domain_tag.bytes);

    /* Identity = SHA256(domain_tag || abi_version(4 BE) || payload) */
    SHA256_CTX ctx;
    SHA256_Init(&ctx);
    SHA256_Update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);

    uint8_t ver_be[4];
    ver_be[0] = (uint8_t)((abi_version >> 24) & 0xFF);
    ver_be[1] = (uint8_t)((abi_version >> 16) & 0xFF);
    ver_be[2] = (uint8_t)((abi_version >> 8) & 0xFF);
    ver_be[3] = (uint8_t)(abi_version & 0xFF);
    SHA256_Update(&ctx, ver_be, 4);

    if (payload && payload_len > 0) {
        SHA256_Update(&ctx, payload, payload_len);
    }
    SHA256_Final(out->bytes, &ctx);
    return 0;
}

int elpis_trm_write_binary(const char *path, const uint8_t *data, uint32_t data_len) {
    if (!path || (!data && data_len > 0)) return -1;

    /* 4-byte BE length header */
    uint8_t header[4];
    header[0] = (uint8_t)((data_len >> 24) & 0xFF);
    header[1] = (uint8_t)((data_len >> 16) & 0xFF);
    header[2] = (uint8_t)((data_len >> 8) & 0xFF);
    header[3] = (uint8_t)(data_len & 0xFF);

    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return -1;

    if (write_all(fd, header, 4) < 0) { close(fd); return -1; }
    if (data_len > 0 && write_all(fd, data, data_len) < 0) { close(fd); return -1; }

    fsync(fd);
    close(fd);
    fsync_file_and_dir(path);
    return 0;
}

int elpis_trm_read_binary(const char *path, uint8_t *data, uint32_t expected_len, uint32_t *actual_len) {
    if (!path || (!data && expected_len > 0) || !actual_len) return -1;

    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;

    uint8_t header[4];
    if (read_all(fd, header, 4) < 0) { close(fd); return -1; }

    uint32_t file_len = (uint32_t)header[0] << 24 |
                        (uint32_t)header[1] << 16 |
                        (uint32_t)header[2] << 8 |
                        (uint32_t)header[3];

    *actual_len = file_len;

    if (file_len != expected_len) { close(fd); return -1; }

    if (file_len > 0 && read_all(fd, data, file_len) < 0) { close(fd); return -1; }

    close(fd);
    return 0;
}
