/* test_embedding_collection.c — Embedding-reference collection tests. */
#include "elpis_semantic/embedding_collection.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>

static void set_digest(hacf_digest *d, unsigned char v) {
    memset(d, 0, sizeof(*d));
    d->bytes[0] = v;
}

int main(void) {
    int passed = 0, failed = 0;

    /* Test 1: collection identity independent of insertion order */
    {
        elpis_semantic_embedding_collection_v1 *c1 = elpis_embedding_collection_create();
        elpis_semantic_embedding_collection_v1 *c2 = elpis_embedding_collection_create();
        c1->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        set_digest(&c1->target_digest, 0xAA);
        c2->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        memcpy(&c2->target_digest, &c1->target_digest, sizeof(hacf_digest));

        /* Add digests in different order */
        hacf_digest p1, p2, v1, v2, r1, r2;
        set_digest(&p1, 0x11);
        set_digest(&p2, 0x22);
        set_digest(&v1, 0x33);
        set_digest(&v2, 0x44);
        set_digest(&r1, 0x55);
        set_digest(&r2, 0x66);

        elpis_embedding_collection_add_profile(c1, &p1);
        elpis_embedding_collection_add_profile(c1, &p2);
        elpis_embedding_collection_add_vector(c1, &v1);
        elpis_embedding_collection_add_vector(c1, &v2);
        elpis_embedding_collection_add_reference(c1, &r1);
        elpis_embedding_collection_add_reference(c1, &r2);

        elpis_embedding_collection_add_profile(c2, &p2);
        elpis_embedding_collection_add_profile(c2, &p1);
        elpis_embedding_collection_add_vector(c2, &v2);
        elpis_embedding_collection_add_vector(c2, &v1);
        elpis_embedding_collection_add_reference(c2, &r2);
        elpis_embedding_collection_add_reference(c2, &r1);

        hacf_digest d1, d2;
        elpis_embedding_collection_finalize(c1, &d1);
        elpis_embedding_collection_finalize(c2, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) == 0) passed++;
        else { printf("FAIL: collection identity depends on insertion order\n"); failed++; }
        elpis_embedding_collection_destroy(c1);
        elpis_embedding_collection_destroy(c2);
    }

    /* Test 2: collection target binds exact snapshot */
    {
        elpis_semantic_embedding_collection_v1 *c1 = elpis_embedding_collection_create();
        elpis_semantic_embedding_collection_v1 *c2 = elpis_embedding_collection_create();
        c1->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        set_digest(&c1->target_digest, 0xAA);
        c2->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        set_digest(&c2->target_digest, 0xBB);

        hacf_digest d1, d2;
        elpis_embedding_collection_finalize(c1, &d1);
        elpis_embedding_collection_finalize(c2, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) != 0) passed++;
        else { printf("FAIL: identity should differ with target digest\n"); failed++; }
        elpis_embedding_collection_destroy(c1);
        elpis_embedding_collection_destroy(c2);
    }

    /* Test 3: collection target binds exact overlay */
    {
        elpis_semantic_embedding_collection_v1 *c = elpis_embedding_collection_create();
        c->target_kind = EMBEDDING_TARGET_QUERY_OVERLAY;
        set_digest(&c->target_digest, 0xCC);

        hacf_digest d;
        int rc = elpis_embedding_collection_finalize(c, &d);
        if (rc == 0) passed++;
        else { printf("FAIL: overlay target finalize failed\n"); failed++; }
        elpis_embedding_collection_destroy(c);
    }

    /* Test 4: collection immutability — adding to finalized changes identity */
    {
        elpis_semantic_embedding_collection_v1 *c = elpis_embedding_collection_create();
        c->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        set_digest(&c->target_digest, 0xAA);

        hacf_digest p1, p2;
        set_digest(&p1, 0x11);
        set_digest(&p2, 0x22);
        elpis_embedding_collection_add_profile(c, &p1);

        hacf_digest d1;
        elpis_embedding_collection_finalize(c, &d1);

        elpis_embedding_collection_add_profile(c, &p2);
        hacf_digest d2;
        elpis_embedding_collection_finalize(c, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) != 0) passed++;
        else { printf("FAIL: adding profile should change identity\n"); failed++; }
        elpis_embedding_collection_destroy(c);
    }

    /* Test 5: duplicate profile silently collapses */
    {
        elpis_semantic_embedding_collection_v1 *c = elpis_embedding_collection_create();
        c->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        set_digest(&c->target_digest, 0xAA);

        hacf_digest p1;
        set_digest(&p1, 0x11);
        elpis_embedding_collection_add_profile(c, &p1);
        elpis_embedding_collection_add_profile(c, &p1);
        if (c->profile_count == 1) passed++;
        else { printf("FAIL: duplicate profile not collapsed (count=%u)\n", c->profile_count); failed++; }
        elpis_embedding_collection_destroy(c);
    }

    /* Test 6: duplicate vector silently collapses */
    {
        elpis_semantic_embedding_collection_v1 *c = elpis_embedding_collection_create();
        c->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        set_digest(&c->target_digest, 0xAA);

        hacf_digest v1;
        set_digest(&v1, 0x33);
        elpis_embedding_collection_add_vector(c, &v1);
        elpis_embedding_collection_add_vector(c, &v1);
        if (c->vector_count == 1) passed++;
        else { printf("FAIL: duplicate vector not collapsed\n"); failed++; }
        elpis_embedding_collection_destroy(c);
    }

    /* Test 7: duplicate reference silently collapses */
    {
        elpis_semantic_embedding_collection_v1 *c = elpis_embedding_collection_create();
        c->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        set_digest(&c->target_digest, 0xAA);

        hacf_digest r1;
        set_digest(&r1, 0x55);
        elpis_embedding_collection_add_reference(c, &r1);
        elpis_embedding_collection_add_reference(c, &r1);
        if (c->reference_count == 1) passed++;
        else { printf("FAIL: duplicate reference not collapsed\n"); failed++; }
        elpis_embedding_collection_destroy(c);
    }

    /* Test 8: corrupt collection rejected — unsorted digests */
    {
        elpis_semantic_embedding_collection_v1 *c = elpis_embedding_collection_create();
        c->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        set_digest(&c->target_digest, 0xAA);

        hacf_digest p1, p2;
        set_digest(&p1, 0x22); /* larger */
        set_digest(&p2, 0x11); /* smaller — inserting out of order */
        /* Manually place in wrong order to test validation */
        memcpy(&c->profile_digests[0], &p1, sizeof(hacf_digest));
        memcpy(&c->profile_digests[1], &p2, sizeof(hacf_digest));
        c->profile_count = 2;

        if (elpis_embedding_collection_validate(c) != 0) passed++;
        else { printf("FAIL: unsorted digests not rejected\n"); failed++; }
        elpis_embedding_collection_destroy(c);
    }

    /* Test 9: collection validation rejects zero target */
    {
        elpis_semantic_embedding_collection_v1 *c = elpis_embedding_collection_create();
        c->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        /* target_digest is all-zero */
        if (elpis_embedding_collection_validate(c) != 0) passed++;
        else { printf("FAIL: zero target digest not rejected\n"); failed++; }
        elpis_embedding_collection_destroy(c);
    }

    /* Test 10: collection cmp works */
    {
        elpis_semantic_embedding_collection_v1 *c1 = elpis_embedding_collection_create();
        elpis_semantic_embedding_collection_v1 *c2 = elpis_embedding_collection_create();
        c1->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        set_digest(&c1->target_digest, 0xAA);
        c2->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        memcpy(&c2->target_digest, &c1->target_digest, sizeof(hacf_digest));

        hacf_digest d;
        elpis_embedding_collection_finalize(c1, &d);
        memcpy(&c1->collection_identity, &d, sizeof(hacf_digest));
        memcpy(&c2->collection_identity, &d, sizeof(hacf_digest));

        if (elpis_embedding_collection_cmp(c1, c2) == 0) passed++;
        else { printf("FAIL: identical collections should compare equal\n"); failed++; }
        elpis_embedding_collection_destroy(c1);
        elpis_embedding_collection_destroy(c2);
    }

    /* Test 11: valid collection passes validation */
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
        if (elpis_embedding_collection_validate(c) == 0) passed++;
        else { printf("FAIL: valid collection rejected\n"); failed++; }
        elpis_embedding_collection_destroy(c);
    }

    /* Test 12: nonzero reserved rejected */
    {
        elpis_semantic_embedding_collection_v1 *c = elpis_embedding_collection_create();
        c->target_kind = EMBEDDING_TARGET_BASE_SNAPSHOT;
        set_digest(&c->target_digest, 0xAA);
        c->reserved[0] = 0xFF;
        if (elpis_embedding_collection_validate(c) != 0) passed++;
        else { printf("FAIL: nonzero reserved not rejected\n"); failed++; }
        elpis_embedding_collection_destroy(c);
    }

    /* Test 13: invalid target kind rejected */
    {
        elpis_semantic_embedding_collection_v1 *c = elpis_embedding_collection_create();
        c->target_kind = (embedding_collection_target_kind)99;
        set_digest(&c->target_digest, 0xAA);
        if (elpis_embedding_collection_validate(c) != 0) passed++;
        else { printf("FAIL: invalid target kind not rejected\n"); failed++; }
        elpis_embedding_collection_destroy(c);
    }

    printf("Collection tests: %d passed, %d failed\n", passed, failed);
    return failed;
}
