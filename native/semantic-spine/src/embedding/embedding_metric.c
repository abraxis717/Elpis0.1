/* embedding_metric.c — Deterministic exact similarity scoring.
 *
 * Accumulates in IEEE-754 float64 with fixed accumulation order.
 * Quantizes to integer score key for canonical ordering.
 *
 * Does NOT use parallel reduction, SIMD, fast-math, or approximate search.
 */
#include "elpis_semantic/embedding_metric.h"
#include <math.h>
#include <string.h>
#include <float.h>

/* ──────────────────────────────────────────────────────────────────── */
/* Float32 reading from canonical LE bytes                               */
/* ──────────────────────────────────────────────────────────────────── */

static float read_float32_le(const uint8_t *bytes) {
    float val;
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    memcpy(&val, bytes, 4);
#else
    uint32_t bits;
    memcpy(&bits, bytes, 4);
    bits = __builtin_bswap32(bits);
    memcpy(&val, &bits, 4);
#endif
    return val;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Validate finite values                                                */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_validate_finite(const uint8_t *bytes, uint32_t dimensions) {
    for (uint32_t i = 0; i < dimensions; i++) {
        float val = read_float32_le(bytes + i * 4);
        if (!isfinite(val)) return -1;
    }
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Cosine similarity                                                     */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_cosine_similarity(const uint8_t *bytes_a,
                                       const uint8_t *bytes_b,
                                       uint32_t dimensions,
                                       embedding_metric_result *out) {
    if (!bytes_a || !bytes_b || !out || dimensions == 0) return -1;
    if (elpis_embedding_validate_finite(bytes_a, dimensions) != 0) return -1;
    if (elpis_embedding_validate_finite(bytes_b, dimensions) != 0) return -1;

    double dot = 0.0, norm_a = 0.0, norm_b = 0.0;
    for (uint32_t i = 0; i < dimensions; i++) {
        float fa = read_float32_le(bytes_a + i * 4);
        float fb = read_float32_le(bytes_b + i * 4);
        double da = (double)fa;
        double db = (double)fb;
        dot += da * db;
        norm_a += da * da;
        norm_b += db * db;
    }

    norm_a = sqrt(norm_a);
    norm_b = sqrt(norm_b);

    out->is_valid = 0;
    if (norm_a < 1e-15 || norm_b < 1e-15) {
        out->raw_score = 0.0;
        out->score_key = 0;
        out->is_valid = 1;
        return 0;
    }

    double cosine = dot / (norm_a * norm_b);
    /* Clamp to [-1, 1] for numerical safety */
    if (cosine > 1.0) cosine = 1.0;
    if (cosine < -1.0) cosine = -1.0;
    if (!isfinite(cosine)) return -1;

    out->raw_score = cosine;
    out->score_key = elpis_embedding_quantize_score(cosine, EMBEDDING_SCORE_SCALE);
    out->is_valid = 1;
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Inner product                                                         */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_inner_product(const uint8_t *bytes_a,
                                   const uint8_t *bytes_b,
                                   uint32_t dimensions,
                                   embedding_metric_result *out) {
    if (!bytes_a || !bytes_b || !out || dimensions == 0) return -1;
    if (elpis_embedding_validate_finite(bytes_a, dimensions) != 0) return -1;
    if (elpis_embedding_validate_finite(bytes_b, dimensions) != 0) return -1;

    double dot = 0.0;
    for (uint32_t i = 0; i < dimensions; i++) {
        double da = (double)read_float32_le(bytes_a + i * 4);
        double db = (double)read_float32_le(bytes_b + i * 4);
        dot += da * db;
    }

    if (!isfinite(dot)) return -1;

    out->raw_score = dot;
    out->score_key = elpis_embedding_quantize_score(dot, EMBEDDING_SCORE_SCALE);
    out->is_valid = 1;
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Squared L2 distance                                                   */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_squared_l2_distance(const uint8_t *bytes_a,
                                         const uint8_t *bytes_b,
                                         uint32_t dimensions,
                                         embedding_metric_result *out) {
    if (!bytes_a || !bytes_b || !out || dimensions == 0) return -1;
    if (elpis_embedding_validate_finite(bytes_a, dimensions) != 0) return -1;
    if (elpis_embedding_validate_finite(bytes_b, dimensions) != 0) return -1;

    double dist = 0.0;
    for (uint32_t i = 0; i < dimensions; i++) {
        double da = (double)read_float32_le(bytes_a + i * 4);
        double db = (double)read_float32_le(bytes_b + i * 4);
        double diff = da - db;
        dist += diff * diff;
    }

    if (!isfinite(dist)) return -1;

    out->raw_score = dist;
    out->score_key = elpis_embedding_quantize_distance(dist);
    out->is_valid = 1;
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Quantization                                                          */
/* ──────────────────────────────────────────────────────────────────── */

int64_t elpis_embedding_quantize_score(double raw, int64_t scale) {
    /* Round-to-nearest-even (banker's rounding) */
    double scaled = raw * (double)scale;
    int64_t key;

    /* Check for negative zero: canonicalize */
    if (scaled == 0.0) scaled = 0.0;

    if (scaled < 0.0) {
        double abs_scaled = -scaled;
        int64_t abs_key;
        double frac = abs_scaled - floor(abs_scaled);
        int64_t lo = (int64_t)floor(abs_scaled);
        if (frac > 0.5) {
            abs_key = lo + 1;
        } else if (frac < 0.5) {
            abs_key = lo;
        } else {
            /* Exactly 0.5: round to even */
            abs_key = (lo % 2 == 0) ? lo : lo + 1;
        }
        key = -abs_key;
    } else {
        double frac = scaled - floor(scaled);
        int64_t lo = (int64_t)floor(scaled);
        if (frac > 0.5) {
            key = lo + 1;
        } else if (frac < 0.5) {
            key = lo;
        } else {
            /* Exactly 0.5: round to even */
            key = (lo % 2 == 0) ? lo : lo + 1;
        }
    }

    /* Clamp */
    if (key > scale) key = scale;
    if (key < -scale) key = -scale;
    return key;
}

int64_t elpis_embedding_quantize_distance(double raw) {
    /* Saturation threshold: any raw value that would produce > EMBEDDING_DISTANCE_KEY_MAX
     * when multiplied by EMBEDDING_SCORE_SCALE is clamped. */
    if (raw < 0.0) return 0;
    double threshold = (double)EMBEDDING_DISTANCE_KEY_MAX / (double)EMBEDDING_SCORE_SCALE;
    if (raw >= threshold) return EMBEDDING_DISTANCE_KEY_MAX;
    int64_t key = (int64_t)(raw * (double)EMBEDDING_SCORE_SCALE);
    if (key > EMBEDDING_DISTANCE_KEY_MAX) key = EMBEDDING_DISTANCE_KEY_MAX;
    if (key < 0) key = 0;
    return key;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Dispatch by profile metric                                            */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_compute_metric(
    const elpis_semantic_embedding_profile_v1 *profile,
    const uint8_t *bytes_a, const uint8_t *bytes_b,
    uint32_t dimensions,
    embedding_metric_result *out) {
    if (!profile || !bytes_a || !bytes_b || !out) return -1;
    if (elpis_embedding_validate_finite(bytes_a, dimensions) != 0) return -1;
    if (elpis_embedding_validate_finite(bytes_b, dimensions) != 0) return -1;

    switch (profile->distance_metric) {
        case EMBEDDING_METRIC_COSINE:
            return elpis_embedding_cosine_similarity(bytes_a, bytes_b, dimensions, out);
        case EMBEDDING_METRIC_INNER_PRODUCT:
            return elpis_embedding_inner_product(bytes_a, bytes_b, dimensions, out);
        case EMBEDDING_METRIC_SQUARED_L2:
            return elpis_embedding_squared_l2_distance(bytes_a, bytes_b, dimensions, out);
        default:
            return -1;
    }
}
