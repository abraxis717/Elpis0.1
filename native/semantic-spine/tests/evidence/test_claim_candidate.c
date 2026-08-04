/* test_claim_candidate.c — Claim candidate tests. */
#include "elpis_semantic/evidence_claim_candidate.h"
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

static void test_candidate_init(void) {
    elpis_evidence_claim_candidate_v1 c;
    elpis_claim_candidate_init(&c);
    TEST(init_abi, c.abi_version == EVIDENCE_CLAIM_CANDIDATE_ABI_VERSION);
    TEST(init_reserved, memcmp(c.reserved, (const uint8_t[48]){0}, sizeof(c.reserved)) == 0);
}

static void test_candidate_identity_deterministic(void) {
    elpis_evidence_claim_candidate_v1 a, b;
    elpis_claim_candidate_init(&a);
    elpis_claim_candidate_init(&b);

    memcpy(a.typer_profile_digest.bytes, "X", 1);
    memcpy(b.typer_profile_digest.bytes, "X", 1);
    a.claim_type = 1; b.claim_type = 1;
    memcpy(a.claim_payload_digest.bytes, "P", 1);
    memcpy(b.claim_payload_digest.bytes, "P", 1);
    memcpy(a.claim_payload_object_digest.bytes, "O", 1);
    memcpy(b.claim_payload_object_digest.bytes, "O", 1);
    a.source_span_count = 1; b.source_span_count = 1;
    memcpy(a.source_span_digests[0].bytes, "S", 1);
    memcpy(b.source_span_digests[0].bytes, "S", 1);
    a.claim_polarity = CLAIM_POLARITY_AFFIRMATIVE;
    b.claim_polarity = CLAIM_POLARITY_AFFIRMATIVE;
    a.claim_modality = CLAIM_MODALITY_ASSERTED;
    b.claim_modality = CLAIM_MODALITY_ASSERTED;
    a.confidence_key = 5; b.confidence_key = 5;

    hacf_digest id_a, id_b;
    elpis_claim_candidate_identity(&a, &id_a);
    elpis_claim_candidate_identity(&b, &id_b);
    TEST(identity_deterministic, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) == 0);
}

static void test_candidate_identity_changes_with_polarity(void) {
    elpis_evidence_claim_candidate_v1 a, b;
    elpis_claim_candidate_init(&a);
    elpis_claim_candidate_init(&b);

    memcpy(a.typer_profile_digest.bytes, "X", 1);
    memcpy(b.typer_profile_digest.bytes, "X", 1);
    a.claim_type = 1; b.claim_type = 1;
    memcpy(a.claim_payload_digest.bytes, "P", 1);
    memcpy(b.claim_payload_digest.bytes, "P", 1);
    memcpy(a.claim_payload_object_digest.bytes, "O", 1);
    memcpy(b.claim_payload_object_digest.bytes, "O", 1);
    a.source_span_count = 1; b.source_span_count = 1;
    memcpy(a.source_span_digests[0].bytes, "S", 1);
    memcpy(b.source_span_digests[0].bytes, "S", 1);
    a.claim_polarity = CLAIM_POLARITY_AFFIRMATIVE;
    b.claim_polarity = CLAIM_POLARITY_NEGATIVE;
    a.claim_modality = CLAIM_MODALITY_ASSERTED;
    b.claim_modality = CLAIM_MODALITY_ASSERTED;
    a.confidence_key = 5; b.confidence_key = 5;

    hacf_digest id_a, id_b;
    elpis_claim_candidate_identity(&a, &id_a);
    elpis_claim_candidate_identity(&b, &id_b);
    TEST(identity_changes_with_polarity, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) != 0);
}

static void test_candidate_identity_changes_with_modality(void) {
    elpis_evidence_claim_candidate_v1 a, b;
    elpis_claim_candidate_init(&a);
    elpis_claim_candidate_init(&b);

    memcpy(a.typer_profile_digest.bytes, "X", 1);
    memcpy(b.typer_profile_digest.bytes, "X", 1);
    a.claim_type = 1; b.claim_type = 1;
    memcpy(a.claim_payload_digest.bytes, "P", 1);
    memcpy(b.claim_payload_digest.bytes, "P", 1);
    memcpy(a.claim_payload_object_digest.bytes, "O", 1);
    memcpy(b.claim_payload_object_digest.bytes, "O", 1);
    a.source_span_count = 1; b.source_span_count = 1;
    memcpy(a.source_span_digests[0].bytes, "S", 1);
    memcpy(b.source_span_digests[0].bytes, "S", 1);
    a.claim_polarity = CLAIM_POLARITY_AFFIRMATIVE;
    b.claim_polarity = CLAIM_POLARITY_AFFIRMATIVE;
    a.claim_modality = CLAIM_MODALITY_ASSERTED;
    b.claim_modality = CLAIM_MODALITY_POSSIBLE;
    a.confidence_key = 5; b.confidence_key = 5;

    hacf_digest id_a, id_b;
    elpis_claim_candidate_identity(&a, &id_a);
    elpis_claim_candidate_identity(&b, &id_b);
    TEST(identity_changes_with_modality, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) != 0);
}

static void test_candidate_identity_changes_with_scope(void) {
    elpis_evidence_claim_candidate_v1 a, b;
    elpis_claim_candidate_init(&a);
    elpis_claim_candidate_init(&b);

    memcpy(a.typer_profile_digest.bytes, "X", 1);
    memcpy(b.typer_profile_digest.bytes, "X", 1);
    a.claim_type = 1; b.claim_type = 1;
    memcpy(a.claim_payload_digest.bytes, "P", 1);
    memcpy(b.claim_payload_digest.bytes, "P", 1);
    memcpy(a.claim_payload_object_digest.bytes, "O", 1);
    memcpy(b.claim_payload_object_digest.bytes, "O", 1);
    a.source_span_count = 1; b.source_span_count = 1;
    memcpy(a.source_span_digests[0].bytes, "S", 1);
    memcpy(b.source_span_digests[0].bytes, "S", 1);
    a.claim_polarity = CLAIM_POLARITY_AFFIRMATIVE;
    b.claim_polarity = CLAIM_POLARITY_AFFIRMATIVE;
    a.claim_modality = CLAIM_MODALITY_ASSERTED;
    b.claim_modality = CLAIM_MODALITY_ASSERTED;
    a.confidence_key = 5; b.confidence_key = 5;

    memset(a.claim_scope_digest.bytes, 1, 32);
    memset(b.claim_scope_digest.bytes, 2, 32);

    hacf_digest id_a, id_b;
    elpis_claim_candidate_identity(&a, &id_a);
    elpis_claim_candidate_identity(&b, &id_b);
    TEST(identity_changes_with_scope, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) != 0);
}

static void test_candidate_identity_changes_with_source_span(void) {
    elpis_evidence_claim_candidate_v1 a, b;
    elpis_claim_candidate_init(&a);
    elpis_claim_candidate_init(&b);

    memcpy(a.typer_profile_digest.bytes, "X", 1);
    memcpy(b.typer_profile_digest.bytes, "X", 1);
    a.claim_type = 1; b.claim_type = 1;
    memcpy(a.claim_payload_digest.bytes, "P", 1);
    memcpy(b.claim_payload_digest.bytes, "P", 1);
    memcpy(a.claim_payload_object_digest.bytes, "O", 1);
    memcpy(b.claim_payload_object_digest.bytes, "O", 1);
    a.source_span_count = 1; b.source_span_count = 1;
    memcpy(a.source_span_digests[0].bytes, "A", 1);
    memcpy(b.source_span_digests[0].bytes, "B", 1);
    a.claim_polarity = CLAIM_POLARITY_AFFIRMATIVE;
    b.claim_polarity = CLAIM_POLARITY_AFFIRMATIVE;
    a.claim_modality = CLAIM_MODALITY_ASSERTED;
    b.claim_modality = CLAIM_MODALITY_ASSERTED;
    a.confidence_key = 5; b.confidence_key = 5;

    hacf_digest id_a, id_b;
    elpis_claim_candidate_identity(&a, &id_a);
    elpis_claim_candidate_identity(&b, &id_b);
    TEST(identity_changes_with_span, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) != 0);
}

static void test_candidate_validate_missing_span(void) {
    elpis_evidence_claim_candidate_v1 c;
    elpis_claim_candidate_init(&c);
    memcpy(c.typer_profile_digest.bytes, "X", 1);
    c.claim_type = 1;
    memcpy(c.claim_payload_digest.bytes, "P", 1);
    memcpy(c.claim_payload_object_digest.bytes, "O", 1);
    c.source_span_count = 0; /* no spans */

    TEST(missing_span_rejected, elpis_claim_candidate_validate(&c) != SEMANTIC_OK);
}

static void test_candidate_validate_unknown_polarity(void) {
    elpis_evidence_claim_candidate_v1 c;
    elpis_claim_candidate_init(&c);
    memcpy(c.typer_profile_digest.bytes, "X", 1);
    c.claim_type = 1;
    memcpy(c.claim_payload_digest.bytes, "P", 1);
    memcpy(c.claim_payload_object_digest.bytes, "O", 1);
    c.source_span_count = 1;
    memcpy(c.source_span_digests[0].bytes, "S", 1);
    c.claim_polarity = CLAIM_POLARITY_UNSPECIFIED;
    c.claim_polarity = 99; /* unknown */

    TEST(unknown_polarity_rejected, elpis_claim_candidate_validate(&c) != SEMANTIC_OK);
}

static void test_candidate_validate_reserved(void) {
    elpis_evidence_claim_candidate_v1 c;
    elpis_claim_candidate_init(&c);
    memcpy(c.typer_profile_digest.bytes, "X", 1);
    c.claim_type = 1;
    memcpy(c.claim_payload_digest.bytes, "P", 1);
    memcpy(c.claim_payload_object_digest.bytes, "O", 1);
    c.source_span_count = 1;
    memcpy(c.source_span_digests[0].bytes, "S", 1);
    c.claim_polarity = CLAIM_POLARITY_UNSPECIFIED;
    c.claim_modality = CLAIM_MODALITY_UNSPECIFIED;

    TEST(clean_valid, elpis_claim_candidate_validate(&c) == SEMANTIC_OK);
    c.reserved[0] = 0xFF;
    TEST(reserved_rejected, elpis_claim_candidate_validate(&c) != SEMANTIC_OK);
}

int main(void) {
    test_candidate_init();
    test_candidate_identity_deterministic();
    test_candidate_identity_changes_with_polarity();
    test_candidate_identity_changes_with_modality();
    test_candidate_identity_changes_with_scope();
    test_candidate_identity_changes_with_source_span();
    test_candidate_validate_missing_span();
    test_candidate_validate_unknown_polarity();
    test_candidate_validate_reserved();

    printf("claim_candidate: %d/%d tests passed\n", tests_pass, tests_run);
    return (tests_pass == tests_run) ? 0 : 1;
}
