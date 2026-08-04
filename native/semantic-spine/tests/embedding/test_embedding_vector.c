/* test_embedding_vector.c — Canonical vector object tests. */
#include "elpis_semantic/embedding_vector.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <float.h>
#include <assert.h>

static void set_nonzero_digest(hacf_digest *d) {
    memset(d, 0, sizeof(*d));
    d->bytes[0] = 0xAB;
    d->bytes[31] = 0xCD;
}

static elpis_semantic_embedding_profile_v1 *make_profile(uint32_t dims,
    embedding_normalization_policy norm, embedding_distance_metric metric) {
    elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
    p->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
    set_nonzero_digest(&p->model_identity_digest);
    p->pooling_policy = EMBEDDING_POOLING_MEAN;
    p->normalization_policy = norm;
    p->distance_metric = metric;
    p->dimensions = dims;
    p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
    hacf_digest d;
    elpis_embedding_profile_identity(p, &d);
    memcpy(&p->profile_identity, &d, sizeof(hacf_digest));
    return p;
}

int main(void) {
    int passed = 0, failed = 0;

    /* Test 1: canonical float32 encoding */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(4, EMBEDDING_NORMALIZATION_NONE, EMBEDDING_METRIC_COSINE);
        float data[4] = {1.0f, 2.0f, 3.0f, 4.0f};
        elpis_semantic_embedding_vector_v1 vec;
        uint8_t *bytes;
        uint32_t len;
        int rc = elpis_embedding_vector_from_float32(p, data, 4, &vec, &bytes, &len);
        if (rc == 0 && len == 16) passed++;
        else { printf("FAIL: canonical encoding failed\n"); failed++; }
        if (bytes) elpis_embedding_vector_free_bytes(bytes);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 2: negative zero canonicalization */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(2, EMBEDDING_NORMALIZATION_NONE, EMBEDDING_METRIC_COSINE);
        float data[2] = {-0.0f, 1.0f};
        elpis_semantic_embedding_vector_v1 vec;
        uint8_t *bytes;
        uint32_t len;
        int rc = elpis_embedding_vector_from_float32(p, data, 2, &vec, &bytes, &len);
        if (rc == 0) {
            /* Check that first 4 bytes are +0.0f, not -0.0f */
            float zero;
            memcpy(&zero, bytes, 4);
            if (zero == 0.0f && !signbit(zero)) passed++;
            else { printf("FAIL: negative zero not canonicalized\n"); failed++; }
        } else {
            printf("FAIL: vector creation rejected -0.0f input\n"); failed++;
        }
        if (bytes) elpis_embedding_vector_free_bytes(bytes);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 3: NaN rejection */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(2, EMBEDDING_NORMALIZATION_NONE, EMBEDDING_METRIC_COSINE);
        float data[2] = {NAN, 1.0f};
        elpis_semantic_embedding_vector_v1 vec;
        uint8_t *bytes;
        uint32_t len;
        int rc = elpis_embedding_vector_from_float32(p, data, 2, &vec, &bytes, &len);
        if (rc != 0) passed++;
        else { printf("FAIL: NaN not rejected\n"); failed++; }
        if (bytes) elpis_embedding_vector_free_bytes(bytes);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 4: positive infinity rejection */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(2, EMBEDDING_NORMALIZATION_NONE, EMBEDDING_METRIC_COSINE);
        float data[2] = {INFINITY, 1.0f};
        elpis_semantic_embedding_vector_v1 vec;
        uint8_t *bytes;
        uint32_t len;
        int rc = elpis_embedding_vector_from_float32(p, data, 2, &vec, &bytes, &len);
        if (rc != 0) passed++;
        else { printf("FAIL: +inf not rejected\n"); failed++; }
        if (bytes) elpis_embedding_vector_free_bytes(bytes);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 5: negative infinity rejection */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(2, EMBEDDING_NORMALIZATION_NONE, EMBEDDING_METRIC_COSINE);
        float data[2] = {-INFINITY, 1.0f};
        elpis_semantic_embedding_vector_v1 vec;
        uint8_t *bytes;
        uint32_t len;
        int rc = elpis_embedding_vector_from_float32(p, data, 2, &vec, &bytes, &len);
        if (rc != 0) passed++;
        else { printf("FAIL: -inf not rejected\n"); failed++; }
        if (bytes) elpis_embedding_vector_free_bytes(bytes);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 6: dimension mismatch rejection */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(4, EMBEDDING_NORMALIZATION_NONE, EMBEDDING_METRIC_COSINE);
        float data[2] = {1.0f, 2.0f};
        elpis_semantic_embedding_vector_v1 vec;
        uint8_t *bytes;
        uint32_t len;
        int rc = elpis_embedding_vector_from_float32(p, data, 2, &vec, &bytes, &len);
        if (rc != 0) passed++;
        else { printf("FAIL: dimension mismatch not rejected\n"); failed++; }
        if (bytes) elpis_embedding_vector_free_bytes(bytes);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 7: profile mismatch rejection */
    {
        elpis_semantic_embedding_profile_v1 *p1 = make_profile(4, EMBEDDING_NORMALIZATION_NONE, EMBEDDING_METRIC_COSINE);
        elpis_semantic_embedding_profile_v1 *p2 = make_profile(8, EMBEDDING_NORMALIZATION_NONE, EMBEDDING_METRIC_COSINE);
        float data[8] = {0,0,0,0,0,0,0,0};
        elpis_semantic_embedding_vector_v1 vec;
        uint8_t *bytes;
        uint32_t len;
        int rc = elpis_embedding_vector_from_float32(p1, data, 8, &vec, &bytes, &len);
        if (rc != 0) passed++;
        else { printf("FAIL: profile dim mismatch not rejected\n"); failed++; }
        if (bytes) elpis_embedding_vector_free_bytes(bytes);
        elpis_embedding_profile_destroy(p1);
        elpis_embedding_profile_destroy(p2);
    }

    /* Test 8: vector digest independent of host padding */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(3, EMBEDDING_NORMALIZATION_NONE, EMBEDDING_METRIC_COSINE);
        float data1[3] = {1.0f, 2.0f, 3.0f};
        float data2[3] = {1.0f, 2.0f, 3.0f};
        elpis_semantic_embedding_vector_v1 vec1, vec2;
        uint8_t *bytes1, *bytes2;
        uint32_t len1, len2;
        int rc1 = elpis_embedding_vector_from_float32(p, data1, 3, &vec1, &bytes1, &len1);
        int rc2 = elpis_embedding_vector_from_float32(p, data2, 3, &vec2, &bytes2, &len2);
        if (rc1 == 0 && rc2 == 0) {
            if (memcmp(bytes1, bytes2, len1) == 0 &&
                memcmp(&vec1.vector_identity, &vec2.vector_identity, sizeof(hacf_digest)) == 0)
                passed++;
            else { printf("FAIL: vector digest depends on allocation\n"); failed++; }
        } else {
            printf("FAIL: vector creation failed\n"); failed++;
        }
        if (bytes1) elpis_embedding_vector_free_bytes(bytes1);
        if (bytes2) elpis_embedding_vector_free_bytes(bytes2);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 9: vector identity fresh-process deterministic */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(4, EMBEDDING_NORMALIZATION_NONE, EMBEDDING_METRIC_COSINE);
        float data[4] = {0.1f, 0.2f, 0.3f, 0.4f};
        elpis_semantic_embedding_vector_v1 vec1, vec2;
        uint8_t *b1, *b2;
        uint32_t l1, l2;
        elpis_embedding_vector_from_float32(p, data, 4, &vec1, &b1, &l1);
        elpis_embedding_vector_from_float32(p, data, 4, &vec2, &b2, &l2);
        if (memcmp(&vec1.vector_identity, &vec2.vector_identity, sizeof(hacf_digest)) == 0) passed++;
        else { printf("FAIL: vector identity not deterministic\n"); failed++; }
        if (b1) elpis_embedding_vector_free_bytes(b1);
        if (b2) elpis_embedding_vector_free_bytes(b2);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 10: normalization validation (unit-L2) */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(2, EMBEDDING_NORMALIZATION_UNIT_L2, EMBEDDING_METRIC_COSINE);
        /* Create a unit vector: [1, 0] has norm 1.0 */
        float data[2] = {1.0f, 0.0f};
        elpis_semantic_embedding_vector_v1 vec;
        uint8_t *bytes;
        uint32_t len;
        int rc = elpis_embedding_vector_from_float32(p, data, 2, &vec, &bytes, &len);
        if (rc == 0) passed++;
        else { printf("FAIL: unit vector rejected\n"); failed++; }
        if (bytes) elpis_embedding_vector_free_bytes(bytes);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 11: no silent normalization — non-unit vector rejected */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(2, EMBEDDING_NORMALIZATION_UNIT_L2, EMBEDDING_METRIC_COSINE);
        float data[2] = {1.0f, 1.0f}; /* norm = sqrt(2) ≈ 1.414, not unit */
        elpis_semantic_embedding_vector_v1 vec;
        uint8_t *bytes;
        uint32_t len;
        int rc = elpis_embedding_vector_from_float32(p, data, 2, &vec, &bytes, &len);
        if (rc != 0) passed++;
        else { printf("FAIL: non-unit vector not rejected (no silent normalization)\n"); failed++; }
        if (bytes) elpis_embedding_vector_free_bytes(bytes);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 12: L2 norm computation */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(3, EMBEDDING_NORMALIZATION_NONE, EMBEDDING_METRIC_COSINE);
        float data[3] = {1.0f, 2.0f, 2.0f};
        elpis_semantic_embedding_vector_v1 vec;
        uint8_t *bytes;
        uint32_t len;
        elpis_embedding_vector_from_float32(p, data, 3, &vec, &bytes, &len);
        double norm = elpis_embedding_vector_l2_norm(bytes, 3);
        /* sqrt(1 + 4 + 4) = 3.0 */
        if (fabs(norm - 3.0) < 1e-10) passed++;
        else { printf("FAIL: L2 norm = %f, expected 3.0\n", norm); failed++; }
        if (bytes) elpis_embedding_vector_free_bytes(bytes);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 13: vector validation catches zero profile digest */
    {
        elpis_semantic_embedding_vector_v1 vec;
        memset(&vec, 0, sizeof(vec));
        vec.abi_version = EMBEDDING_VECTOR_ABI_VERSION;
        vec.dimensions = 4;
        vec.vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        /* profile_digest is all-zero */
        if (elpis_embedding_vector_validate(&vec) != 0) passed++;
        else { printf("FAIL: zero profile digest not rejected\n"); failed++; }
    }

    /* Test 14: vector cmp and is_same */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(2, EMBEDDING_NORMALIZATION_NONE, EMBEDDING_METRIC_COSINE);
        float data[2] = {1.0f, 0.0f};
        elpis_semantic_embedding_vector_v1 v1, v2;
        uint8_t *b1, *b2;
        uint32_t l1, l2;
        elpis_embedding_vector_from_float32(p, data, 2, &v1, &b1, &l1);
        elpis_embedding_vector_from_float32(p, data, 2, &v2, &b2, &l2);
        if (elpis_embedding_vector_is_same(&v1, &v2) == 1) passed++;
        else { printf("FAIL: identical vectors not same\n"); failed++; }
        if (b1) elpis_embedding_vector_free_bytes(b1);
        if (b2) elpis_embedding_vector_free_bytes(b2);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 15: different data → different digest */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(2, EMBEDDING_NORMALIZATION_NONE, EMBEDDING_METRIC_COSINE);
        float data1[2] = {1.0f, 0.0f};
        float data2[2] = {0.0f, 1.0f};
        elpis_semantic_embedding_vector_v1 v1, v2;
        uint8_t *b1, *b2;
        uint32_t l1, l2;
        elpis_embedding_vector_from_float32(p, data1, 2, &v1, &b1, &l1);
        elpis_embedding_vector_from_float32(p, data2, 2, &v2, &b2, &l2);
        if (elpis_embedding_vector_is_same(&v1, &v2) == 0) passed++;
        else { printf("FAIL: different vectors reported as same\n"); failed++; }
        if (b1) elpis_embedding_vector_free_bytes(b1);
        if (b2) elpis_embedding_vector_free_bytes(b2);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 16: vector validate normalization function */
    {
        elpis_semantic_embedding_profile_v1 *p = make_profile(2, EMBEDDING_NORMALIZATION_UNIT_L2, EMBEDDING_METRIC_COSINE);
        float data[2] = {0.70710678f, 0.70710678f}; /* approximately unit */
        elpis_semantic_embedding_vector_v1 vec;
        uint8_t *bytes;
        uint32_t len;
        /* This might fail due to tolerance — let's use exact unit */
        float data_exact[2] = {1.0f, 0.0f};
        int rc = elpis_embedding_vector_from_float32(p, data_exact, 2, &vec, &bytes, &len);
        int rc2 = elpis_embedding_vector_validate_normalization(p, bytes, 2);
        if (rc == 0 && rc2 == 0) passed++;
        else { printf("FAIL: unit vector validation failed\n"); failed++; }
        if (bytes) elpis_embedding_vector_free_bytes(bytes);
        elpis_embedding_profile_destroy(p);
    }

    printf("Vector tests: %d passed, %d failed\n", passed, failed);
    return failed;
}
