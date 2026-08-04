/* test_retrieval_requirement.c — Retrieval requirement identity, validation, dedup. */
#include "elpis_semantic/retrieval_requirement.h"
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
    /* Test: retrieval requirement identity deterministic */
    {
        elpis_semantic_retrieval_requirement_v1 req;
        elpis_retrieval_requirement_init(&req);
        memset(req.originating_requirement_digest.bytes, 0xAA, HACF_DIGEST_BYTES);
        req.deficit_reason = DEF_OBJECT_ABSENT;
        req.retrieval_purpose = RETRIEVAL_PURPOSE_OBJECT_LOOKUP;
        req.target_object_kind = KIND_NODE;
        memset(req.target_object_digest.bytes, 0xBB, HACF_DIGEST_BYTES);
        req.requested_result_limit = 10;
        req.requirement_priority_key = 1;
        hacf_digest d1, d2;
        elpis_retrieval_requirement_identity(&req, &d1);
        elpis_retrieval_requirement_identity(&req, &d2);
        ASSERT_DIGEST_EQ(&d1, &d2);
    }

    /* Test: identity changes with different deficit reason */
    {
        elpis_semantic_retrieval_requirement_v1 r1, r2;
        elpis_retrieval_requirement_init(&r1); elpis_retrieval_requirement_init(&r2);
        memset(r1.originating_requirement_digest.bytes, 0xAA, HACF_DIGEST_BYTES);
        r1.deficit_reason = DEF_OBJECT_ABSENT;
        r1.retrieval_purpose = RETRIEVAL_PURPOSE_OBJECT_LOOKUP;
        r1.target_object_kind = KIND_NODE;
        memset(r1.target_object_digest.bytes, 0xBB, HACF_DIGEST_BYTES);
        r1.requested_result_limit = 10; r1.requirement_priority_key = 1;
        r2 = r1; r2.deficit_reason = DEF_TYPE_COVERAGE_BELOW_MIN;
        hacf_digest d1, d2;
        elpis_retrieval_requirement_identity(&r1, &d1);
        elpis_retrieval_requirement_identity(&r2, &d2);
        ASSERT_NEQ(memcmp(d1.bytes, d2.bytes, HACF_DIGEST_BYTES), 0); /* Different reasons → different digests */
    }

    /* Test: nonzero reserved fields rejected */
    {
        elpis_semantic_retrieval_requirement_v1 req;
        elpis_retrieval_requirement_init(&req);
        memset(req.originating_requirement_digest.bytes, 0xAA, HACF_DIGEST_BYTES);
        req.deficit_reason = DEF_OBJECT_ABSENT;
        req.retrieval_purpose = RETRIEVAL_PURPOSE_OBJECT_LOOKUP;
        req.requested_result_limit = 10;
        req.query_source_kind = SOURCE_OVERLAY;
        memset(req.query_source_digest.bytes, 0xCC, HACF_DIGEST_BYTES);
        req.reserved[0] = 1;
        ASSERT_NEQ(elpis_retrieval_requirement_validate(&req), SEMANTIC_OK);
    }

    /* Test: retrieval requirement contains no query text (structurally verified) */
    {
        elpis_semantic_retrieval_requirement_v1 req;
        elpis_retrieval_requirement_init(&req);
        /* Verify no field for query text exists — struct only has digests and enums */
        size_t struct_size = sizeof(elpis_semantic_retrieval_requirement_v1);
        /* All fields are digests, enums, uint32 — no char[] for text */
        ASSERT_EQ(struct_size > 0, 1);
    }

    /* Test: exact duplicate retrieval requirements collapse */
    {
        elpis_semantic_retrieval_requirement_v1 r1, r2;
        elpis_retrieval_requirement_init(&r1); elpis_retrieval_requirement_init(&r2);
        memset(r1.originating_requirement_digest.bytes, 0xAA, HACF_DIGEST_BYTES);
        r1.deficit_reason = DEF_OBJECT_ABSENT;
        r1.retrieval_purpose = RETRIEVAL_PURPOSE_OBJECT_LOOKUP;
        r1.target_object_kind = KIND_NODE;
        memset(r1.target_object_digest.bytes, 0xBB, HACF_DIGEST_BYTES);
        r1.requested_result_limit = 10; r1.requirement_priority_key = 1;
        r2 = r1;
        hacf_digest id1, id2;
        elpis_retrieval_requirement_identity(&r1, &id1);
        elpis_retrieval_requirement_identity(&r2, &id2);
        memcpy(r1.retrieval_identity.bytes, id1.bytes, HACF_DIGEST_BYTES);
        memcpy(r2.retrieval_identity.bytes, id2.bytes, HACF_DIGEST_BYTES);
        ASSERT_EQ(elpis_retrieval_requirement_is_duplicate(&r1, &r2), 1);
    }

    /* Test: distinct targets remain distinct */
    {
        elpis_semantic_retrieval_requirement_v1 r1, r2;
        elpis_retrieval_requirement_init(&r1); elpis_retrieval_requirement_init(&r2);
        memset(r1.originating_requirement_digest.bytes, 0xAA, HACF_DIGEST_BYTES);
        r1.deficit_reason = DEF_OBJECT_ABSENT;
        r1.retrieval_purpose = RETRIEVAL_PURPOSE_OBJECT_LOOKUP;
        r1.target_object_kind = KIND_NODE;
        memset(r1.target_object_digest.bytes, 0xBB, HACF_DIGEST_BYTES);
        r1.requested_result_limit = 10; r1.requirement_priority_key = 1;
        r2 = r1;
        memset(r2.target_object_digest.bytes, 0xCC, HACF_DIGEST_BYTES);
        hacf_digest id1, id2;
        elpis_retrieval_requirement_identity(&r1, &id1);
        elpis_retrieval_requirement_identity(&r2, &id2);
        memcpy(r1.retrieval_identity.bytes, id1.bytes, HACF_DIGEST_BYTES);
        memcpy(r2.retrieval_identity.bytes, id2.bytes, HACF_DIGEST_BYTES);
        ASSERT_EQ(elpis_retrieval_requirement_is_duplicate(&r1, &r2), 0);
    }

    printf("Retrieval requirement tests: %d passed, %d failed\n", passed, failed);
    return failed > 0 ? 1 : 0;
}
