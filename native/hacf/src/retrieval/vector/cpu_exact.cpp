/* cpu_exact.cpp - exact exhaustive CPU scoring, the R2 correctness oracle.
 *
 * Numerical policy, fixed and load-bearing:
 *   - stored vectors are float32
 *   - every accumulation is double
 *   - each product is computed as (double)a * (double)b, never float*float
 *   - no fused multiply-add is requested and no reassociation is permitted
 *     (-ffast-math and friends would change results and are not used)
 *   - the dimension loop runs in index order, so the summation order is fixed
 *
 * Two hosts with IEEE-754 doubles therefore produce bit-identical scores from
 * bit-identical inputs, which is what cross-host result-digest parity needs. */

#include "elpis/vector_index.h"
#include "elpis/vector_result.h"
#include "elpis/sha256.h"

#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>

namespace {

uint32_t get_u32le(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

float load_f32le(const uint8_t *p) {
    uint32_t bits = get_u32le(p);
    float f;
    std::memcpy(&f, &bits, 4);
    return f;
}

} // namespace

extern "C" {

int elpis_vector_score_block(const uint8_t *records, uint64_t count, uint32_t dimensions,
                             const float *query, uint32_t metric, double *scores_out) {
    if (!records || !query || !scores_out) return -1;
    if (dimensions != ELPIS_EMBEDDING_DIM) return -1;
    if (metric != ELPIS_METRIC_DOT && metric != ELPIS_METRIC_COSINE) return -1;

    double qnorm = 1.0;
    if (metric == ELPIS_METRIC_COSINE) {
        double acc = 0.0;
        for (uint32_t d = 0; d < dimensions; d++) acc += (double)query[d] * (double)query[d];
        qnorm = std::sqrt(acc);
        if (!(qnorm > 0.0)) return -1;                 /* zero-norm query under cosine */
    }

    for (uint64_t i = 0; i < count; i++) {
        const uint8_t *vec = records + i * (uint64_t)ELPIS_VSHARD_RECORD_BYTES + 64;
        double dot = 0.0, vsq = 0.0;
        for (uint32_t d = 0; d < dimensions; d++) {
            double v = (double)load_f32le(vec + d * 4u);
            double q = (double)query[d];
            dot += v * q;
            vsq += v * v;
        }
        if (metric == ELPIS_METRIC_COSINE) {
            double vn = std::sqrt(vsq);
            /* A stored zero vector cannot have a cosine. It scores -inf-free:
             * it is excluded by reporting the lowest possible finite score. */
            scores_out[i] = (vn > 0.0) ? (dot / (vn * qnorm)) : -2.0;
        } else {
            scores_out[i] = dot;
        }
    }
    return 0;
}

/* ---- deterministic ordering ------------------------------------------------ */

int64_t elpis_vector_score_key(double score) {
    /* This key is defined only for the normalized indexed score domain. Public
     * callers are contained too: non-finite values map to the lowest key and
     * finite overshoot is clamped to [-1,1]. Indexed search rejects overshoot
     * beyond its declared numerical envelope before calling this function. */
    if (!std::isfinite(score)) return std::numeric_limits<int64_t>::min();
    if (score > 1.0) score = 1.0;
    if (score < -1.0) score = -1.0;
    double x = score * (double)ELPIS_VEC_SCORE_SCALE;
    if (x >= 0.0) {
        double r = std::floor(x + 0.5);
        return (int64_t)r;
    }
    double r = std::ceil(x - 0.5);
    return (int64_t)r;
}

const char *elpis_vec_strerror(int status) {
    switch (status) {
    case ELPIS_VEC_OK:          return "ok";
    case ELPIS_VEC_E_INVAL:     return "invalid argument";
    case ELPIS_VEC_E_QUERY:     return "query vector rejected";
    case ELPIS_VEC_E_PROFILE:   return "embedding profile or corpus binding mismatch";
    case ELPIS_VEC_E_FORMAT:    return "shard format rejected";
    case ELPIS_VEC_E_INTEGRITY: return "integrity failure";
    case ELPIS_VEC_E_RESIDENCY: return "shard could not be made WARM-resident";
    case ELPIS_VEC_E_DUPLICATE: return "duplicate chunk digest or shard";
    case ELPIS_VEC_E_NOTFOUND:  return "no such shard";
    case ELPIS_VEC_E_LIMIT:     return "index capacity reached";
    case ELPIS_VEC_E_INTERNAL:  return "internal error";
    default:                    return "unknown vector status";
    }
}

int elpis_vector_hit_compare(const elpis_vector_hit *a, const elpis_vector_hit *b) {
    if (!a || !b) return 0;
    /* Higher canonical key first. The host double is never consulted. */
    if (a->score_key > b->score_key) return -1;
    if (a->score_key < b->score_key) return 1;
    /* Then lexicographically smaller chunk digest. Digests are unique across an
     * index, so the order is total: no pointer, timestamp, hash-table order,
     * locale or sort-stability dependence remains. */
    return std::strcmp(a->chunk_digest, b->chunk_digest);
}

int elpis_vector_result_digest(const elpis_vector_hit *hits, uint32_t n, char out[65]) {
    if (!out || (!hits && n)) return -1;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, "elpis-vector-result-v1", 22);
    uint8_t nb[4] = {(uint8_t)(n & 0xffu), (uint8_t)((n >> 8) & 0xffu),
                     (uint8_t)((n >> 16) & 0xffu), (uint8_t)((n >> 24) & 0xffu)};
    elpis_sha256_update(&ctx, nb, 4);
    for (uint32_t i = 0; i < n; i++) {
        const elpis_vector_hit &h = hits[i];
        uint8_t rank[4] = {(uint8_t)(h.rank & 0xffu), (uint8_t)((h.rank >> 8) & 0xffu),
                           (uint8_t)((h.rank >> 16) & 0xffu), (uint8_t)((h.rank >> 24) & 0xffu)};
        elpis_sha256_update(&ctx, rank, 4);
        elpis_sha256_update(&ctx, h.chunk_digest, 64);
        elpis_sha256_update(&ctx, h.doc_digest, 64);
        elpis_sha256_update(&ctx, h.shard_digest, 64);
        /* Canonical integer key, little-endian two's complement. Raw host
         * double bytes are deliberately excluded from the identity. */
        uint64_t bits = (uint64_t)h.score_key;
        uint8_t sb[8];
        for (int k = 0; k < 8; k++) sb[k] = (uint8_t)(bits >> (8 * k));
        elpis_sha256_update(&ctx, sb, 8);
    }
    uint8_t d[32];
    elpis_sha256_final(&ctx, d);
    elpis_hex32(d, out);
    return 0;
}

} // extern "C"
