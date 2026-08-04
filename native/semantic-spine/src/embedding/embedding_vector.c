/* embedding_vector.c — Canonical embedding vector object.
 *
 * Canonical float32 encoding:
 *   - IEEE-754 binary32, little-endian byte order
 *   - Negative zero → positive zero
 *   - NaN, ±infinity rejected
 */
#include "elpis_semantic/embedding_vector.h"
#include "elpis/sha256.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <arpa/inet.h>
#include <float.h>
#include <stdint.h>

/* ──────────────────────────────────────────────────────────────────── */
/* Helper: write domain tag, u32 BE, digest                              */
/* ──────────────────────────────────────────────────────────────────── */

static void write_domain_tag(elpis_sha256_ctx *ctx, const char *domain) {
    size_t len = strlen(domain);
    uint32_t be_len = htonl((uint32_t)len);
    elpis_sha256_update(ctx, &be_len, 4);
    elpis_sha256_update(ctx, domain, len);
}

static void write_u32_be(elpis_sha256_ctx *ctx, uint32_t val) {
    uint32_t be = htonl(val);
    elpis_sha256_update(ctx, &be, 4);
}

static void write_digest(elpis_sha256_ctx *ctx, const hacf_digest *d) {
    elpis_sha256_update(ctx, d->bytes, HACF_DIGEST_BYTES);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Canonical float32 conversion                                          */
/* ──────────────────────────────────────────────────────────────────── */

/* Canonicalize a single float32 value to little-endian IEEE-754 bytes.
 * Returns 0 on success, -1 if the value is NaN or infinity. */
static int canonicalize_float32(float val, uint8_t out[4]) {
    /* Reject NaN */
    if (val != val) return -1;
    /* Reject infinities */
    if (val > FLT_MAX || val < -FLT_MAX) return -1;

    /* Canonicalize negative zero to positive zero */
    if (val == 0.0f) {
        val = 0.0f; /* force +0 */
    }

    /* Copy to bytes — we assume little-endian host or use explicit conversion */
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    memcpy(out, &val, 4);
#else
    /* Big-endian host: reverse bytes for little-endian output */
    uint32_t bits;
    memcpy(&bits, &val, 4);
    bits = __builtin_bswap32(bits);
    memcpy(out, &bits, 4);
#endif
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Vector identity                                                       */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_vector_identity(const elpis_semantic_embedding_vector_v1 *vec,
                                     hacf_digest *out) {
    if (!vec || !out) return -1;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.embedding_vector.v1");
    write_u32_be(&ctx, vec->abi_version);
    write_digest(&ctx, &vec->profile_digest);
    write_u32_be(&ctx, vec->dimensions);
    write_u32_be(&ctx, (uint32_t)vec->vector_dtype);
    write_digest(&ctx, &vec->vector_bytes_digest);
    write_u32_be(&ctx, vec->vector_flags);
    elpis_sha256_final(&ctx, out->bytes);
    return 0;
}

int elpis_embedding_vector_bytes_digest(const uint8_t *bytes, uint32_t byte_count,
                                         hacf_digest *out) {
    if (!bytes || !out || byte_count == 0) return -1;
    elpis_sha256(bytes, byte_count, out->bytes);
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Vector creation from float32                                          */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_vector_from_float32(
    const elpis_semantic_embedding_profile_v1 *profile,
    const float *data, uint32_t dimensions,
    elpis_semantic_embedding_vector_v1 *out,
    uint8_t **canonical_bytes_out, uint32_t *canonical_bytes_len) {
    if (!profile || !data || !out || !canonical_bytes_out || !canonical_bytes_len) return -1;
    if (dimensions == 0) return -1;
    if (dimensions != profile->dimensions) return -1;

    *canonical_bytes_out = NULL;
    *canonical_bytes_len = 0;

    uint32_t byte_count = dimensions * sizeof(float);
    uint8_t *canonical = malloc(byte_count);
    if (!canonical) return -2;

    /* Canonicalize each float */
    for (uint32_t i = 0; i < dimensions; i++) {
        if (canonicalize_float32(data[i], canonical + i * 4) != 0) {
            free(canonical);
            return -3; /* NaN or infinity */
        }
    }

    /* Validate normalization if profile requires it */
    if (profile->normalization_policy == EMBEDDING_NORMALIZATION_UNIT_L2) {
        double norm = elpis_embedding_vector_l2_norm(canonical, dimensions);
        if (norm < (1.0 - EMBEDDING_NORMALIZATION_TOLERANCE) ||
            norm > (1.0 + EMBEDDING_NORMALIZATION_TOLERANCE)) {
            free(canonical);
            return -4; /* normalization failure */
        }
    }

    /* Compute bytes digest */
    hacf_digest bytes_digest;
    elpis_embedding_vector_bytes_digest(canonical, byte_count, &bytes_digest);

    /* Fill output record */
    memset(out, 0, sizeof(*out));
    out->abi_version = EMBEDDING_VECTOR_ABI_VERSION;
    memcpy(&out->profile_digest, &profile->profile_identity, sizeof(hacf_digest));
    out->dimensions = dimensions;
    out->vector_dtype = profile->vector_dtype;
    memcpy(&out->vector_bytes_digest, &bytes_digest, sizeof(hacf_digest));
    out->vector_flags = EMBEDDING_VECTOR_FLAG_NONE;

    /* Compute vector identity */
    elpis_embedding_vector_identity(out, &out->vector_identity);

    /* Return canonical bytes to caller */
    *canonical_bytes_out = canonical;
    *canonical_bytes_len = byte_count;
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Validation                                                              */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_vector_validate(const elpis_semantic_embedding_vector_v1 *vec) {
    if (!vec) return -1;
    if (vec->abi_version != EMBEDDING_VECTOR_ABI_VERSION) return -1;
    if (vec->dimensions == 0) return -1;
    if (vec->vector_dtype != EMBEDDING_DTYPE_FLOAT32) return -1;
    /* Profile digest must be non-zero */
    static const uint8_t zero_buf[64] = {0};
    if (memcmp(&vec->profile_digest, zero_buf, sizeof(hacf_digest)) == 0) return -1;
    /* Vector bytes digest must be non-zero */
    if (memcmp(&vec->vector_bytes_digest, zero_buf, sizeof(hacf_digest)) == 0) return -1;
    if (vec->vector_flags & ~EMBEDDING_VECTOR_FLAG_MASK) return -1;
    if (memcmp(vec->reserved, zero_buf, sizeof(vec->reserved)) != 0) return -1;
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* L2 norm                                                                 */
/* ──────────────────────────────────────────────────────────────────── */

double elpis_embedding_vector_l2_norm(const uint8_t *bytes, uint32_t dimensions) {
    double sum = 0.0;
    for (uint32_t i = 0; i < dimensions; i++) {
        float val;
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
        memcpy(&val, bytes + i * 4, 4);
#else
        uint32_t bits;
        memcpy(&bits, bytes + i * 4, 4);
        bits = __builtin_bswap32(bits);
        memcpy(&val, &bits, 4);
#endif
        sum += (double)val * (double)val;
    }
    return sqrt(sum);
}

int elpis_embedding_vector_validate_normalization(
    const elpis_semantic_embedding_profile_v1 *profile,
    const uint8_t *bytes, uint32_t dimensions) {
    if (profile->normalization_policy != EMBEDDING_NORMALIZATION_UNIT_L2) return 0;
    double norm = elpis_embedding_vector_l2_norm(bytes, dimensions);
    if (norm < (1.0 - EMBEDDING_NORMALIZATION_TOLERANCE) ||
        norm > (1.0 + EMBEDDING_NORMALIZATION_TOLERANCE)) {
        return -4;
    }
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Comparison                                                              */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_vector_cmp(const elpis_semantic_embedding_vector_v1 *a,
                                const elpis_semantic_embedding_vector_v1 *b) {
    if (!a || !b) return -1;
    return memcmp(a->vector_identity.bytes, b->vector_identity.bytes, HACF_DIGEST_BYTES);
}

int elpis_embedding_vector_is_same(const elpis_semantic_embedding_vector_v1 *a,
                                    const elpis_semantic_embedding_vector_v1 *b) {
    if (!a || !b) return 0;
    return memcmp(a->vector_identity.bytes, b->vector_identity.bytes, HACF_DIGEST_BYTES) == 0;
}

void elpis_embedding_vector_free_bytes(uint8_t *bytes) {
    free(bytes);
}
