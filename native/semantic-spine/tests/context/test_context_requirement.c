/* test_context_requirement.c — Tests for context requirement identity and validation. */
#include "elpis_semantic/context_requirement.h"
#include "elpis_semantic/identity.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int passed = 0, failed = 0;
#define ASSERT_OK(expr) do { int r = (expr); if (r == SEMANTIC_OK) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #expr); } } while(0)
#define ASSERT_NEQ(expr, v) do { int r = (expr); if (r == (v)) { failed++; fprintf(stderr, "FAIL %s:%d %s == %d (unexpectedly equal)\n", __FILE__, __LINE__, #expr, v); } else passed++; } while(0)
#define ASSERT_EQ(a, b) do { if ((a) == (b)) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s != %s\n", __FILE__, __LINE__, #a, #b); } } while(0)
#define ASSERT_DIGEST_EQ(a, b) do { if (memcmp((a)->bytes, (b)->bytes, HACF_DIGEST_BYTES) == 0) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d digests differ\n", __FILE__, __LINE__); } } while(0)
#define ASSERT_DIGEST_NEQ(a, b) do { if (memcmp((a)->bytes, (b)->bytes, HACF_DIGEST_BYTES) != 0) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d digests equal\n", __FILE__, __LINE__); } } while(0)

int main(void) {
    /* Test: requirement identity deterministic */
    {
        elpis_semantic_context_requirement_v1 req;
        elpis_context_requirement_init(&req);
        req.requirement_type = TYPE_OBJECT_PRESENT;
        req.requirement_level = MANDATORY;
        req.target_object_kind = KIND_NODE;
        hacf_digest d1, d2;
        elpis_context_requirement_identity(&req, &d1);
        elpis_context_requirement_identity(&req, &d2);
        ASSERT_DIGEST_EQ(&d1, &d2);
    }

    /* Test: identity changes with type */
    {
        elpis_semantic_context_requirement_v1 r1, r2;
        elpis_context_requirement_init(&r1); elpis_context_requirement_init(&r2);
        r1.requirement_type = TYPE_OBJECT_PRESENT; r1.requirement_level = MANDATORY;
        r2.requirement_type = TYPE_TYPE_COVERAGE;  r2.requirement_level = MANDATORY;
        hacf_digest d1, d2;
        elpis_context_requirement_identity(&r1, &d1);
        elpis_context_requirement_identity(&r2, &d2);
        ASSERT_DIGEST_NEQ(&d1, &d2);
    }

    /* Test: identity changes with level */
    {
        elpis_semantic_context_requirement_v1 r1, r2;
        elpis_context_requirement_init(&r1); elpis_context_requirement_init(&r2);
        r1.requirement_type = TYPE_OBJECT_PRESENT; r1.requirement_level = MANDATORY;
        r2.requirement_type = TYPE_OBJECT_PRESENT; r2.requirement_level = PREFERRED;
        hacf_digest d1, d2;
        elpis_context_requirement_identity(&r1, &d1);
        elpis_context_requirement_identity(&r2, &d2);
        ASSERT_DIGEST_NEQ(&d1, &d2);
    }

    /* Test: identity changes with target */
    {
        elpis_semantic_context_requirement_v1 r1, r2;
        elpis_context_requirement_init(&r1); elpis_context_requirement_init(&r2);
        r1.requirement_type = TYPE_OBJECT_PRESENT; r1.requirement_level = MANDATORY;
        r1.target_object_kind = KIND_NODE;
        r2.requirement_type = TYPE_OBJECT_PRESENT; r2.requirement_level = MANDATORY;
        r2.target_object_kind = KIND_HYPEREDGE;
        hacf_digest d1, d2;
        elpis_context_requirement_identity(&r1, &d1);
        elpis_context_requirement_identity(&r2, &d2);
        ASSERT_DIGEST_NEQ(&d1, &d2);
    }

    /* Test: identity changes with threshold (extension bytes) */
    {
        elpis_semantic_context_requirement_v1 r1, r2;
        elpis_context_requirement_init(&r1); elpis_context_requirement_init(&r2);
        r1.requirement_type = TYPE_OBJECT_PRESENT; r1.requirement_level = MANDATORY;
        r2.requirement_type = TYPE_OBJECT_PRESENT; r2.requirement_level = MANDATORY;
        context_object_present_ext ext1, ext2;
        memset(&ext1, 0, sizeof(ext1)); ext1.required_object_kind = 1;
        memset(&ext2, 0, sizeof(ext2)); ext2.required_object_kind = 2;
        r1.extension_size = sizeof(ext1); memcpy(r1.extension_bytes, &ext1, sizeof(ext1));
        r2.extension_size = sizeof(ext2); memcpy(r2.extension_bytes, &ext2, sizeof(ext2));
        hacf_digest d1, d2;
        elpis_context_requirement_identity(&r1, &d1);
        elpis_context_requirement_identity(&r2, &d2);
        ASSERT_DIGEST_NEQ(&d1, &d2);
    }

    /* Test: identity changes with filter */
    {
        elpis_semantic_context_requirement_v1 r1, r2;
        elpis_context_requirement_init(&r1); elpis_context_requirement_init(&r2);
        r1.requirement_type = TYPE_OBJECT_PRESENT; r1.requirement_level = MANDATORY;
        r1.minimum_authority = 10;
        r2.requirement_type = TYPE_OBJECT_PRESENT; r2.requirement_level = MANDATORY;
        r2.minimum_authority = 20;
        hacf_digest d1, d2;
        elpis_context_requirement_identity(&r1, &d1);
        elpis_context_requirement_identity(&r2, &d2);
        ASSERT_DIGEST_NEQ(&d1, &d2);
    }

    /* Test: unknown requirement type rejected */
    {
        elpis_semantic_context_requirement_v1 req;
        elpis_context_requirement_init(&req);
        req.requirement_type = (semantic_requirement_type)99;
        ASSERT_NEQ(elpis_context_requirement_validate(&req), SEMANTIC_OK);
    }

    /* Test: invalid level rejected */
    {
        elpis_semantic_context_requirement_v1 req;
        elpis_context_requirement_init(&req);
        req.requirement_type = TYPE_OBJECT_PRESENT;
        req.requirement_level = (semantic_requirement_level)0;
        ASSERT_NEQ(elpis_context_requirement_validate(&req), SEMANTIC_OK);
    }

    /* Test: nonzero reserved fields rejected */
    {
        elpis_semantic_context_requirement_v1 req;
        elpis_context_requirement_init(&req);
        req.requirement_type = TYPE_OBJECT_PRESENT;
        req.requirement_level = MANDATORY;
        req.reserved[0] = 1;
        ASSERT_NEQ(elpis_context_requirement_validate(&req), SEMANTIC_OK);
    }

    /* Test: valid requirement passes */
    {
        elpis_semantic_context_requirement_v1 req;
        elpis_context_requirement_init(&req);
        req.requirement_type = TYPE_OBJECT_PRESENT;
        req.requirement_level = MANDATORY;
        req.target_object_kind = KIND_NODE;
        ASSERT_OK(elpis_context_requirement_validate(&req));
    }

    /* Test: is_duplicate works */
    {
        elpis_semantic_context_requirement_v1 r1, r2;
        elpis_context_requirement_init(&r1); elpis_context_requirement_init(&r2);
        r1.requirement_type = TYPE_OBJECT_PRESENT; r1.requirement_level = MANDATORY;
        r2 = r1;
        hacf_digest d1, d2;
        elpis_context_requirement_identity(&r1, &d1);
        elpis_context_requirement_identity(&r2, &d2);
        memcpy(r1.requirement_identity.bytes, d1.bytes, HACF_DIGEST_BYTES);
        memcpy(r2.requirement_identity.bytes, d2.bytes, HACF_DIGEST_BYTES);
        ASSERT_EQ(elpis_context_requirement_is_duplicate(&r1, &r2), 1);
    }

    /* Test: is_duplicate returns 0 for different requirements */
    {
        elpis_semantic_context_requirement_v1 r1, r2;
        elpis_context_requirement_init(&r1); elpis_context_requirement_init(&r2);
        r1.requirement_type = TYPE_OBJECT_PRESENT; r1.requirement_level = MANDATORY;
        r2.requirement_type = TYPE_TYPE_COVERAGE; r2.requirement_level = MANDATORY;
        hacf_digest d1, d2;
        elpis_context_requirement_identity(&r1, &d1);
        elpis_context_requirement_identity(&r2, &d2);
        memcpy(r1.requirement_identity.bytes, d1.bytes, HACF_DIGEST_BYTES);
        memcpy(r2.requirement_identity.bytes, d2.bytes, HACF_DIGEST_BYTES);
        ASSERT_EQ(elpis_context_requirement_is_duplicate(&r1, &r2), 0);
    }

    printf("Context requirement tests: %d passed, %d failed\n", passed, failed);
    return failed > 0 ? 1 : 0;
}
