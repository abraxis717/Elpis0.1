/* elpis_semantic/embedding_metric.h — Deterministic exact similarity scoring.
 *
 * Computes exact cosine similarity, inner product, and squared L2 distance
 * over canonical float32 bytes. Results are accumulated in IEEE-754 float64
 * with fixed accumulation order. Raw float is exposed for observability;
 * only the integer score key determines canonical ordering.
 *
 * Cosine / inner-product score scale: 1,000,000,000
 * Squared L2 distance key: monotonic integer with explicit saturation.
 */
#ifndef ELPIS_SEMANTIC_EMBEDDING_METRIC_H
#define ELPIS_SEMANTIC_EMBEDDING_METRIC_H

#include "elpis_semantic/embedding_profile.h"
#include "elpis_semantic/embedding_vector.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ──────────────────────────────────────────────────────────────────── */
/* Score constants                                                       */
/* ──────────────────────────────────────────────────────────────────── */

#define EMBEDDING_SCORE_SCALE 1000000000LL  /* 10^9 for cosine/inner product */
#define EMBEDDING_SCORE_KEY_MIN (-EMBEDDING_SCORE_SCALE)
#define EMBEDDING_SCORE_KEY_MAX  EMBEDDING_SCORE_SCALE

/* For squared L2: saturation at 2^31 - 1 (max positive int32 mapped to int64) */
#define EMBEDDING_DISTANCE_KEY_MAX 2147483647LL

/* ──────────────────────────────────────────────────────────────────── */
/* Metric result                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct embedding_metric_result {
    int64_t  score_key;        /* canonical integer score (or distance key) */
    double   raw_score;        /* diagnostic floating-point value */
    uint32_t is_valid;         /* 1 = valid result, 0 = rejected */
} embedding_metric_result;

/* ──────────────────────────────────────────────────────────────────── */
/* Metric operations                                                     */
/* ──────────────────────────────────────────────────────────────────── */

/* Compute similarity metric between two vectors. Both must share the same
 * embedding profile (checked by profile digest). Returns SEMANTIC_OK on success.
 *
 * profile:  shared embedding profile (determines which metric to use)
 * bytes_a:  canonical float32 bytes of vector A
 * bytes_b:  canonical float32 bytes of vector B
 * dimensions: must match profile dimensions
 * out:      filled with score_key, raw_score, is_valid
 *
 * Rejects when:
 *   - profile digests differ (checked by caller)
 *   - dimensions differ
 *   - dtypes differ
 *   - vectors contain nonfinite values
 *   - metric is unsupported */
int elpis_embedding_compute_metric(
    const elpis_semantic_embedding_profile_v1 *profile,
    const uint8_t *bytes_a, const uint8_t *bytes_b,
    uint32_t dimensions,
    embedding_metric_result *out);

/* Compute exact cosine similarity. Accumulates in float64. */
int elpis_embedding_cosine_similarity(const uint8_t *bytes_a,
                                       const uint8_t *bytes_b,
                                       uint32_t dimensions,
                                       embedding_metric_result *out);

/* Compute exact inner product. Accumulates in float64. */
int elpis_embedding_inner_product(const uint8_t *bytes_a,
                                   const uint8_t *bytes_b,
                                   uint32_t dimensions,
                                   embedding_metric_result *out);

/* Compute exact squared L2 distance. Accumulates in float64. */
int elpis_embedding_squared_l2_distance(const uint8_t *bytes_a,
                                         const uint8_t *bytes_b,
                                         uint32_t dimensions,
                                         embedding_metric_result *out);

/* Quantize a double score to an integer score key.
 * Round-to-nearest-even (banker's rounding), clamped to [MIN, MAX]. */
int64_t elpis_embedding_quantize_score(double raw, int64_t scale);

/* Quantize a double distance to an integer distance key.
 * Truncate toward zero, clamped to [0, MAX]. */
int64_t elpis_embedding_quantize_distance(double raw);

/* Validate that canonical float32 bytes contain only finite values. */
int elpis_embedding_validate_finite(const uint8_t *bytes, uint32_t dimensions);

#ifdef __cplusplus
}
#endif
#endif
