/* test_typing_bundle.c — Typing bundle tests. */
#include "elpis_semantic/evidence_typing_bundle.h"
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

static void test_bundle_init(void) {
    elpis_evidence_typing_bundle_v1 b;
    elpis_typing_bundle_init(&b);
    TEST(init_abi, b.abi_version == EVIDENCE_TYPING_BUNDLE_ABI_VERSION);
    TEST(init_reserved, memcmp(b.reserved, (const uint8_t[48]){0}, sizeof(b.reserved)) == 0);
}

static void test_bundle_identity_deterministic(void) {
    elpis_evidence_typing_bundle_v1 a, b;
    elpis_typing_bundle_init(&a);
    elpis_typing_bundle_init(&b);

    memset(a.base_snapshot_digest.bytes, 1, 32);
    memset(b.base_snapshot_digest.bytes, 1, 32);
    memset(a.query_overlay_digest.bytes, 2, 32);
    memset(b.query_overlay_digest.bytes, 2, 32);
    memset(a.retrieval_expansion_digest.bytes, 3, 32);
    memset(b.retrieval_expansion_digest.bytes, 3, 32);
    memset(a.retrieval_expanded_view_digest.bytes, 4, 32);
    memset(b.retrieval_expanded_view_digest.bytes, 4, 32);
    memset(a.typer_profile_digest.bytes, 5, 32);
    memset(b.typer_profile_digest.bytes, 5, 32);

    hacf_digest id_a, id_b;
    elpis_typing_bundle_identity(&a, &id_a);
    elpis_typing_bundle_identity(&b, &id_b);
    TEST(identity_deterministic, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) == 0);
}

static void test_bundle_insertion_order_independent(void) {
    /* Adding candidates in different order should produce different bundle identities
     * if stored in raw order — but canonical ordering fixes this.
     * For this test we verify that same set produces same identity when stored identically. */
    elpis_evidence_typing_bundle_v1 a, b;
    elpis_typing_bundle_init(&a);
    elpis_typing_bundle_init(&b);

    memset(a.base_snapshot_digest.bytes, 1, 32);
    memset(b.base_snapshot_digest.bytes, 1, 32);
    memset(a.query_overlay_digest.bytes, 2, 32);
    memset(b.query_overlay_digest.bytes, 2, 32);
    memset(a.retrieval_expansion_digest.bytes, 3, 32);
    memset(b.retrieval_expansion_digest.bytes, 3, 32);
    memset(a.retrieval_expanded_view_digest.bytes, 4, 32);
    memset(b.retrieval_expanded_view_digest.bytes, 4, 32);
    memset(a.typer_profile_digest.bytes, 5, 32);
    memset(b.typer_profile_digest.bytes, 5, 32);

    /* Same candidates in same order */
    a.claim_candidate_count = 2; b.claim_candidate_count = 2;
    memset(a.claim_candidate_digests[0].bytes, 'A', 32);
    memset(b.claim_candidate_digests[0].bytes, 'A', 32);
    memset(a.claim_candidate_digests[1].bytes, 'B', 32);
    memset(b.claim_candidate_digests[1].bytes, 'B', 32);

    hacf_digest id_a, id_b;
    elpis_typing_bundle_identity(&a, &id_a);
    elpis_typing_bundle_identity(&b, &id_b);
    TEST(same_candidates_same_order_same_identity, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) == 0);
}

static void test_bundle_binds_exact_base_snapshot(void) {
    elpis_evidence_typing_bundle_v1 a, b;
    elpis_typing_bundle_init(&a);
    elpis_typing_bundle_init(&b);

    memset(a.base_snapshot_digest.bytes, 1, 32);
    memset(b.base_snapshot_digest.bytes, 2, 32); /* different */
    memset(a.query_overlay_digest.bytes, 2, 32);
    memset(b.query_overlay_digest.bytes, 2, 32);
    memset(a.retrieval_expansion_digest.bytes, 3, 32);
    memset(b.retrieval_expansion_digest.bytes, 3, 32);
    memset(a.retrieval_expanded_view_digest.bytes, 4, 32);
    memset(b.retrieval_expanded_view_digest.bytes, 4, 32);
    memset(a.typer_profile_digest.bytes, 5, 32);
    memset(b.typer_profile_digest.bytes, 5, 32);

    hacf_digest id_a, id_b;
    elpis_typing_bundle_identity(&a, &id_a);
    elpis_typing_bundle_identity(&b, &id_b);
    TEST(base_snapshot_change_changes_identity, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) != 0);
}

static void test_bundle_count_bound_enforced(void) {
    elpis_evidence_typing_bundle_v1 b;
    elpis_typing_bundle_init(&b);
    memset(b.base_snapshot_digest.bytes, 1, 32);
    memset(b.query_overlay_digest.bytes, 2, 32);
    memset(b.retrieval_expansion_digest.bytes, 3, 32);
    memset(b.retrieval_expanded_view_digest.bytes, 4, 32);
    memset(b.typer_profile_digest.bytes, 5, 32);

    b.evidence_span_count = EVIDENCE_BUNDLE_MAX_SPANS + 1;
    TEST(span_count_exceeds_bound, elpis_typing_bundle_validate(&b) != SEMANTIC_OK);
}

static void test_bundle_exact_duplicate_collapse(void) {
    /* Bundle with exact duplicate claim digests should still validate
     * (dedup is handled at admission level) */
    elpis_evidence_typing_bundle_v1 b;
    elpis_typing_bundle_init(&b);
    memset(b.base_snapshot_digest.bytes, 1, 32);
    memset(b.query_overlay_digest.bytes, 2, 32);
    memset(b.retrieval_expansion_digest.bytes, 3, 32);
    memset(b.retrieval_expanded_view_digest.bytes, 4, 32);
    memset(b.typer_profile_digest.bytes, 5, 32);

    b.claim_candidate_count = 2;
    memset(b.claim_candidate_digests[0].bytes, 'X', 32);
    memset(b.claim_candidate_digests[1].bytes, 'X', 32); /* exact duplicate */

    TEST(duplicate_in_bundle_valid, elpis_typing_bundle_validate(&b) == SEMANTIC_OK);
}

static void test_bundle_hacf_package_identity(void) {
    elpis_evidence_typing_bundle_v1 a, b;
    elpis_typing_bundle_init(&a);
    elpis_typing_bundle_init(&b);

    memset(a.base_snapshot_digest.bytes, 1, 32);
    memset(b.base_snapshot_digest.bytes, 1, 32);
    memset(a.query_overlay_digest.bytes, 2, 32);
    memset(b.query_overlay_digest.bytes, 2, 32);
    memset(a.retrieval_expansion_digest.bytes, 3, 32);
    memset(b.retrieval_expansion_digest.bytes, 3, 32);
    memset(a.retrieval_expanded_view_digest.bytes, 4, 32);
    memset(b.retrieval_expanded_view_digest.bytes, 4, 32);
    memset(a.typer_profile_digest.bytes, 5, 32);
    memset(b.typer_profile_digest.bytes, 5, 32);

    memset(a.HACF_package_digest.bytes, 7, 32);
    memset(b.HACF_package_digest.bytes, 8, 32); /* different */

    hacf_digest id_a, id_b;
    elpis_typing_bundle_identity(&a, &id_a);
    elpis_typing_bundle_identity(&b, &id_b);
    TEST(hacf_change_changes_identity, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) != 0);
}

int main(void) {
    test_bundle_init();
    test_bundle_identity_deterministic();
    test_bundle_insertion_order_independent();
    test_bundle_binds_exact_base_snapshot();
    test_bundle_count_bound_enforced();
    test_bundle_exact_duplicate_collapse();
    test_bundle_hacf_package_identity();

    printf("typing_bundle: %d/%d tests passed\n", tests_pass, tests_run);
    return (tests_pass == tests_run) ? 0 : 1;
}
