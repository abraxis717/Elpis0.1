/* test_embedding_storage.c — Immutable persistence tests. */
#define _DEFAULT_SOURCE
#include "elpis_semantic/embedding_storage.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include <sys/stat.h>
#include <unistd.h>

static void set_digest(hacf_digest *d, unsigned char v) {
    memset(d, 0, sizeof(*d));
    d->bytes[0] = v;
}

static void set_nonzero_digest(hacf_digest *d) {
    memset(d, 0, sizeof(*d));
    d->bytes[0] = 0xAB;
    d->bytes[31] = 0xCD;
}

static void make_path(char *buf, size_t sz, const char *dir, const char *fname) {
    snprintf(buf, sz, "%s/%s", dir, fname);
}

int main(void) {
    int passed = 0, failed = 0;
    const char *test_dir = "/tmp/elpis_embedding_storage_test";
    char path[512];

    /* Clean test dir */
    snprintf(path, sizeof(path), "rm -rf '%s' && mkdir -p '%s'", test_dir, test_dir);
    system(path);

    /* Test 1: profile round trip */
    {
        elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
        p->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        set_nonzero_digest(&p->model_identity_digest);
        p->pooling_policy = EMBEDDING_POOLING_MEAN;
        p->normalization_policy = EMBEDDING_NORMALIZATION_UNIT_L2;
        p->distance_metric = EMBEDDING_METRIC_COSINE;
        p->dimensions = 768;
        p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        hacf_digest d;
        elpis_embedding_profile_identity(p, &d);
        memcpy(&p->profile_identity, &d, sizeof(hacf_digest));

        make_path(path, sizeof(path), test_dir, "profile.bin");
        int rc = elpis_embedding_write_profile(p, path, NULL);
        if (rc == 0) {
            elpis_semantic_embedding_profile_v1 p2;
            int rc2 = elpis_embedding_read_profile(path, &p2);
            if (rc2 == 0 &&
                memcmp(&p2.profile_identity, &p->profile_identity, sizeof(hacf_digest)) == 0)
                passed++;
            else { printf("FAIL: profile round trip mismatch\n"); failed++; }
        } else {
            printf("FAIL: profile write failed (rc=%d)\n", rc); failed++;
        }
        elpis_embedding_profile_destroy(p);
        make_path(path, sizeof(path), test_dir, "profile.bin");
        unlink(path);
    }

    /* Test 2: collection round trip */
    {
        elpis_semantic_embedding_collection_v1 *c = elpis_embedding_collection_create();
        c->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        set_digest(&c->target_digest, 0xAA);
        hacf_digest p1, v1, r1;
        set_digest(&p1, 0x11);
        set_digest(&v1, 0x33);
        set_digest(&r1, 0x55);
        elpis_embedding_collection_add_profile(c, &p1);
        elpis_embedding_collection_add_vector(c, &v1);
        elpis_embedding_collection_add_reference(c, &r1);
        hacf_digest d;
        elpis_embedding_collection_finalize(c, &d);

        make_path(path, sizeof(path), test_dir, "collection.bin");
        int rc = elpis_embedding_write_collection(c, path, NULL);
        if (rc == 0) {
            elpis_semantic_embedding_collection_v1 c2;
            int rc2 = elpis_embedding_read_collection(path, &c2);
            if (rc2 == 0 &&
                memcmp(&c2.collection_identity, &c->collection_identity, sizeof(hacf_digest)) == 0)
                passed++;
            else { printf("FAIL: collection round trip mismatch\n"); failed++; }
        } else {
            printf("FAIL: collection write failed\n"); failed++;
        }
        elpis_embedding_collection_destroy(c);
        make_path(path, sizeof(path), test_dir, "collection.bin");
        unlink(path);
    }

    /* Test 3: atomic no-replace publication */
    {
        elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
        p->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        set_nonzero_digest(&p->model_identity_digest);
        p->pooling_policy = EMBEDDING_POOLING_MEAN;
        p->normalization_policy = EMBEDDING_NORMALIZATION_NONE;
        p->distance_metric = EMBEDDING_METRIC_COSINE;
        p->dimensions = 128;
        p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        hacf_digest d;
        elpis_embedding_profile_identity(p, &d);
        memcpy(&p->profile_identity, &d, sizeof(hacf_digest));

        make_path(path, sizeof(path), test_dir, "noreplace.bin");
        int rc1 = elpis_embedding_write_profile(p, path, NULL);
        int rc2 = elpis_embedding_write_profile(p, path, NULL);
        if (rc1 == 0 && rc2 != 0) passed++;
        else { printf("FAIL: no-replace not enforced (rc1=%d, rc2=%d)\n", rc1, rc2); failed++; }
        elpis_embedding_profile_destroy(p);
        make_path(path, sizeof(path), test_dir, "noreplace.bin");
        unlink(path);
    }

    /* Test 4: existing destination preserved */
    {
        elpis_semantic_embedding_profile_v1 *p1 = elpis_embedding_profile_create();
        p1->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        set_digest(&p1->model_identity_digest, 0x11);
        p1->pooling_policy = EMBEDDING_POOLING_MEAN;
        p1->normalization_policy = EMBEDDING_NORMALIZATION_NONE;
        p1->distance_metric = EMBEDDING_METRIC_COSINE;
        p1->dimensions = 128;
        p1->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        hacf_digest d1;
        elpis_embedding_profile_identity(p1, &d1);
        memcpy(&p1->profile_identity, &d1, sizeof(hacf_digest));

        make_path(path, sizeof(path), test_dir, "existing.bin");
        elpis_embedding_write_profile(p1, path, NULL);

        elpis_semantic_embedding_profile_v1 *p2 = elpis_embedding_profile_create();
        p2->provider_kind = EMBEDDING_PROVIDER_LOCAL_DETERMINISTIC;
        set_digest(&p2->model_identity_digest, 0x22);
        p2->pooling_policy = EMBEDDING_POOLING_CLS;
        p2->normalization_policy = EMBEDDING_NORMALIZATION_NONE;
        p2->distance_metric = EMBEDDING_METRIC_COSINE;
        p2->dimensions = 256;
        p2->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        hacf_digest d2;
        elpis_embedding_profile_identity(p2, &d2);
        memcpy(&p2->profile_identity, &d2, sizeof(hacf_digest));

        int rc = elpis_embedding_write_profile(p2, path, NULL);

        elpis_semantic_embedding_profile_v1 p_read;
        int rc2 = elpis_embedding_read_profile(path, &p_read);
        if (rc != 0 && rc2 == 0 &&
            memcmp(&p_read.profile_identity, &d1, sizeof(hacf_digest)) == 0)
            passed++;
        else { printf("FAIL: existing destination not preserved\n"); failed++; }
        elpis_embedding_profile_destroy(p1);
        elpis_embedding_profile_destroy(p2);
        make_path(path, sizeof(path), test_dir, "existing.bin");
        unlink(path);
    }

    /* Test 5: corrupt file rejected */
    {
        make_path(path, sizeof(path), test_dir, "corrupt.bin");
        FILE *f = fopen(path, "wb");
        if (f) {
            uint8_t garbage[100];
            for (int i = 0; i < 100; i++) garbage[i] = (uint8_t)(i * 7 + 3);
            fwrite(garbage, 1, 100, f);
            fclose(f);

            elpis_semantic_embedding_profile_v1 p;
            int rc = elpis_embedding_read_profile(path, &p);
            if (rc != 0) passed++;
            else { printf("FAIL: corrupt file not rejected\n"); failed++; }
            unlink(path);
        } else {
            printf("FAIL: could not create corrupt file\n"); failed++;
        }
    }

    /* Test 6: truncated file rejected */
    {
        elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
        p->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        set_nonzero_digest(&p->model_identity_digest);
        p->pooling_policy = EMBEDDING_POOLING_MEAN;
        p->normalization_policy = EMBEDDING_NORMALIZATION_NONE;
        p->distance_metric = EMBEDDING_METRIC_COSINE;
        p->dimensions = 128;
        p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        hacf_digest d;
        elpis_embedding_profile_identity(p, &d);
        memcpy(&p->profile_identity, &d, sizeof(hacf_digest));

        make_path(path, sizeof(path), test_dir, "full.bin");
        elpis_embedding_write_profile(p, path, NULL);

        FILE *f = fopen(path, "r+b");
        if (f) {
            fseek(f, 20, SEEK_SET);
            ftruncate(fileno(f), 20);
            fclose(f);

            elpis_semantic_embedding_profile_v1 p2;
            int rc = elpis_embedding_read_profile(path, &p2);
            if (rc != 0) passed++;
            else { printf("FAIL: truncated file not rejected\n"); failed++; }
            unlink(path);
        }
        elpis_embedding_profile_destroy(p);
    }

    /* Test 7: trailing-byte rejection */
    {
        elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
        p->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        set_nonzero_digest(&p->model_identity_digest);
        p->pooling_policy = EMBEDDING_POOLING_MEAN;
        p->normalization_policy = EMBEDDING_NORMALIZATION_NONE;
        p->distance_metric = EMBEDDING_METRIC_COSINE;
        p->dimensions = 128;
        p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        hacf_digest d;
        elpis_embedding_profile_identity(p, &d);
        memcpy(&p->profile_identity, &d, sizeof(hacf_digest));

        make_path(path, sizeof(path), test_dir, "trailing.bin");
        elpis_embedding_write_profile(p, path, NULL);

        FILE *f = fopen(path, "ab");
        if (f) {
            fwrite("GARBAGE", 1, 7, f);
            fclose(f);

            elpis_semantic_embedding_profile_v1 p2;
            int rc = elpis_embedding_read_profile(path, &p2);
            if (rc != 0) passed++;
            else { printf("FAIL: trailing bytes not rejected\n"); failed++; }
            unlink(path);
        }
        elpis_embedding_profile_destroy(p);
    }

    /* Test 8: file package digest deterministic */
    {
        elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
        p->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        set_nonzero_digest(&p->model_identity_digest);
        p->pooling_policy = EMBEDDING_POOLING_MEAN;
        p->normalization_policy = EMBEDDING_NORMALIZATION_NONE;
        p->distance_metric = EMBEDDING_METRIC_COSINE;
        p->dimensions = 128;
        p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        hacf_digest d;
        elpis_embedding_profile_identity(p, &d);
        memcpy(&p->profile_identity, &d, sizeof(hacf_digest));

        make_path(path, sizeof(path), test_dir, "pkg.bin");
        elpis_embedding_write_profile(p, path, NULL);
        hacf_digest pkg1, pkg2;
        elpis_embedding_file_package_digest(path, &pkg1);
        elpis_embedding_file_package_digest(path, &pkg2);
        if (memcmp(&pkg1, &pkg2, sizeof(hacf_digest)) == 0) passed++;
        else { printf("FAIL: file package digest not deterministic\n"); failed++; }
        unlink(path);
        elpis_embedding_profile_destroy(p);
    }

    /* Test 9: vector round trip */
    {
        elpis_semantic_embedding_profile_v1 *p = elpis_embedding_profile_create();
        p->provider_kind = EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED;
        set_nonzero_digest(&p->model_identity_digest);
        p->pooling_policy = EMBEDDING_POOLING_MEAN;
        p->normalization_policy = EMBEDDING_NORMALIZATION_NONE;
        p->distance_metric = EMBEDDING_METRIC_COSINE;
        p->dimensions = 4;
        p->vector_dtype = EMBEDDING_DTYPE_FLOAT32;
        hacf_digest pd;
        elpis_embedding_profile_identity(p, &pd);
        memcpy(&p->profile_identity, &pd, sizeof(hacf_digest));

        float data[4] = {0.1f, 0.2f, 0.3f, 0.4f};
        elpis_semantic_embedding_vector_v1 vec;
        uint8_t *bytes; uint32_t len;
        elpis_embedding_vector_from_float32(p, data, 4, &vec, &bytes, &len);

        make_path(path, sizeof(path), test_dir, "vec.bin");
        int rc = elpis_embedding_write_vector(&vec, bytes, len, path, NULL);
        if (rc == 0) {
            elpis_semantic_embedding_vector_v1 v2;
            uint8_t *b2; uint32_t l2;
            int rc2 = elpis_embedding_read_vector(path, &v2, &b2, &l2);
            if (rc2 == 0 &&
                memcmp(&v2.vector_identity, &vec.vector_identity, sizeof(hacf_digest)) == 0 &&
                l2 == len && memcmp(b2, bytes, len) == 0)
                passed++;
            else { printf("FAIL: vector round trip mismatch\n"); failed++; }
            if (b2) elpis_embedding_vector_free_bytes(b2);
        } else {
            printf("FAIL: vector write failed\n"); failed++;
        }
        elpis_embedding_vector_free_bytes(bytes);
        elpis_embedding_profile_destroy(p);
        make_path(path, sizeof(path), test_dir, "vec.bin");
        unlink(path);
    }

    /* Cleanup */
    snprintf(path, sizeof(path), "rm -rf '%s'", test_dir);
    system(path);

    printf("Storage tests: %d passed, %d failed\n", passed, failed);
    return failed;
}
