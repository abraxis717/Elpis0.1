#ifndef ELPIS_SHA256_H
#define ELPIS_SHA256_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct elpis_sha256_ctx {
    uint32_t state[8];
    uint64_t total_bytes;
    uint8_t  block[64];
    size_t   block_used;
} elpis_sha256_ctx;

void elpis_sha256_init(elpis_sha256_ctx *ctx);
void elpis_sha256_update(elpis_sha256_ctx *ctx, const void *data, size_t len);
void elpis_sha256_final(elpis_sha256_ctx *ctx, uint8_t out[32]);
void elpis_sha256(const void *data, size_t len, uint8_t out[32]);
void elpis_hex32(const uint8_t digest[32], char out[65]);
int  elpis_unhex32(const char hex[64], uint8_t out[32]);
int  elpis_digest_equal(const uint8_t a[32], const uint8_t b[32]);

#ifdef __cplusplus
}
#endif

#endif
