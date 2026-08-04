/* test_typed_evidence_view.c — Typed evidence view tests. */
#include "elpis_semantic/typed_evidence_view.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stdio.h>



#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}

static int tests_run = 0;
static int tests_pass = 0;

#define TEST(name, expr) do { \
    tests_run++; \
    if (expr) { tests_pass++; } \
    else { fprintf(stderr, "FAIL: %s at %s:%d\n", #expr, __FILE__, __LINE__); } \
} while(0)

static void test_view_init(void) {
    elpis_typed_evidence_view_v1 v;
    elpis_typed_evidence_view_init(&v);
    TEST(init_abi, v.abi_version == TYPED_EVIDENCE_VIEW_ABI_VERSION);
    TEST(init_reserved, memcmp(v.reserved, (const uint8_t[48]){0}, sizeof(v.reserved)) == 0);
}

static void test_view_identity_deterministic(void) {
    elpis_typed_evidence_view_v1 a, b;
    elpis_typed_evidence_view_init(&a);
    elpis_typed_evidence_view_init(&b);

    memset(a.base_snapshot_digest.bytes, 1, 32);
    memset(b.base_snapshot_digest.bytes, 1, 32);
    memset(a.query_overlay_digest.bytes, 2, 32);
    memset(b.query_overlay_digest.bytes, 2, 32);
    memset(a.retrieval_expansion_digest.bytes, 3, 32);
    memset(b.retrieval_expansion_digest.bytes, 3, 32);
    memset(a.admission_layer_digest.bytes, 4, 32);
    memset(b.admission_layer_digest.bytes, 4, 32);

    hacf_digest id_a, id_b;
    elpis_typed_evidence_view_identity(&a, &id_a);
    elpis_typed_evidence_view_identity(&b, &id_b);
    TEST(identity_deterministic, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) == 0);
}

static void test_view_claim_lookup(void) {
    elpis_typed_evidence_view_v1 v;
    elpis_typed_evidence_view_init(&v);
    memset(v.base_snapshot_digest.bytes, 1, 32);
    memset(v.query_overlay_digest.bytes, 2, 32);
    memset(v.retrieval_expansion_digest.bytes, 3, 32);
    memset(v.admission_layer_digest.bytes, 4, 32);

    v.admitted_claim_count = 3;
    memset(v.admitted_claim_digests[0].bytes, 'A', 32);
    memset(v.admitted_claim_digests[1].bytes, 'B', 32);
    memset(v.admitted_claim_digests[2].bytes, 'C', 32);

    hacf_digest search;
    uint32_t idx;

    memset(search.bytes, 'A', 32);
    TEST(lookup_A, elpis_typed_view_lookup_claim(&v, &search, &idx) == SEMANTIC_OK);
    TEST(index_A, idx == 0);

    memset(search.bytes, 'C', 32);
    TEST(lookup_C, elpis_typed_view_lookup_claim(&v, &search, &idx) == SEMANTIC_OK);
    TEST(index_C, idx == 2);

    memset(search.bytes, 'Z', 32);
    TEST(lookup_missing, elpis_typed_view_lookup_claim(&v, &search, &idx) == SEMANTIC_E_NOTFOUND);
}

static void test_view_relation_lookup(void) {
    elpis_typed_evidence_view_v1 v;
    elpis_typed_evidence_view_init(&v);
    memset(v.base_snapshot_digest.bytes, 1, 32);
    memset(v.query_overlay_digest.bytes, 2, 32);
    memset(v.retrieval_expansion_digest.bytes, 3, 32);
    memset(v.admission_layer_digest.bytes, 4, 32);

    v.admitted_relation_count = 2;
    memset(v.admitted_relation_digests[0].bytes, 'R', 32);
    memset(v.admitted_relation_digests[1].bytes, 'S', 32);

    hacf_digest search;
    uint32_t idx;

    memset(search.bytes, 'R', 32);
    TEST(lookup_R, elpis_typed_view_lookup_relation(&v, &search, &idx) == SEMANTIC_OK);
    TEST(index_R, idx == 0);

    memset(search.bytes, 'Z', 32);
    TEST(lookup_missing, elpis_typed_view_lookup_relation(&v, &search, &idx) == SEMANTIC_E_NOTFOUND);
}

static void test_view_validate(void) {
    elpis_typed_evidence_view_v1 v;
    elpis_typed_evidence_view_init(&v);
    memset(v.base_snapshot_digest.bytes, 1, 32);
    memset(v.query_overlay_digest.bytes, 2, 32);
    memset(v.retrieval_expansion_digest.bytes, 3, 32);
    memset(v.admission_layer_digest.bytes, 4, 32);

    TEST(valid_view, elpis_typed_evidence_view_validate(&v) == SEMANTIC_OK);

    memset(v.base_snapshot_digest.bytes, 0, 32); /* zero digest */
    TEST(zero_base_snapshot_rejected, elpis_typed_evidence_view_validate(&v) != SEMANTIC_OK);
}

static void test_view_reserved(void) {
    elpis_typed_evidence_view_v1 v;
    elpis_typed_evidence_view_init(&v);
    memset(v.base_snapshot_digest.bytes, 1, 32);
    memset(v.query_overlay_digest.bytes, 2, 32);
    memset(v.retrieval_expansion_digest.bytes, 3, 32);
    memset(v.admission_layer_digest.bytes, 4, 32);

    v.reserved[0] = 0xFF;
    TEST(reserved_rejected, elpis_typed_evidence_view_validate(&v) != SEMANTIC_OK);
}

int main(void) {
    test_view_init();
    test_view_identity_deterministic();
    test_view_claim_lookup();
    test_view_relation_lookup();
    test_view_validate();
    test_view_reserved();

    printf("typed_evidence_view: %d/%d tests passed\n", tests_pass, tests_run);
    return (tests_pass == tests_run) ? 0 : 1;
}
