/* test_admission_policy.c — Admission policy tests. */
#include "elpis_semantic/evidence_admission_policy.h"
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

static void test_policy_default_init(void) {
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);

    TEST(abi_version, policy.abi_version == EVIDENCE_ADMISSION_POLICY_ABI_VERSION);
    TEST(strict_flag, (policy.policy_flags & ADMISSION_POLICY_FLAG_STRICT) != 0);
    TEST(primary_allowed, policy.allow_primary_items == 1);
    TEST(context_allowed, policy.allow_context_items == 1);
    TEST(context_parent_required, policy.context_item_parent_required == 1);
    TEST(min_spans, policy.minimum_distinct_source_spans == 1);
    TEST(min_items, policy.minimum_distinct_retrieval_items == 1);
    TEST(min_docs, policy.minimum_distinct_documents == 1);
    TEST(min_bundles, policy.minimum_distinct_bundles == 1);
    TEST(duplicate_handling, policy.duplicate_handling_policy == DUPLICATE_COLLAPSE);
    TEST(conflict_handling, policy.conflict_handling_policy == CONFLICT_RETAIN_BOTH);
    TEST(unsupported_behavior, policy.unsupported_type_behavior == UNSUPPORTED_REJECT);
    TEST(span_validation_required, policy.require_exact_span_validation == 1);
    TEST(target_resolution_required, policy.require_target_resolution == 1);
}

static void test_policy_identity_deterministic(void) {
    elpis_evidence_admission_policy_v1 a, b;
    elpis_admission_policy_init_default(&a);
    elpis_admission_policy_init_default(&b);

    hacf_digest id_a, id_b;
    elpis_admission_policy_identity(&a, &id_a);
    elpis_admission_policy_identity(&b, &id_b);
    TEST(identity_deterministic, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) == 0);
}

static void test_policy_provider_allowlist(void) {
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);

    /* Empty allowlist = all allowed */
    hacf_digest d;
    memset(d.bytes, 1, 32);
    TEST(empty_allowlist_allows_all, elpis_policy_allows_typer(&policy, &d) == 1);

    policy.allowed_typer_count = 1;
    memset(policy.allowed_typer_profile_digests[0].bytes, 2, 32);
    TEST(allowlist_rejects_unknown, elpis_policy_allows_typer(&policy, &d) == 0);

    memset(d.bytes, 2, 32);
    TEST(allowlist_allows_known, elpis_policy_allows_typer(&policy, &d) == 1);
}

static void test_policy_claim_allowlist(void) {
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);

    TEST(empty_claim_list_allows_all, elpis_policy_allows_claim_type(&policy, 999) == 1);

    policy.allowed_claim_type_count = 2;
    policy.allowed_claim_type_ids[0] = 1;
    policy.allowed_claim_type_ids[1] = 3;
    TEST(claim_list_allows_1, elpis_policy_allows_claim_type(&policy, 1) == 1);
    TEST(claim_list_rejects_2, elpis_policy_allows_claim_type(&policy, 2) == 0);
    TEST(claim_list_allows_3, elpis_policy_allows_claim_type(&policy, 3) == 1);
}

static void test_policy_relation_allowlist(void) {
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);

    TEST(empty_relation_list_allows_all, elpis_policy_allows_relation_type(&policy, 999) == 1);

    policy.allowed_relation_type_count = 1;
    policy.allowed_relation_type_ids[0] = 102;
    TEST(relation_list_allows_102, elpis_policy_allows_relation_type(&policy, 102) == 1);
    TEST(relation_list_rejects_101, elpis_policy_allows_relation_type(&policy, 101) == 0);
}

static void test_policy_confidence_threshold(void) {
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);

    /* Default has zero threshold, so all confidence passes */
    TEST(zero_threshold_allows_zero, policy.minimum_claim_confidence_key == 0);
}

static void test_policy_source_authority_floor(void) {
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);

    TEST(zero_source_floor, policy.minimum_source_authority == 0);
}

static void test_policy_authority_ceiling(void) {
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);

    TEST(claim_authority_ceiling_advisory, policy.maximum_claim_authority == 1);
    TEST(relation_authority_ceiling_provisional, policy.maximum_relation_authority == 2);
}

static void test_policy_admission_limit(void) {
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);

    TEST(default_no_limit, policy.admission_limit == 0);
    policy.admission_limit = 10;
    TEST(limit_set, policy.admission_limit == 10);
}

static void test_policy_reserved_fields(void) {
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);

    TEST(clean_valid, elpis_admission_policy_validate(&policy) == SEMANTIC_OK);
    policy.reserved[0] = 0xFF;
    TEST(reserved_rejected, elpis_admission_policy_validate(&policy) != SEMANTIC_OK);
}

static void test_policy_flags(void) {
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);

    policy.policy_flags = 0xFF;
    TEST(unknown_flags_rejected, elpis_admission_policy_validate(&policy) != SEMANTIC_OK);
}

int main(void) {
    test_policy_default_init();
    test_policy_identity_deterministic();
    test_policy_provider_allowlist();
    test_policy_claim_allowlist();
    test_policy_relation_allowlist();
    test_policy_confidence_threshold();
    test_policy_source_authority_floor();
    test_policy_authority_ceiling();
    test_policy_admission_limit();
    test_policy_reserved_fields();
    test_policy_flags();

    printf("admission_policy: %d/%d tests passed\n", tests_pass, tests_run);
    return (tests_pass == tests_run) ? 0 : 1;
}
