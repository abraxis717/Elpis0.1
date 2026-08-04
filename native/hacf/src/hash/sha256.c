#include "elpis/sha256.h"

#include <string.h>

static uint32_t rotr32(uint32_t x, unsigned n) { return (x >> n) | (x << (32u - n)); }
static uint32_t load_be32(const uint8_t p[4]) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}
static void store_be32(uint8_t p[4], uint32_t x) {
    p[0] = (uint8_t)(x >> 24); p[1] = (uint8_t)(x >> 16);
    p[2] = (uint8_t)(x >> 8);  p[3] = (uint8_t)x;
}
static void store_be64(uint8_t p[8], uint64_t x) {
    for (int i = 7; i >= 0; --i) { p[i] = (uint8_t)x; x >>= 8; }
}

static const uint32_t K[64] = {
    0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
    0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
    0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
    0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
    0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
    0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
    0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
    0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u
};

static void compress(elpis_sha256_ctx *ctx, const uint8_t block[64]) {
    uint32_t w[64];
    for (int i = 0; i < 16; ++i) w[i] = load_be32(block + 4 * i);
    for (int i = 16; i < 64; ++i) {
        uint32_t s0 = rotr32(w[i-15],7) ^ rotr32(w[i-15],18) ^ (w[i-15] >> 3);
        uint32_t s1 = rotr32(w[i-2],17) ^ rotr32(w[i-2],19) ^ (w[i-2] >> 10);
        w[i] = w[i-16] + s0 + w[i-7] + s1;
    }
    uint32_t a=ctx->state[0], b=ctx->state[1], c=ctx->state[2], d=ctx->state[3];
    uint32_t e=ctx->state[4], f=ctx->state[5], g=ctx->state[6], h=ctx->state[7];
    for (int i = 0; i < 64; ++i) {
        uint32_t S1 = rotr32(e,6) ^ rotr32(e,11) ^ rotr32(e,25);
        uint32_t ch = (e & f) ^ ((~e) & g);
        uint32_t t1 = h + S1 + ch + K[i] + w[i];
        uint32_t S0 = rotr32(a,2) ^ rotr32(a,13) ^ rotr32(a,22);
        uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        uint32_t t2 = S0 + maj;
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    ctx->state[0]+=a; ctx->state[1]+=b; ctx->state[2]+=c; ctx->state[3]+=d;
    ctx->state[4]+=e; ctx->state[5]+=f; ctx->state[6]+=g; ctx->state[7]+=h;
}

void elpis_sha256_init(elpis_sha256_ctx *ctx) {
    if (!ctx) return;
    static const uint32_t init[8] = {
        0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,
        0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u
    };
    memcpy(ctx->state, init, sizeof init);
    ctx->total_bytes = 0;
    ctx->block_used = 0;
    memset(ctx->block, 0, sizeof ctx->block);
}

void elpis_sha256_update(elpis_sha256_ctx *ctx, const void *data, size_t len) {
    if (!ctx || (!data && len)) return;
    const uint8_t *p = (const uint8_t *)data;
    ctx->total_bytes += (uint64_t)len;
    while (len) {
        size_t room = 64u - ctx->block_used;
        size_t take = len < room ? len : room;
        memcpy(ctx->block + ctx->block_used, p, take);
        ctx->block_used += take; p += take; len -= take;
        if (ctx->block_used == 64u) { compress(ctx, ctx->block); ctx->block_used = 0; }
    }
}

void elpis_sha256_final(elpis_sha256_ctx *ctx, uint8_t out[32]) {
    if (!ctx || !out) return;
    uint64_t bit_len = ctx->total_bytes * 8u;
    ctx->block[ctx->block_used++] = 0x80u;
    if (ctx->block_used > 56u) {
        memset(ctx->block + ctx->block_used, 0, 64u - ctx->block_used);
        compress(ctx, ctx->block);
        ctx->block_used = 0;
    }
    memset(ctx->block + ctx->block_used, 0, 56u - ctx->block_used);
    store_be64(ctx->block + 56, bit_len);
    compress(ctx, ctx->block);
    for (int i = 0; i < 8; ++i) store_be32(out + 4*i, ctx->state[i]);
    memset(ctx, 0, sizeof *ctx);
}

void elpis_sha256(const void *data, size_t len, uint8_t out[32]) {
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, data, len);
    elpis_sha256_final(&ctx, out);
}

void elpis_hex32(const uint8_t digest[32], char out[65]) {
    static const char h[] = "0123456789abcdef";
    if (!digest || !out) return;
    for (int i = 0; i < 32; ++i) { out[2*i] = h[digest[i] >> 4]; out[2*i+1] = h[digest[i] & 15]; }
    out[64] = '\0';
}

static int hexv(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int elpis_unhex32(const char hex[64], uint8_t out[32]) {
    if (!hex || !out) return -1;
    for (int i = 0; i < 32; ++i) {
        int a = hexv(hex[2*i]), b = hexv(hex[2*i+1]);
        if (a < 0 || b < 0) return -1;
        out[i] = (uint8_t)((a << 4) | b);
    }
    return 0;
}

int elpis_digest_equal(const uint8_t a[32], const uint8_t b[32]) {
    if (!a || !b) return 0;
    uint8_t x = 0;
    for (int i = 0; i < 32; ++i) x |= (uint8_t)(a[i] ^ b[i]);
    return x == 0;
}
