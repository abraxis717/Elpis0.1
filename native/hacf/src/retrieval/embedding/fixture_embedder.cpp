/* fixture_embedder.cpp - deterministic embedding providers.
 *
 * Fixture construction (v2), chosen so the emitted float32 bytes are identical
 * on every host without depending on libm, extended precision, or reduction
 * order:
 *
 *   seed    = SHA256("elpis-fixture-embed-v2\0" || input)
 *   stream  = SHA256(seed || u32le(block)) for block = 0, 1, 2, ...
 *   consume 3 bytes at a time: position = (b0 | b1<<8) mod 384, sign = b2 & 1
 *   keep the first 16 DISTINCT positions in stream order
 *   selected components = +0.25f or -0.25f exactly, all others = +0.0f
 *
 * Every component is a power of two exactly representable in binary32, so the
 * values survive storage and reload bit-for-bit. The L2 norm is exact by
 * construction and needs no square root:
 *
 *   16 * 0.25^2 = 16 * 0.0625 = 1.0
 *
 * The unnormalized profile uses +/-1.0f instead, giving an exact norm of 4.0,
 * so the two normalization policies are observably different and both exact.
 *
 * The modulo on a 16-bit draw is very slightly biased across 384 positions.
 * That is deliberate and harmless: the fixture is a qualification instrument,
 * not a semantic embedding, and bias does not affect determinism.
 *
 * The values are not semantically meaningful. They exist to qualify storage,
 * scoring, ranking, corruption handling, FMS integration and cross-host
 * reproducibility. */

#include "embedder_internal.h"

#include "elpis/sha256.h"

#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <new>

namespace {

const char kFixtureSeedTag[] = "elpis-fixture-embed-v2";
const uint32_t kFixtureNonzero = 16u;
const char kZeroHex[65] = "0000000000000000000000000000000000000000000000000000000000000000";


void put_u32le(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v & 0xffu);
    p[1] = (uint8_t)((v >> 8) & 0xffu);
    p[2] = (uint8_t)((v >> 16) & 0xffu);
    p[3] = (uint8_t)((v >> 24) & 0xffu);
}
} // namespace

void elpis_embedder_set_error(elpis_embedder *e, const char *message) {
    if (!e) return;
    std::snprintf(e->error, sizeof e->error, "%s", message ? message : "unknown error");
}

/* strnlen is POSIX, not standard C++; -std=c++17 without extensions may not
 * declare it. Fixed-width profile fields must never be read past their end. */
size_t elpis_embedder_bounded_len(const char *s, size_t cap) {
    size_t n = 0;
    while (n < cap && s[n]) n++;
    return n;
}

/* Bounded validation of a fixed-width 65-byte ABI digest field.
 *
 * The field is part of a struct the caller may have heap-allocated to exactly
 * sizeof(elpis_embedding_profile). An unterminated field must therefore never
 * cause a read past byte 64: this function inspects bytes [0,64] only, never
 * byte 65 or later, and never calls strlen. Canonical form is exactly 64
 * lowercase hexadecimal characters followed by NUL. */
int elpis_embedder_valid_hex64(const char field[65]) {
    if (!field) return 0;
    for (int i = 0; i < 64; i++) {
        char c = field[i];
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return 0;   /* lowercase only */
    }
    return field[64] == '\0';
}

/* Bounded text field: printable, NUL-terminated within cap, non-empty. */
int elpis_embedder_valid_text(const char *field, size_t cap, int allow_empty) {
    if (!field) return 0;
    size_t n = elpis_embedder_bounded_len(field, cap);
    if (n == cap) return 0;                       /* no terminator inside the field */
    if (!allow_empty && n == 0) return 0;
    for (size_t i = 0; i < n; i++) {
        unsigned char ch = (unsigned char)field[i];
        if (ch < 0x20 || ch == 0x7f) return 0;
    }
    return 1;
}

extern "C" {

/* ---- shared vector helpers ------------------------------------------------ */

int elpis_vector_all_finite(const float *v, uint32_t dim) {
    if (!v) return 0;
    for (uint32_t i = 0; i < dim; i++) {
        float x = v[i];
        if (std::isnan(x) || std::isinf(x)) return 0;
    }
    return 1;
}

double elpis_vector_l2_norm(const float *v, uint32_t dim) {
    double acc = 0.0;                       /* double accumulation, see docs/R2_VECTOR_ARCHITECTURE.md */
    for (uint32_t i = 0; i < dim; i++) acc += (double)v[i] * (double)v[i];
    return std::sqrt(acc);
}

int elpis_vector_l2_normalize(float *v, uint32_t dim) {
    double n = elpis_vector_l2_norm(v, dim);
    if (!(n > 0.0) || std::isnan(n) || std::isinf(n)) return -1;
    for (uint32_t i = 0; i < dim; i++) v[i] = (float)((double)v[i] / n);
    return 0;
}

/* ---- profile --------------------------------------------------------------- */

int elpis_embedding_profile_validate(const elpis_embedding_profile *p) {
    if (!p) return -1;
    if (p->abi_version != ELPIS_EMBEDDING_ABI_VERSION) return -1;
    if (p->dimensions != ELPIS_EMBEDDING_DIM) return -1;
    if (p->element_type != ELPIS_ELEM_F32) return -1;
    if (p->normalization != ELPIS_NORM_NONE && p->normalization != ELPIS_NORM_L2) return -1;
    if (p->metric != ELPIS_METRIC_DOT && p->metric != ELPIS_METRIC_COSINE) return -1;
    if (p->max_input_bytes == 0 || p->batch_limit == 0) return -1;
    if (p->reserved != 0) return -1;                    /* reserved must be zero */
    /* All character fields are fixed-width ABI arrays: bounded checks only.
     * No strlen, no read past the declared width, no read past byte 64 of a
     * digest field. */
    if (!elpis_embedder_valid_text(p->name, sizeof p->name, 0)) return -1;
    if (!elpis_embedder_valid_text(p->backend, sizeof p->backend, 0)) return -1;
    if (!elpis_embedder_valid_text(p->device, sizeof p->device, 1)) return -1;
    if (!elpis_embedder_valid_hex64(p->model_digest)) return -1;
    if (!elpis_embedder_valid_hex64(p->tokenizer_digest)) return -1;
    return 0;
}

int elpis_embedding_profile_digest(const elpis_embedding_profile *p, char out[65]) {
    if (!p || !out) return -1;
    if (elpis_embedding_profile_validate(p) != 0) return -1;

    /* Fixed field order, explicit little-endian integers, fixed-width text
     * fields zero-padded: no struct padding ever reaches the digest. */
    uint8_t buf[8 * 4 + 64 + 32 + 64 + 64 + 64];
    std::memset(buf, 0, sizeof buf);
    size_t o = 0;
    const uint32_t ints[8] = {p->abi_version, p->dimensions, p->element_type, p->normalization,
                              p->metric, p->max_input_bytes, p->batch_limit, 0u};
    for (uint32_t v : ints) { put_u32le(buf + o, v); o += 4; }
    std::memcpy(buf + o, p->name, elpis_embedder_bounded_len(p->name, sizeof p->name));          o += 64;
    std::memcpy(buf + o, p->backend, elpis_embedder_bounded_len(p->backend, sizeof p->backend)); o += 32;
    std::memcpy(buf + o, p->device, elpis_embedder_bounded_len(p->device, sizeof p->device));    o += 64;
    std::memcpy(buf + o, p->model_digest, 64);                                      o += 64;
    std::memcpy(buf + o, p->tokenizer_digest, 64);                                  o += 64;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, "elpis-embedding-profile-v1", 26);
    elpis_sha256_update(&ctx, buf, o);
    uint8_t d[32];
    elpis_sha256_final(&ctx, d);
    elpis_hex32(d, out);
    return 0;
}

int elpis_embedding_profile_equal(const elpis_embedding_profile *a,
                                  const elpis_embedding_profile *b) {
    char da[65], db[65];
    if (elpis_embedding_profile_digest(a, da) != 0) return 0;
    if (elpis_embedding_profile_digest(b, db) != 0) return 0;
    return std::strcmp(da, db) == 0;
}

/* ---- providers -------------------------------------------------------------- */

int elpis_embedder_fixture_create(uint32_t normalization, elpis_embedder **out) {
    if (!out) return -1;
    if (normalization != ELPIS_NORM_NONE && normalization != ELPIS_NORM_L2) return -1;
    auto *e = new (std::nothrow) elpis_embedder();
    if (!e) return -1;
    e->kind = ELPIS_EMBEDDER_KIND_FIXTURE;
    e->profile.abi_version = ELPIS_EMBEDDING_ABI_VERSION;
    e->profile.dimensions = ELPIS_EMBEDDING_DIM;
    e->profile.element_type = ELPIS_ELEM_F32;
    e->profile.normalization = normalization;
    e->profile.metric = (normalization == ELPIS_NORM_L2) ? ELPIS_METRIC_COSINE : ELPIS_METRIC_DOT;
    e->profile.max_input_bytes = 1u << 20;
    e->profile.batch_limit = 1024;
    std::snprintf(e->profile.name, sizeof e->profile.name, "fixture-sha256-v2");
    std::snprintf(e->profile.backend, sizeof e->profile.backend, "cpu-fixture");
    std::snprintf(e->profile.device, sizeof e->profile.device, "cpu");
    std::snprintf(e->profile.model_digest, sizeof e->profile.model_digest, "%s", kZeroHex);
    std::snprintf(e->profile.tokenizer_digest, sizeof e->profile.tokenizer_digest, "%s", kZeroHex);
    if (elpis_embedding_profile_digest(&e->profile, e->profile_digest) != 0) { delete e; return -1; }
    *out = e;
    return 0;
}

void elpis_embedder_destroy(elpis_embedder *e) { delete e; }

int elpis_embedder_profile(const elpis_embedder *e, elpis_embedding_profile *out) {
    if (!e || !out) return -1;
    *out = e->profile;
    return 0;
}

const char *elpis_embedder_error(const elpis_embedder *e) {
    return e ? e->error : "null embedder";
}

int elpis_embedder_embed(elpis_embedder *e, const void *bytes, size_t len,
                         float *out, uint32_t out_dim) {
    if (!e || !out) return -1;
    if (e->kind != ELPIS_EMBEDDER_KIND_FIXTURE) { elpis_embedder_set_error(e, "external provider cannot synthesise vectors"); return -1; }
    if (out_dim != e->profile.dimensions) { elpis_embedder_set_error(e, "dimension mismatch"); return -1; }
    if (!bytes && len) { elpis_embedder_set_error(e, "null input"); return -1; }
    if (len > e->profile.max_input_bytes) { elpis_embedder_set_error(e, "input exceeds max_input_bytes"); return -1; }

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, kFixtureSeedTag, sizeof kFixtureSeedTag);   /* includes the NUL */
    if (len) elpis_sha256_update(&ctx, bytes, len);
    uint8_t seed[32];
    elpis_sha256_final(&ctx, seed);

    for (uint32_t i = 0; i < out_dim; i++) out[i] = 0.0f;

    /* Exactly representable magnitudes: 0.25 gives an exact unit norm over 16
     * components, 1.0 gives an exact norm of 4. No division, no sqrt. */
    const float magnitude = (e->profile.normalization == ELPIS_NORM_L2) ? 0.25f : 1.0f;

    uint32_t chosen = 0, block = 0;
    while (chosen < kFixtureNonzero) {
        uint8_t counter[4];
        put_u32le(counter, block++);
        elpis_sha256_ctx bc;
        elpis_sha256_init(&bc);
        elpis_sha256_update(&bc, seed, sizeof seed);
        elpis_sha256_update(&bc, counter, sizeof counter);
        uint8_t blk[32];
        elpis_sha256_final(&bc, blk);

        for (uint32_t o = 0; o + 3 <= 32 && chosen < kFixtureNonzero; o += 3) {
            uint32_t pos = ((uint32_t)blk[o] | ((uint32_t)blk[o + 1] << 8)) % out_dim;
            if (out[pos] != 0.0f) continue;                   /* first 16 distinct positions */
            out[pos] = (blk[o + 2] & 1u) ? magnitude : -magnitude;
            chosen++;
        }
        if (block > 4096u) { elpis_embedder_set_error(e, "fixture position selection failed to converge"); return -1; }
    }

    /* The norm is exact by construction; assert it instead of computing one. */
    {
        double sq = 0.0;
        uint32_t nz = 0;
        for (uint32_t i = 0; i < out_dim; i++)
            if (out[i] != 0.0f) { nz++; sq += (double)out[i] * (double)out[i]; }
        const double want = (e->profile.normalization == ELPIS_NORM_L2) ? 1.0 : 16.0;
        if (nz != kFixtureNonzero || sq != want) {
            elpis_embedder_set_error(e, "fixture vector failed its exactness invariant");
            return -1;
        }
    }
    if (!elpis_vector_all_finite(out, out_dim)) { elpis_embedder_set_error(e, "non-finite fixture vector"); return -1; }
    return 0;
}

} // extern "C"
