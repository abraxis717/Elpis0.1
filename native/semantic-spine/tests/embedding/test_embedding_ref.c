/* test_embedding_ref.c — Embedding reference identity tests. */
#include "elpis_semantic/embedding_ref.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>

static void set_digest(hacf_digest *d, unsigned char v) {
    memset(d, 0, sizeof(*d));
    d->bytes[0] = v;
}

int main(void) {
    int passed = 0, failed = 0;

    /* Test 1: reference identity changes with vector */
    {
        elpis_semantic_embedding_ref_v1 *r1 = elpis_embedding_ref_create();
        elpis_semantic_embedding_ref_v1 *r2 = elpis_embedding_ref_create();
        set_digest(&r1->semantic_node_digest, 0x10);
        memcpy(&r2->semantic_node_digest, &r1->semantic_node_digest, sizeof(hacf_digest));
        set_digest(&r1->embedding_profile_digest, 0x20);
        memcpy(&r2->embedding_profile_digest, &r1->embedding_profile_digest, sizeof(hacf_digest));
        set_digest(&r1->embedding_vector_digest, 0x30);
        set_digest(&r2->embedding_vector_digest, 0x31);
        r1->authority = r2->authority = 1;
        r1->reference_flags = r2->reference_flags = 0;
        set_digest(&r1->provenance_digest, 0x40);
        memcpy(&r2->provenance_digest, &r1->provenance_digest, sizeof(hacf_digest));

        hacf_digest d1, d2;
        elpis_embedding_ref_identity(r1, &d1);
        elpis_embedding_ref_identity(r2, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) != 0) passed++;
        else { printf("FAIL: ref identity should differ with vector\n"); failed++; }
        elpis_embedding_ref_destroy(r1);
        elpis_embedding_ref_destroy(r2);
    }

    /* Test 2: reference identity changes with profile */
    {
        elpis_semantic_embedding_ref_v1 *r1 = elpis_embedding_ref_create();
        elpis_semantic_embedding_ref_v1 *r2 = elpis_embedding_ref_create();
        set_digest(&r1->semantic_node_digest, 0x10);
        memcpy(&r2->semantic_node_digest, &r1->semantic_node_digest, sizeof(hacf_digest));
        set_digest(&r1->embedding_profile_digest, 0x20);
        set_digest(&r2->embedding_profile_digest, 0x21);
        set_digest(&r1->embedding_vector_digest, 0x30);
        memcpy(&r2->embedding_vector_digest, &r1->embedding_vector_digest, sizeof(hacf_digest));
        r1->authority = r2->authority = 1;
        r1->reference_flags = r2->reference_flags = 0;
        set_digest(&r1->provenance_digest, 0x40);
        memcpy(&r2->provenance_digest, &r1->provenance_digest, sizeof(hacf_digest));

        hacf_digest d1, d2;
        elpis_embedding_ref_identity(r1, &d1);
        elpis_embedding_ref_identity(r2, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) != 0) passed++;
        else { printf("FAIL: ref identity should differ with profile\n"); failed++; }
        elpis_embedding_ref_destroy(r1);
        elpis_embedding_ref_destroy(r2);
    }

    /* Test 3: reference identity changes with provenance */
    {
        elpis_semantic_embedding_ref_v1 *r1 = elpis_embedding_ref_create();
        elpis_semantic_embedding_ref_v1 *r2 = elpis_embedding_ref_create();
        set_digest(&r1->semantic_node_digest, 0x10);
        memcpy(&r2->semantic_node_digest, &r1->semantic_node_digest, sizeof(hacf_digest));
        set_digest(&r1->embedding_profile_digest, 0x20);
        memcpy(&r2->embedding_profile_digest, &r1->embedding_profile_digest, sizeof(hacf_digest));
        set_digest(&r1->embedding_vector_digest, 0x30);
        memcpy(&r2->embedding_vector_digest, &r1->embedding_vector_digest, sizeof(hacf_digest));
        r1->authority = r2->authority = 1;
        r1->reference_flags = r2->reference_flags = 0;
        set_digest(&r1->provenance_digest, 0x40);
        set_digest(&r2->provenance_digest, 0x41);

        hacf_digest d1, d2;
        elpis_embedding_ref_identity(r1, &d1);
        elpis_embedding_ref_identity(r2, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) != 0) passed++;
        else { printf("FAIL: ref identity should differ with provenance\n"); failed++; }
        elpis_embedding_ref_destroy(r1);
        elpis_embedding_ref_destroy(r2);
    }

    /* Test 4: reference identity changes with authority */
    {
        elpis_semantic_embedding_ref_v1 *r1 = elpis_embedding_ref_create();
        elpis_semantic_embedding_ref_v1 *r2 = elpis_embedding_ref_create();
        set_digest(&r1->semantic_node_digest, 0x10);
        memcpy(&r2->semantic_node_digest, &r1->semantic_node_digest, sizeof(hacf_digest));
        set_digest(&r1->embedding_profile_digest, 0x20);
        memcpy(&r2->embedding_profile_digest, &r1->embedding_profile_digest, sizeof(hacf_digest));
        set_digest(&r1->embedding_vector_digest, 0x30);
        memcpy(&r2->embedding_vector_digest, &r1->embedding_vector_digest, sizeof(hacf_digest));
        r1->authority = 1;
        r2->authority = 2;
        r1->reference_flags = r2->reference_flags = 0;
        set_digest(&r1->provenance_digest, 0x40);
        memcpy(&r2->provenance_digest, &r1->provenance_digest, sizeof(hacf_digest));

        hacf_digest d1, d2;
        elpis_embedding_ref_identity(r1, &d1);
        elpis_embedding_ref_identity(r2, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) != 0) passed++;
        else { printf("FAIL: ref identity should differ with authority\n"); failed++; }
        elpis_embedding_ref_destroy(r1);
        elpis_embedding_ref_destroy(r2);
    }

    /* Test 5: exact duplicate collapse */
    {
        elpis_semantic_embedding_ref_v1 *r1 = elpis_embedding_ref_create();
        elpis_semantic_embedding_ref_v1 *r2 = elpis_embedding_ref_create();
        set_digest(&r1->semantic_node_digest, 0x10);
        memcpy(&r2->semantic_node_digest, &r1->semantic_node_digest, sizeof(hacf_digest));
        set_digest(&r1->embedding_profile_digest, 0x20);
        memcpy(&r2->embedding_profile_digest, &r1->embedding_profile_digest, sizeof(hacf_digest));
        set_digest(&r1->embedding_vector_digest, 0x30);
        memcpy(&r2->embedding_vector_digest, &r1->embedding_vector_digest, sizeof(hacf_digest));
        r1->authority = r2->authority = 1;
        r1->reference_flags = r2->reference_flags = 0;
        set_digest(&r1->provenance_digest, 0x40);
        memcpy(&r2->provenance_digest, &r1->provenance_digest, sizeof(hacf_digest));

        hacf_digest d1, d2;
        elpis_embedding_ref_identity(r1, &d1);
        elpis_embedding_ref_identity(r2, &d2);
        memcpy(&r1->ref_identity, &d1, sizeof(hacf_digest));
        memcpy(&r2->ref_identity, &d2, sizeof(hacf_digest));
        if (elpis_embedding_ref_is_duplicate(r1, r2) == 1) passed++;
        else { printf("FAIL: exact duplicates not detected\n"); failed++; }
        elpis_embedding_ref_destroy(r1);
        elpis_embedding_ref_destroy(r2);
    }

    /* Test 6: conflicting duplicate rejection */
    {
        elpis_semantic_embedding_ref_v1 *r1 = elpis_embedding_ref_create();
        elpis_semantic_embedding_ref_v1 *r2 = elpis_embedding_ref_create();
        set_digest(&r1->semantic_node_digest, 0x10);
        memcpy(&r2->semantic_node_digest, &r1->semantic_node_digest, sizeof(hacf_digest));
        set_digest(&r1->embedding_profile_digest, 0x20);
        memcpy(&r2->embedding_profile_digest, &r1->embedding_profile_digest, sizeof(hacf_digest));
        set_digest(&r1->embedding_vector_digest, 0x30);
        set_digest(&r2->embedding_vector_digest, 0x31); /* different vector */
        r1->authority = r2->authority = 1;
        r1->reference_flags = r2->reference_flags = 0;
        set_digest(&r1->provenance_digest, 0x40);
        memcpy(&r2->provenance_digest, &r1->provenance_digest, sizeof(hacf_digest));

        if (elpis_embedding_ref_is_conflict(r1, r2) == 1) passed++;
        else { printf("FAIL: conflict not detected\n"); failed++; }
        elpis_embedding_ref_destroy(r1);
        elpis_embedding_ref_destroy(r2);
    }

    /* Test 7: validation rejects zero node digest */
    {
        elpis_semantic_embedding_ref_v1 *r = elpis_embedding_ref_create();
        /* semantic_node_digest is all-zero */
        set_digest(&r->embedding_profile_digest, 0x20);
        set_digest(&r->embedding_vector_digest, 0x30);
        r->authority = 1;
        if (elpis_embedding_ref_validate(r) != 0) passed++;
        else { printf("FAIL: zero node digest not rejected\n"); failed++; }
        elpis_embedding_ref_destroy(r);
    }

    /* Test 8: validation rejects zero profile digest */
    {
        elpis_semantic_embedding_ref_v1 *r = elpis_embedding_ref_create();
        set_digest(&r->semantic_node_digest, 0x10);
        /* embedding_profile_digest is all-zero */
        set_digest(&r->embedding_vector_digest, 0x30);
        r->authority = 1;
        if (elpis_embedding_ref_validate(r) != 0) passed++;
        else { printf("FAIL: zero profile digest not rejected\n"); failed++; }
        elpis_embedding_ref_destroy(r);
    }

    /* Test 9: validation rejects zero vector digest */
    {
        elpis_semantic_embedding_ref_v1 *r = elpis_embedding_ref_create();
        set_digest(&r->semantic_node_digest, 0x10);
        set_digest(&r->embedding_profile_digest, 0x20);
        /* embedding_vector_digest is all-zero */
        r->authority = 1;
        if (elpis_embedding_ref_validate(r) != 0) passed++;
        else { printf("FAIL: zero vector digest not rejected\n"); failed++; }
        elpis_embedding_ref_destroy(r);
    }

    /* Test 10: validation rejects invalid authority */
    {
        elpis_semantic_embedding_ref_v1 *r = elpis_embedding_ref_create();
        set_digest(&r->semantic_node_digest, 0x10);
        set_digest(&r->embedding_profile_digest, 0x20);
        set_digest(&r->embedding_vector_digest, 0x30);
        r->authority = 99;
        if (elpis_embedding_ref_validate(r) != 0) passed++;
        else { printf("FAIL: authority > 3 not rejected\n"); failed++; }
        elpis_embedding_ref_destroy(r);
    }

    /* Test 11: valid reference passes validation */
    {
        elpis_semantic_embedding_ref_v1 *r = elpis_embedding_ref_create();
        set_digest(&r->semantic_node_digest, 0x10);
        set_digest(&r->embedding_profile_digest, 0x20);
        set_digest(&r->embedding_vector_digest, 0x30);
        r->authority = 2;
        set_digest(&r->provenance_digest, 0x40);
        if (elpis_embedding_ref_validate(r) == 0) passed++;
        else { printf("FAIL: valid reference rejected\n"); failed++; }
        elpis_embedding_ref_destroy(r);
    }

    /* Test 12: identity deterministic */
    {
        elpis_semantic_embedding_ref_v1 *r = elpis_embedding_ref_create();
        set_digest(&r->semantic_node_digest, 0x10);
        set_digest(&r->embedding_profile_digest, 0x20);
        set_digest(&r->embedding_vector_digest, 0x30);
        r->authority = 1;
        set_digest(&r->provenance_digest, 0x40);

        hacf_digest d1, d2;
        elpis_embedding_ref_identity(r, &d1);
        elpis_embedding_ref_identity(r, &d2);
        if (memcmp(&d1, &d2, sizeof(hacf_digest)) == 0) passed++;
        else { printf("FAIL: ref identity not deterministic\n"); failed++; }
        elpis_embedding_ref_destroy(r);
    }

    /* Test 13: nonzero reserved rejected */
    {
        elpis_semantic_embedding_ref_v1 *r = elpis_embedding_ref_create();
        set_digest(&r->semantic_node_digest, 0x10);
        set_digest(&r->embedding_profile_digest, 0x20);
        set_digest(&r->embedding_vector_digest, 0x30);
        r->authority = 1;
        r->reserved[0] = 0xFF;
        if (elpis_embedding_ref_validate(r) != 0) passed++;
        else { printf("FAIL: nonzero reserved not rejected\n"); failed++; }
        elpis_embedding_ref_destroy(r);
    }

    /* Test 14: non-conflict when different node */
    {
        elpis_semantic_embedding_ref_v1 *r1 = elpis_embedding_ref_create();
        elpis_semantic_embedding_ref_v1 *r2 = elpis_embedding_ref_create();
        set_digest(&r1->semantic_node_digest, 0x10);
        set_digest(&r2->semantic_node_digest, 0x11);
        set_digest(&r1->embedding_profile_digest, 0x20);
        memcpy(&r2->embedding_profile_digest, &r1->embedding_profile_digest, sizeof(hacf_digest));
        set_digest(&r1->embedding_vector_digest, 0x30);
        set_digest(&r2->embedding_vector_digest, 0x31);
        r1->authority = r2->authority = 1;
        set_digest(&r1->provenance_digest, 0x40);
        memcpy(&r2->provenance_digest, &r1->provenance_digest, sizeof(hacf_digest));

        if (elpis_embedding_ref_is_conflict(r1, r2) == 0) passed++;
        else { printf("FAIL: different nodes should not conflict\n"); failed++; }
        elpis_embedding_ref_destroy(r1);
        elpis_embedding_ref_destroy(r2);
    }

    printf("Reference tests: %d passed, %d failed\n", passed, failed);
    return failed;
}
