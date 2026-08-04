/* test_context_requirement_set.c — Requirement set identity, duplicate collapse, canonical ordering. */
#include "elpis_semantic/context_requirement_set.h"
#include "elpis_semantic/identity.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int passed = 0, failed = 0;
#define ASSERT_OK(expr) do { int r = (expr); if (r == SEMANTIC_OK) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #expr); } } while(0)
#define ASSERT_EQ(a, b) do { if ((a) == (b)) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s != %s\n", __FILE__, __LINE__, #a, #b); } } while(0)
#define ASSERT_NEQ(a, b) do { if ((a) != (b)) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s == %s\n", __FILE__, __LINE__, #a, #b); } } while(0)
#define ASSERT_DIGEST_EQ(a, b) do { if (memcmp((a)->bytes, (b)->bytes, HACF_DIGEST_BYTES) == 0) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d digests differ\n", __FILE__, __LINE__); } } while(0)
#define ASSERT_DIGEST_NEQ(a, b) do { if (memcmp((a)->bytes, (b)->bytes, HACF_DIGEST_BYTES) != 0) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d digests equal\n", __FILE__, __LINE__); } } while(0)

int main(void) {
    /* Create two distinct requirement digests for testing */
    elpis_semantic_context_requirement_v1 r1, r2;
    elpis_context_requirement_init(&r1); elpis_context_requirement_init(&r2);
    r1.requirement_type = TYPE_OBJECT_PRESENT; r1.requirement_level = MANDATORY;
    r2.requirement_type = TYPE_TYPE_COVERAGE; r2.requirement_level = MANDATORY;
    hacf_digest d1, d2;
    elpis_context_requirement_identity(&r1, &d1);
    elpis_context_requirement_identity(&r2, &d2);

    /* Test: set identity independent of insertion order */
    {
        elpis_semantic_context_requirement_set_v1 s1, s2;
        elpis_context_requirement_set_init(&s1); elpis_context_requirement_set_init(&s2);
        hacf_digest overlay; memset(&overlay, 0xAA, sizeof(overlay));
        memcpy(s1.target_query_overlay_digest.bytes, overlay.bytes, HACF_DIGEST_BYTES);
        memcpy(s2.target_query_overlay_digest.bytes, overlay.bytes, HACF_DIGEST_BYTES);
        elpis_context_requirement_set_add(&s1, &d1);
        elpis_context_requirement_set_add(&s1, &d2);
        elpis_context_requirement_set_add(&s2, &d2);
        elpis_context_requirement_set_add(&s2, &d1);
        elpis_context_requirement_set_canonicalize(&s1);
        elpis_context_requirement_set_canonicalize(&s2);
        hacf_digest id1, id2;
        elpis_context_requirement_set_identity(&s1, &id1);
        elpis_context_requirement_set_identity(&s2, &id2);
        ASSERT_DIGEST_EQ(&id1, &id2);
    }

    /* Test: exact duplicate requirement collapse */
    {
        elpis_semantic_context_requirement_set_v1 s;
        elpis_context_requirement_set_init(&s);
        elpis_context_requirement_set_add(&s, &d1);
        int ret = elpis_context_requirement_set_add(&s, &d1);
        ASSERT_EQ(ret, SEMANTIC_E_DUPLICATE);
        ASSERT_EQ(s.requirement_count, 1);
    }

    /* Test: bounded count enforcement */
    {
        elpis_semantic_context_requirement_set_v1 s;
        elpis_context_requirement_set_init(&s);
        for (uint32_t i = 0; i < CONTEXT_MAX_REQUIREMENTS; i++) {
            hacf_digest fake; memset(&fake, 0, sizeof(fake));
            fake.bytes[0] = (uint8_t)i;
            fake.bytes[1] = (uint8_t)(i >> 8);
            elpis_context_requirement_set_add(&s, &fake);
        }
        ASSERT_EQ(s.requirement_count, CONTEXT_MAX_REQUIREMENTS);
        hacf_digest overflow; memset(&overflow, 0xFF, sizeof(overflow));
        int ret = elpis_context_requirement_set_add(&s, &overflow);
        ASSERT_NEQ(ret, SEMANTIC_OK);
    }

    /* Test: valid set identity */
    {
        elpis_semantic_context_requirement_set_v1 s;
        elpis_context_requirement_set_init(&s);
        elpis_context_requirement_set_add(&s, &d1);
        hacf_digest id1, id2;
        elpis_context_requirement_set_identity(&s, &id1);
        elpis_context_requirement_set_identity(&s, &id2);
        ASSERT_DIGEST_EQ(&id1, &id2);
    }

    /* Test: canonical ordering is ascending */
    {
        elpis_semantic_context_requirement_set_v1 s;
        elpis_context_requirement_set_init(&s);
        /* Add in reverse order */
        elpis_context_requirement_set_add(&s, &d2);
        elpis_context_requirement_set_add(&s, &d1);
        elpis_context_requirement_set_canonicalize(&s);
        /* After canonicalize, digests should be sorted ascending */
        int cmp = memcmp(s.requirement_digests[0].bytes, s.requirement_digests[1].bytes, HACF_DIGEST_BYTES);
        ASSERT_EQ(cmp < 0, 1);
    }

    /* Test: requirement set with different overlays produce different identities */
    {
        elpis_semantic_context_requirement_set_v1 s1, s2;
        elpis_context_requirement_set_init(&s1); elpis_context_requirement_set_init(&s2);
        hacf_digest ov1, ov2;
        memset(&ov1, 0xAA, sizeof(ov1));
        memset(&ov2, 0xBB, sizeof(ov2));
        memcpy(s1.target_query_overlay_digest.bytes, ov1.bytes, HACF_DIGEST_BYTES);
        memcpy(s2.target_query_overlay_digest.bytes, ov2.bytes, HACF_DIGEST_BYTES);
        elpis_context_requirement_set_add(&s1, &d1);
        elpis_context_requirement_set_add(&s2, &d1);
        hacf_digest id1, id2;
        elpis_context_requirement_set_identity(&s1, &id1);
        elpis_context_requirement_set_identity(&s2, &id2);
        ASSERT_DIGEST_NEQ(&id1, &id2);
    }

    printf("Context requirement set tests: %d passed, %d failed\n", passed, failed);
    return failed > 0 ? 1 : 0;
}
