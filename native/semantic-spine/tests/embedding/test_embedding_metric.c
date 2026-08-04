/* test_embedding_metric.c — Deterministic exact similarity scoring tests. */
#include "elpis_semantic/embedding_metric.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <float.h>

/* Helper: write float32 as LE bytes */
static void write_f32_le(uint8_t *out, float val) {
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    memcpy(out, &val, 4);
#else
    uint32_t bits;
    memcpy(&bits, &val, 4);
    bits = __builtin_bswap32(bits);
    memcpy(out, &bits, 4);
#endif
}

int main(void) {
    int passed = 0, failed = 0;

    /* Test 1: cosine known fixture — identical vectors */
    {
        uint8_t a[8], b[8];
        write_f32_le(a, 1.0f); write_f32_le(a+4, 0.0f);
        memcpy(b, a, 8);
        embedding_metric_result r;
        int rc = elpis_embedding_cosine_similarity(a, b, 2, &r);
        if (rc == 0 && r.is_valid && fabs(r.raw_score - 1.0) < 1e-10) passed++;
        else { printf("FAIL: cosine of identical vectors != 1.0\n"); failed++; }
    }

    /* Test 2: cosine known fixture — orthogonal vectors */
    {
        uint8_t a[8], b[8];
        write_f32_le(a, 1.0f); write_f32_le(a+4, 0.0f);
        write_f32_le(b, 0.0f); write_f32_le(b+4, 1.0f);
        embedding_metric_result r;
        elpis_embedding_cosine_similarity(a, b, 2, &r);
        if (r.is_valid && fabs(r.raw_score) < 1e-10) passed++;
        else { printf("FAIL: cosine of orthogonal vectors != 0.0\n"); failed++; }
    }

    /* Test 3: cosine known fixture — opposite vectors */
    {
        uint8_t a[8], b[8];
        write_f32_le(a, 1.0f); write_f32_le(a+4, 0.0f);
        write_f32_le(b, -1.0f); write_f32_le(b+4, 0.0f);
        embedding_metric_result r;
        elpis_embedding_cosine_similarity(a, b, 2, &r);
        if (r.is_valid && fabs(r.raw_score - (-1.0)) < 1e-10) passed++;
        else { printf("FAIL: cosine of opposite vectors != -1.0\n"); failed++; }
    }

    /* Test 4: inner-product known fixture */
    {
        uint8_t a[12], b[12];
        write_f32_le(a, 1.0f); write_f32_le(a+4, 2.0f); write_f32_le(a+8, 3.0f);
        write_f32_le(b, 4.0f); write_f32_le(b+4, 5.0f); write_f32_le(b+8, 6.0f);
        /* 1*4 + 2*5 + 3*6 = 4 + 10 + 18 = 32 */
        embedding_metric_result r;
        elpis_embedding_inner_product(a, b, 3, &r);
        if (r.is_valid && fabs(r.raw_score - 32.0) < 1e-10) passed++;
        else { printf("FAIL: inner product != 32.0, got %f\n", r.raw_score); failed++; }
    }

    /* Test 5: squared-L2 known fixture */
    {
        uint8_t a[8], b[8];
        write_f32_le(a, 1.0f); write_f32_le(a+4, 2.0f);
        write_f32_le(b, 4.0f); write_f32_le(b+4, 6.0f);
        /* (1-4)^2 + (2-6)^2 = 9 + 16 = 25 */
        embedding_metric_result r;
        elpis_embedding_squared_l2_distance(a, b, 2, &r);
        if (r.is_valid && fabs(r.raw_score - 25.0) < 1e-10) passed++;
        else { printf("FAIL: squared L2 != 25.0, got %f\n", r.raw_score); failed++; }
    }

    /* Test 6: metric/profile dispatch by profile */
    {
        elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
        p->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        p->pooling_policy = EMBEDDING_POOLING_MEAN;
        p->normalization_policy = EMBEDDING_NORMALIZATION_NONE;
        p->distance_metric = EMBEDDING_METRIC_INNER_PRODUCT;
        p->dimensions = 2;
        p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;

        uint8_t a[8], b[8];
        write_f32_le(a, 1.0f); write_f32_le(a+4, 2.0f);
        write_f32_le(b, 3.0f); write_f32_le(b+4, 4.0f);

        embedding_metric_result r;
        int rc = elpis_embedding_compute_metric(p, a, b, 2, &r);
        /* inner product: 1*3 + 2*4 = 11 */
        if (rc == 0 && r.is_valid && fabs(r.raw_score - 11.0) < 1e-10) passed++;
        else { printf("FAIL: metric dispatch inner product != 11.0\n"); failed++; }
        elpis_embedding_profile_destroy(p);
    }

    /* Test 7: fixed accumulation order — same result on replay */
    {
        uint8_t a[24], b[24];
        for (int i = 0; i < 6; i++) {
            write_f32_le(a + i*4, (float)(i+1));
            write_f32_le(b + i*4, (float)(i*2));
        }
        embedding_metric_result r1, r2;
        elpis_embedding_cosine_similarity(a, b, 6, &r1);
        elpis_embedding_cosine_similarity(a, b, 6, &r2);
        if (r1.score_key == r2.score_key && r1.raw_score == r2.raw_score) passed++;
        else { printf("FAIL: cosine not reproducible\n"); failed++; }
    }

    /* Test 8: integer score-key determinism */
    {
        uint8_t a[8], b[8];
        write_f32_le(a, 0.6f); write_f32_le(a+4, 0.8f);
        write_f32_le(b, 1.0f); write_f32_le(b+4, 0.0f);
        /* cos = 0.6*1.0 + 0.8*0.0 = 0.6 */
        /* norm_a = sqrt(0.36 + 0.64) = 1.0, norm_b = 1.0 */
        /* cosine = 0.6 */
        embedding_metric_result r1, r2, r3;
        elpis_embedding_cosine_similarity(a, b, 2, &r1);
        elpis_embedding_cosine_similarity(a, b, 2, &r2);
        elpis_embedding_cosine_similarity(a, b, 2, &r3);
        if (r1.score_key == r2.score_key && r2.score_key == r3.score_key) passed++;
        else { printf("FAIL: score key not deterministic\n"); failed++; }
    }

    /* Test 9: score key scale check */
    {
        int64_t key = elpis_embedding_quantize_score(0.6, EMBEDDING_SCORE_SCALE);
        /* 0.6 * 1e9 = 600,000,000 */
        if (key == 600000000LL) passed++;
        else { printf("FAIL: score key = %lld, expected 600000000\n", (long long)key); failed++; }
    }

    /* Test 10: score key clamping */
    {
        int64_t key = elpis_embedding_quantize_score(1.5, EMBEDDING_SCORE_SCALE);
        if (key == EMBEDDING_SCORE_SCALE) passed++;
        else { printf("FAIL: score key not clamped up\n"); failed++; }
    }

    /* Test 11: NaN vector rejected */
    {
        uint8_t a[8], b[8];
        write_f32_le(a, 1.0f); write_f32_le(a+4, 0.0f);
        write_f32_le(b, NAN); write_f32_le(b+4, 0.0f);
        embedding_metric_result r;
        int rc = elpis_embedding_cosine_similarity(a, b, 2, &r);
        if (rc != 0) passed++;
        else { printf("FAIL: NaN vector not rejected\n"); failed++; }
    }

    /* Test 12: infinity vector rejected */
    {
        uint8_t a[8], b[8];
        write_f32_le(a, 1.0f); write_f32_le(a+4, 0.0f);
        write_f32_le(b, INFINITY); write_f32_le(b+4, 0.0f);
        embedding_metric_result r;
        int rc = elpis_embedding_cosine_similarity(a, b, 2, &r);
        if (rc != 0) passed++;
        else { printf("FAIL: infinity vector not rejected\n"); failed++; }
    }

    /* Test 13: zero vector cosine handled */
    {
        uint8_t a[8], b[8];
        write_f32_le(a, 0.0f); write_f32_le(a+4, 0.0f);
        write_f32_le(b, 1.0f); write_f32_le(b+4, 0.0f);
        embedding_metric_result r;
        int rc = elpis_embedding_cosine_similarity(a, b, 2, &r);
        if (rc == 0 && r.is_valid) passed++;
        else { printf("FAIL: zero vector cosine failed\n"); failed++; }
    }

    /* Test 14: squared L2 distance key */
    {
        uint8_t a[4], b[4];
        write_f32_le(a, 1.0f);
        write_f32_le(b, 2.0f);
        /* (1-2)^2 = 1 */
        embedding_metric_result r;
        elpis_embedding_squared_l2_distance(a, b, 1, &r);
        int64_t key = elpis_embedding_quantize_distance(1.0);
        if (key == EMBEDDING_SCORE_SCALE) passed++; /* 1.0 * 1e9 */
        else { printf("FAIL: distance key wrong: %lld\n", (long long)key); failed++; }
    }

    /* Test 15: validate_finite rejects NaN */
    {
        uint8_t a[4];
        write_f32_le(a, NAN);
        if (elpis_embedding_validate_finite(a, 1) != 0) passed++;
        else { printf("FAIL: NaN not caught by validate_finite\n"); failed++; }
    }

    /* Test 16: same-process exact replay */
    {
        uint8_t a[32], b[32];
        for (int i = 0; i < 8; i++) {
            write_f32_le(a + i*4, (float)(i*3.7 + 0.1));
            write_f32_le(b + i*4, (float)(i*2.1 + 0.5));
        }
        embedding_metric_result results[5];
        for (int i = 0; i < 5; i++) {
            elpis_embedding_cosine_similarity(a, b, 8, &results[i]);
        }
        int all_same = 1;
        for (int i = 1; i < 5; i++) {
            if (results[i].score_key != results[0].score_key ||
                results[i].raw_score != results[0].raw_score) {
                all_same = 0;
            }
        }
        if (all_same) passed++;
        else { printf("FAIL: same-process replay not exact\n"); failed++; }
    }

    /* Test 17: validate_finite passes all-finite */
    {
        uint8_t a[8];
        write_f32_le(a, 1.0f); write_f32_le(a+4, -1.0f);
        if (elpis_embedding_validate_finite(a, 2) == 0) passed++;
        else { printf("FAIL: finite vector rejected\n"); failed++; }
    }

    /* Test 18: distance key saturation */
    {
        int64_t key = elpis_embedding_quantize_distance(1e15);
        if (key == EMBEDDING_DISTANCE_KEY_MAX) passed++;
        else { printf("FAIL: distance key not saturated\n"); failed++; }
    }

    printf("Metric tests: %d passed, %d failed\n", passed, failed);
    return failed;
}
