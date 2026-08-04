/* test_admission_segment.c — Admission segment tests. */
#include "elpis_semantic/evidence_admission.h"
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

static void test_admission_layer_init(void) {
    elpis_evidence_admission_v1 a;
    elpis_evidence_admission_init(&a);
    TEST(init_abi, a.abi_version == EVIDENCE_ADMISSION_ABI_VERSION);
    TEST(init_reserved, memcmp(a.reserved, (const uint8_t[48]){0}, sizeof(a.reserved)) == 0);
}

static void test_admission_layer_counts_consistent(void) {
    elpis_evidence_admission_v1 a;
    elpis_evidence_admission_init(&a);
    memset(a.base_snapshot_digest.bytes, 1, 32);
    memset(a.query_overlay_digest.bytes, 2, 32);
    memset(a.retrieval_expansion_digest.bytes, 3, 32);
    memset(a.typing_bundle_digest.bytes, 4, 32);
    memset(a.admission_policy_digest.bytes, 5, 32);

    a.admission_decision_count = 10;
    a.admission_receipt_count = 10;
    a.admitted_claim_count = 3;
    a.admitted_relation_count = 2;
    a.rejected_claim_count = 4;
    a.rejected_relation_count = 1;

    TEST(counts_consistent, elpis_evidence_admission_validate(&a) == SEMANTIC_OK);

    a.rejected_relation_count = 0; /* 3+2+4+0 = 9 != 10 */
    TEST(counts_inconsistent, elpis_evidence_admission_validate(&a) != SEMANTIC_OK);
}

static void test_admission_layer_decision_receipt_match(void) {
    elpis_evidence_admission_v1 a;
    elpis_evidence_admission_init(&a);
    memset(a.base_snapshot_digest.bytes, 1, 32);
    memset(a.query_overlay_digest.bytes, 2, 32);
    memset(a.retrieval_expansion_digest.bytes, 3, 32);
    memset(a.typing_bundle_digest.bytes, 4, 32);
    memset(a.admission_policy_digest.bytes, 5, 32);

    a.admission_decision_count = 5;
    a.admission_receipt_count = 3; /* mismatch */

    TEST(decision_receipt_mismatch, elpis_evidence_admission_validate(&a) != SEMANTIC_OK);
}

static void test_admission_layer_identity_deterministic(void) {
    elpis_evidence_admission_v1 a, b;
    elpis_evidence_admission_init(&a);
    elpis_evidence_admission_init(&b);

    memset(a.base_snapshot_digest.bytes, 1, 32);
    memset(b.base_snapshot_digest.bytes, 1, 32);
    memset(a.query_overlay_digest.bytes, 2, 32);
    memset(b.query_overlay_digest.bytes, 2, 32);
    memset(a.retrieval_expansion_digest.bytes, 3, 32);
    memset(b.retrieval_expansion_digest.bytes, 3, 32);
    memset(a.retrieval_expanded_view_digest.bytes, 4, 32);
    memset(b.retrieval_expanded_view_digest.bytes, 4, 32);
    memset(a.typing_bundle_digest.bytes, 5, 32);
    memset(b.typing_bundle_digest.bytes, 5, 32);
    memset(a.admission_policy_digest.bytes, 6, 32);
    memset(b.admission_policy_digest.bytes, 6, 32);

    hacf_digest id_a, id_b;
    elpis_evidence_admission_identity(&a, &id_a);
    elpis_evidence_admission_identity(&b, &id_b);
    TEST(identity_deterministic, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) == 0);
}

int main(void) {
    test_admission_layer_init();
    test_admission_layer_counts_consistent();
    test_admission_layer_decision_receipt_match();
    test_admission_layer_identity_deterministic();

    printf("admission_segment: %d/%d tests passed\n", tests_pass, tests_run);
    return (tests_pass == tests_run) ? 0 : 1;
}
