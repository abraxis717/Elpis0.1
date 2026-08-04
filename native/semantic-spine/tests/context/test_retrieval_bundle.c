/* test_retrieval_bundle.c — Retrieval requirement bundle ordering, dedup, limits. */
#include "elpis_semantic/retrieval_requirement_bundle.h"
#include "elpis_semantic/identity.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int passed = 0, failed = 0;
#define ASSERT_OK(expr) do { int r = (expr); if (r == SEMANTIC_OK) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #expr); } } while(0)
#define ASSERT_EQ(a, b) do { if ((a) == (b)) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s != %s\n", __FILE__, __LINE__, #a, #b); } } while(0)
#define ASSERT_NEQ(a, b) do { if ((a) != (b)) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s == %s\n", __FILE__, __LINE__, #a, #b); } } while(0)
#define ASSERT_DIGEST_EQ(a, b) do { if (memcmp((a)->bytes, (b)->bytes, HACF_DIGEST_BYTES) == 0) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d digests differ\n", __FILE__, __LINE__); } } while(0)

int main(void) {
    /* Create distinct digests for testing */
    hacf_digest d1, d2, d3;
    memset(&d1, 0x11, sizeof(d1));
    memset(&d2, 0x22, sizeof(d2));
    memset(&d3, 0x33, sizeof(d3));

    /* Test: bundle identity deterministic */
    {
        elpis_semantic_retrieval_requirement_bundle_v1 b;
        elpis_retrieval_bundle_init(&b);
        elpis_retrieval_bundle_add(&b, &d1);
        elpis_retrieval_bundle_add(&b, &d2);
        hacf_digest id1, id2;
        elpis_retrieval_requirement_bundle_identity(&b, &id1);
        elpis_retrieval_requirement_bundle_identity(&b, &id2);
        ASSERT_DIGEST_EQ(&id1, &id2);
    }

    /* Test: exact duplicate retrieval requirements collapse */
    {
        elpis_semantic_retrieval_requirement_bundle_v1 b;
        elpis_retrieval_bundle_init(&b);
        elpis_retrieval_bundle_add(&b, &d1);
        int ret = elpis_retrieval_bundle_add(&b, &d1);
        ASSERT_EQ(ret, SEMANTIC_E_DUPLICATE);
        ASSERT_EQ(b.retrieval_count, 1);
    }

    /* Test: canonical ordering sorts ascending */
    {
        elpis_semantic_retrieval_requirement_bundle_v1 b;
        elpis_retrieval_bundle_init(&b);
        elpis_retrieval_bundle_add(&b, &d3);
        elpis_retrieval_bundle_add(&b, &d1);
        elpis_retrieval_bundle_add(&b, &d2);
        elpis_retrieval_bundle_canonicalize(&b);
        /* After canonicalize: d1 < d2 < d3 */
        int c1 = memcmp(b.retrieval_requirement_digests[0].bytes,
                        b.retrieval_requirement_digests[1].bytes, HACF_DIGEST_BYTES);
        int c2 = memcmp(b.retrieval_requirement_digests[1].bytes,
                        b.retrieval_requirement_digests[2].bytes, HACF_DIGEST_BYTES);
        ASSERT_EQ(c1 < 0, 1);
        ASSERT_EQ(c2 < 0, 1);
    }

    /* Test: bundle identity independent of insertion order */
    {
        elpis_semantic_retrieval_requirement_bundle_v1 b1, b2;
        elpis_retrieval_bundle_init(&b1); elpis_retrieval_bundle_init(&b2);
        memset(b1.context_deficit_report_digest.bytes, 0xAA, HACF_DIGEST_BYTES);
        memset(b2.context_deficit_report_digest.bytes, 0xAA, HACF_DIGEST_BYTES);
        elpis_retrieval_bundle_add(&b1, &d1); elpis_retrieval_bundle_add(&b1, &d2);
        elpis_retrieval_bundle_add(&b2, &d2); elpis_retrieval_bundle_add(&b2, &d1);
        elpis_retrieval_bundle_canonicalize(&b1);
        elpis_retrieval_bundle_canonicalize(&b2);
        hacf_digest id1, id2;
        elpis_retrieval_requirement_bundle_identity(&b1, &id1);
        elpis_retrieval_requirement_bundle_identity(&b2, &id2);
        ASSERT_DIGEST_EQ(&id1, &id2);
    }

    /* Test: nonzero reserved fields rejected */
    {
        elpis_semantic_retrieval_requirement_bundle_v1 b;
        elpis_retrieval_bundle_init(&b);
        elpis_retrieval_bundle_add(&b, &d1);
        b.reserved[0] = 1;
        ASSERT_EQ(elpis_retrieval_bundle_validate(&b), SEMANTIC_E_RESERVATION);
    }

    /* Test: empty bundle is valid */
    {
        elpis_semantic_retrieval_requirement_bundle_v1 b;
        elpis_retrieval_bundle_init(&b);
        memset(b.context_deficit_report_digest.bytes, 0xAA, HACF_DIGEST_BYTES);
        /* Empty bundle is valid for CONTEXT_SUFFICIENT */
        ASSERT_OK(elpis_retrieval_bundle_validate(&b));
    }

    printf("Retrieval bundle tests: %d passed, %d failed\n", passed, failed);
    return failed > 0 ? 1 : 0;
}
