/* test_embedding_profile.c — Profile identity tests. */
#include "elpis_semantic/embedding_profile.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>

static void set_nonzero_digest(hacf_digest *d) {
    memset(d, 0, sizeof(*d));
    d->bytes[0] = 0xAB;
    d->bytes[31] = 0xCD;
}

static void set_digest_byte(hacf_digest *d, unsigned char v) {
    memset(d, 0, sizeof(*d));
    d->bytes[0] = v;
}

int main(void) {
    int passed = 0, failed = 0;

    /* Test 1: profile identity deterministic */
    {
        elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
        p->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        set_nonzero_digest(&p->model_identity_digest);
        p->pooling_policy = EMBEDDING_POOLING_MEAN;
        p->normalization_policy = EMBEDDING_NORMALIZATION_UNIT_L2;
        p->distance_metric = EMBEDDING_METRIC_COSINE;
        p->dimensions = 768;
        p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;

        hacf_digest d1, d2;
        elpis_embedding_profile_identity(p, &d1);
        elpis_embedding_profile_identity(p, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) == 0) passed++;
        else { printf("FAIL: profile identity not deterministic\n"); failed++; }
        elpis_embedding_profile_destroy(p);
    }

    /* Test 2: identity changes with model identity */
    {
        elpis_semantic_embedding_profile_v1 *p1 = elpis_embedding_profile_create();
        elpis_semantic_embedding_profile_v1 *p2 = elpis_embedding_profile_create();
        p1->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        p2->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        set_digest_byte(&p1->model_identity_digest, 0x11);
        set_digest_byte(&p2->model_identity_digest, 0x22);
        p1->pooling_policy = p2->pooling_policy = EMBEDDING_POOLING_MEAN;
        p1->normalization_policy = p2->normalization_policy = EMBEDDING_NORMALIZATION_UNIT_L2;
        p1->distance_metric = p2->distance_metric = EMBEDDING_METRIC_COSINE;
        p1->dimensions = p2->dimensions = 768;
        p1->vector_dtype = p2->vector_dtype = EMBEDDING_DTYPE_FLOAT32;

        hacf_digest d1, d2;
        elpis_embedding_profile_identity(p1, &d1);
        elpis_embedding_profile_identity(p2, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) != 0) passed++;
        else { printf("FAIL: identity should differ with model identity\n"); failed++; }
        elpis_embedding_profile_destroy(p1);
        elpis_embedding_profile_destroy(p2);
    }

    /* Test 3: identity changes with tokenizer identity */
    {
        elpis_semantic_embedding_profile_v1 *p1 = elpis_embedding_profile_create();
        elpis_semantic_embedding_profile_v1 *p2 = elpis_embedding_profile_create();
        p1->provider_kind = p2->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        set_nonzero_digest(&p1->model_identity_digest);
        memcpy(&p2->model_identity_digest, &p1->model_identity_digest, sizeof(hacf_digest));
        set_digest_byte(&p1->tokenizer_identity_digest, 0xAA);
        set_digest_byte(&p2->tokenizer_identity_digest, 0xBB);
        p1->pooling_policy = p2->pooling_policy = EMBEDDING_POOLING_MEAN;
        p1->normalization_policy = p2->normalization_policy = EMBEDDING_NORMALIZATION_UNIT_L2;
        p1->distance_metric = p2->distance_metric = EMBEDDING_METRIC_COSINE;
        p1->dimensions = p2->dimensions = 768;
        p1->vector_dtype = p2->vector_dtype = EMBEDDING_DTYPE_FLOAT32;

        hacf_digest d1, d2;
        elpis_embedding_profile_identity(p1, &d1);
        elpis_embedding_profile_identity(p2, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) != 0) passed++;
        else { printf("FAIL: identity should differ with tokenizer identity\n"); failed++; }
        elpis_embedding_profile_destroy(p1);
        elpis_embedding_profile_destroy(p2);
    }

    /* Test 4: identity changes with pooling */
    {
        elpis_semantic_embedding_profile_v1 *p1 = elpis_embedding_profile_create();
        elpis_semantic_embedding_profile_v1 *p2 = elpis_embedding_profile_create();
        p1->provider_kind = p2->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        p1->pooling_policy = EMBEDDING_POOLING_MEAN;
        p2->pooling_policy = EMBEDDING_POOLING_CLS;
        p1->normalization_policy = p2->normalization_policy = EMBEDDING_NORMALIZATION_UNIT_L2;
        p1->distance_metric = p2->distance_metric = EMBEDDING_METRIC_COSINE;
        p1->dimensions = p2->dimensions = 768;
        p1->vector_dtype = p2->vector_dtype = EMBEDDING_DTYPE_FLOAT32;

        hacf_digest d1, d2;
        elpis_embedding_profile_identity(p1, &d1);
        elpis_embedding_profile_identity(p2, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) != 0) passed++;
        else { printf("FAIL: identity should differ with pooling\n"); failed++; }
        elpis_embedding_profile_destroy(p1);
        elpis_embedding_profile_destroy(p2);
    }

    /* Test 5: identity changes with normalization */
    {
        elpis_semantic_embedding_profile_v1 *p1 = elpis_embedding_profile_create();
        elpis_semantic_embedding_profile_v1 *p2 = elpis_embedding_profile_create();
        p1->provider_kind = p2->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        p1->pooling_policy = p2->pooling_policy = EMBEDDING_POOLING_MEAN;
        p1->normalization_policy = EMBEDDING_NORMALIZATION_NONE;
        p2->normalization_policy = EMBEDDING_NORMALIZATION_UNIT_L2;
        p1->distance_metric = p2->distance_metric = EMBEDDING_METRIC_COSINE;
        p1->dimensions = p2->dimensions = 768;
        p1->vector_dtype = p2->vector_dtype = EMBEDDING_DTYPE_FLOAT32;

        hacf_digest d1, d2;
        elpis_embedding_profile_identity(p1, &d1);
        elpis_embedding_profile_identity(p2, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) != 0) passed++;
        else { printf("FAIL: identity should differ with normalization\n"); failed++; }
        elpis_embedding_profile_destroy(p1);
        elpis_embedding_profile_destroy(p2);
    }

    /* Test 6: identity changes with metric */
    {
        elpis_semantic_embedding_profile_v1 *p1 = elpis_embedding_profile_create();
        elpis_semantic_embedding_profile_v1 *p2 = elpis_embedding_profile_create();
        p1->provider_kind = p2->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        p1->pooling_policy = p2->pooling_policy = EMBEDDING_POOLING_MEAN;
        p1->normalization_policy = p2->normalization_policy = EMBEDDING_NORMALIZATION_UNIT_L2;
        p1->distance_metric = EMBEDDING_METRIC_COSINE;
        p2->distance_metric = EMBEDDING_METRIC_INNER_PRODUCT;
        p1->dimensions = p2->dimensions = 768;
        p1->vector_dtype = p2->vector_dtype = EMBEDDING_DTYPE_FLOAT32;

        hacf_digest d1, d2;
        elpis_embedding_profile_identity(p1, &d1);
        elpis_embedding_profile_identity(p2, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) != 0) passed++;
        else { printf("FAIL: identity should differ with metric\n"); failed++; }
        elpis_embedding_profile_destroy(p1);
        elpis_embedding_profile_destroy(p2);
    }

    /* Test 7: identity changes with dimensions */
    {
        elpis_semantic_embedding_profile_v1 *p1 = elpis_embedding_profile_create();
        elpis_semantic_embedding_profile_v1 *p2 = elpis_embedding_profile_create();
        p1->provider_kind = p2->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        p1->pooling_policy = p2->pooling_policy = EMBEDDING_POOLING_MEAN;
        p1->normalization_policy = p2->normalization_policy = EMBEDDING_NORMALIZATION_UNIT_L2;
        p1->distance_metric = p2->distance_metric = EMBEDDING_METRIC_COSINE;
        p1->dimensions = 768;
        p2->dimensions = 1536;
        p1->vector_dtype = p2->vector_dtype = EMBEDDING_DTYPE_FLOAT32;

        hacf_digest d1, d2;
        elpis_embedding_profile_identity(p1, &d1);
        elpis_embedding_profile_identity(p2, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) != 0) passed++;
        else { printf("FAIL: identity should differ with dimensions\n"); failed++; }
        elpis_embedding_profile_destroy(p1);
        elpis_embedding_profile_destroy(p2);
    }

    /* Test 8: identity changes with preprocessing policy */
    {
        elpis_semantic_embedding_profile_v1 *p1 = elpis_embedding_profile_create();
        elpis_semantic_embedding_profile_v1 *p2 = elpis_embedding_profile_create();
        p1->provider_kind = p2->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        set_digest_byte(&p1->preprocessing_policy_digest, 0x11);
        set_digest_byte(&p2->preprocessing_policy_digest, 0x22);
        p1->pooling_policy = p2->pooling_policy = EMBEDDING_POOLING_MEAN;
        p1->normalization_policy = p2->normalization_policy = EMBEDDING_NORMALIZATION_UNIT_L2;
        p1->distance_metric = p2->distance_metric = EMBEDDING_METRIC_COSINE;
        p1->dimensions = p2->dimensions = 768;
        p1->vector_dtype = p2->vector_dtype = EMBEDDING_DTYPE_FLOAT32;

        hacf_digest d1, d2;
        elpis_embedding_profile_identity(p1, &d1);
        elpis_embedding_profile_identity(p2, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) != 0) passed++;
        else { printf("FAIL: identity should differ with preprocessing policy\n"); failed++; }
        elpis_embedding_profile_destroy(p1);
        elpis_embedding_profile_destroy(p2);
    }

    /* Test 9: unknown enum rejected */
    {
        elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
        p->provider_kind = (embedding_provider_kind)99;
        if (elpis_semantic_embedding_profile_validate(p) != 0) passed++;
        else { printf("FAIL: unknown provider kind not rejected\n"); failed++; }
        elpis_embedding_profile_destroy(p);
    }

    /* Test 10: nonzero reserved fields rejected */
    {
        elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
        p->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        p->pooling_policy = EMBEDDING_POOLING_MEAN;
        p->normalization_policy = EMBEDDING_NORMALIZATION_UNIT_L2;
        p->distance_metric = EMBEDDING_METRIC_COSINE;
        p->dimensions = 768;
        p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        p->reserved[0] = 0xFF;
        if (elpis_semantic_embedding_profile_validate(p) != 0) passed++;
        else { printf("FAIL: nonzero reserved not rejected\n"); failed++; }
        elpis_embedding_profile_destroy(p);
    }

    /* Test 11: valid profile passes */
    {
        elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
        p->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        p->pooling_policy = EMBEDDING_POOLING_MEAN;
        p->normalization_policy = EMBEDDING_NORMALIZATION_UNIT_L2;
        p->distance_metric = EMBEDDING_METRIC_COSINE;
        p->dimensions = 768;
        p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        if (elpis_semantic_embedding_profile_validate(p) == 0) passed++;
        else { printf("FAIL: valid profile rejected\n"); failed++; }
        elpis_embedding_profile_destroy(p);
    }

    /* Test 12: dimensions = 0 rejected */
    {
        elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
        p->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        p->pooling_policy = EMBEDDING_POOLING_MEAN;
        p->normalization_policy = EMBEDDING_NORMALIZATION_NONE;
        p->distance_metric = EMBEDDING_METRIC_COSINE;
        p->dimensions = 0;
        p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        if (elpis_semantic_embedding_profile_validate(p) != 0) passed++;
        else { printf("FAIL: zero dimensions not rejected\n"); failed++; }
        elpis_embedding_profile_destroy(p);
    }

    /* Test 13: dimensions > ceiling rejected */
    {
        elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
        p->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        p->pooling_policy = EMBEDDING_POOLING_MEAN;
        p->normalization_policy = EMBEDDING_NORMALIZATION_NONE;
        p->distance_metric = EMBEDDING_METRIC_COSINE;
        p->dimensions = EMBEDDING_DIMENSION_CEILING + 1;
        p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        if (elpis_semantic_embedding_profile_validate(p) != 0) passed++;
        else { printf("FAIL: dimensions > ceiling not rejected\n"); failed++; }
        elpis_embedding_profile_destroy(p);
    }

    /* Test 14: profile cmp and is_same */
    {
        elpis_semantic_embedding_profile_v1 *p1 = elpis_embedding_profile_create();
        elpis_semantic_embedding_profile_v1 *p2 = elpis_embedding_profile_create();
        p1->provider_kind = p2->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        p1->pooling_policy = p2->pooling_policy = EMBEDDING_POOLING_MEAN;
        p1->normalization_policy = p2->normalization_policy = EMBEDDING_NORMALIZATION_UNIT_L2;
        p1->distance_metric = p2->distance_metric = EMBEDDING_METRIC_COSINE;
        p1->dimensions = p2->dimensions = 768;
        p1->vector_dtype = p2->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        hacf_digest d;
        elpis_embedding_profile_identity(p1, &d);
        memcpy(&p1->profile_identity, &d, sizeof(hacf_digest));
        memcpy(&p2->profile_identity, &d, sizeof(hacf_digest));
        if (elpis_embedding_profile_is_same(p1, p2) == 1 && elpis_embedding_profile_cmp(p1, p2) == 0) passed++;
        else { printf("FAIL: same profiles not equal\n"); failed++; }
        elpis_embedding_profile_destroy(p1);
        elpis_embedding_profile_destroy(p2);
    }

    /* Test 15: all provider kinds accepted */
    {
        int all_ok = 1;
        for (int kind = 1; kind <= 4; kind++) {
            elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
            p->provider_kind = (embedding_provider_kind)kind;
            p->pooling_policy = EMBEDDING_POOLING_MEAN;
            p->normalization_policy = EMBEDDING_NORMALIZATION_NONE;
            p->distance_metric = EMBEDDING_METRIC_COSINE;
            p->dimensions = 128;
            p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
            if (elpis_semantic_embedding_profile_validate(p) != 0) all_ok = 0;
            elpis_embedding_profile_destroy(p);
        }
        if (all_ok) passed++;
        else { printf("FAIL: some valid provider kind rejected\n"); failed++; }
    }

    /* Test 16: all pooling policies accepted */
    {
        int all_ok = 1;
        for (int p = 1; p <= 6; p++) {
            elpis_semantic_embedding_profile_v1 *prof = elpis_embedding_profile_create();
            prof->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
            prof->pooling_policy = (embedding_pooling_policy)p;
            prof->normalization_policy = EMBEDDING_NORMALIZATION_NONE;
            prof->distance_metric = EMBEDDING_METRIC_COSINE;
            prof->dimensions = 128;
            prof->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
            if (elpis_semantic_embedding_profile_validate(prof) != 0) all_ok = 0;
            elpis_embedding_profile_destroy(prof);
        }
        if (all_ok) passed++;
        else { printf("FAIL: some valid pooling policy rejected\n"); failed++; }
    }

    printf("Profile tests: %d passed, %d failed\n", passed, failed);
    return failed;
}
