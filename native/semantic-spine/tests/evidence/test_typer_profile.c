/* test_typer_profile.c — Evidence-typer provider profile tests. */
#include "elpis_semantic/evidence_typer_profile.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stdio.h>



#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
#include <assert.h>

static int tests_run = 0;
static int tests_pass = 0;

#define TEST(name, expr) do { \
    tests_run++; \
    if (expr) { tests_pass++; } \
    else { fprintf(stderr, "FAIL: %s at %s:%d\n", #expr, __FILE__, __LINE__); } \
} while(0)

static void test_profile_init(void) {
    elpis_evidence_typer_profile_v1 profile;
    elpis_typer_profile_init(&profile);
    TEST(init_sets_abi_version, profile.abi_version == EVIDENCE_TYPER_PROFILE_ABI_VERSION);
    TEST(init_zeros_reserved, memcmp(profile.reserved, (const uint8_t[48]){0}, sizeof(profile.reserved)) == 0);
    TEST(init_zeros_digests, digest_is_zero(&profile.provider_identity_digest));
}

static void test_profile_identity_deterministic(void) {
    elpis_evidence_typer_profile_v1 a, b;
    elpis_typer_profile_init(&a);
    elpis_typer_profile_init(&b);

    a.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    b.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    a.confidence_scale = 10;
    b.confidence_scale = 10;
    a.maximum_claims_per_item = 100;
    b.maximum_claims_per_item = 100;
    a.maximum_relations_per_item = 50;
    b.maximum_relations_per_item = 50;

    /* Same random seed digest */
    memcpy(a.provider_identity_digest.bytes, "abc", 3);
    memcpy(b.provider_identity_digest.bytes, "abc", 3);

    hacf_digest id_a, id_b;
    TEST(identity_compute_ok, elpis_typer_profile_identity(&a, &id_a) == SEMANTIC_OK);
    TEST(identity_compute_ok_2, elpis_typer_profile_identity(&b, &id_b) == SEMANTIC_OK);
    TEST(identity_deterministic, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) == 0);
}

static void test_profile_identity_changes_with_kind(void) {
    elpis_evidence_typer_profile_v1 a, b;
    elpis_typer_profile_init(&a);
    elpis_typer_profile_init(&b);

    a.provider_kind = TYPER_KIND_DETERMINISTIC_RULE;
    b.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    a.confidence_scale = 10;
    b.confidence_scale = 10;
    a.maximum_claims_per_item = 100;
    b.maximum_claims_per_item = 100;
    a.maximum_relations_per_item = 50;
    b.maximum_relations_per_item = 50;

    memcpy(a.provider_identity_digest.bytes, "abc", 3);
    memcpy(b.provider_identity_digest.bytes, "abc", 3);

    hacf_digest id_a, id_b;
    elpis_typer_profile_identity(&a, &id_a);
    elpis_typer_profile_identity(&b, &id_b);
    TEST(identity_differs_with_kind, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) != 0);
}

static void test_profile_identity_changes_with_config(void) {
    elpis_evidence_typer_profile_v1 a, b;
    elpis_typer_profile_init(&a);
    elpis_typer_profile_init(&b);

    a.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    b.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    a.confidence_scale = 10;
    b.confidence_scale = 20;
    a.maximum_claims_per_item = 100;
    b.maximum_claims_per_item = 100;
    a.maximum_relations_per_item = 50;
    b.maximum_relations_per_item = 50;

    memcpy(a.provider_identity_digest.bytes, "abc", 3);
    memcpy(b.provider_identity_digest.bytes, "abc", 3);

    hacf_digest id_a, id_b;
    elpis_typer_profile_identity(&a, &id_a);
    elpis_typer_profile_identity(&b, &id_b);
    TEST(identity_differs_with_confidence_scale, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) != 0);
}

static void test_profile_identity_changes_with_input_schema(void) {
    elpis_evidence_typer_profile_v1 a, b;
    elpis_typer_profile_init(&a);
    elpis_typer_profile_init(&b);

    a.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    b.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    a.confidence_scale = 10;
    b.confidence_scale = 10;
    a.maximum_claims_per_item = 100;
    b.maximum_claims_per_item = 100;
    a.maximum_relations_per_item = 50;
    b.maximum_relations_per_item = 50;
    memcpy(a.provider_identity_digest.bytes, "abc", 3);
    memcpy(b.provider_identity_digest.bytes, "abc", 3);

    memset(a.input_schema_digest.bytes, 1, 32);
    memset(b.input_schema_digest.bytes, 2, 32);

    hacf_digest id_a, id_b;
    elpis_typer_profile_identity(&a, &id_a);
    elpis_typer_profile_identity(&b, &id_b);
    TEST(identity_differs_with_input_schema, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) != 0);
}

static void test_profile_identity_changes_with_output_schema(void) {
    elpis_evidence_typer_profile_v1 a, b;
    elpis_typer_profile_init(&a);
    elpis_typer_profile_init(&b);

    a.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    b.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    a.confidence_scale = 10;
    b.confidence_scale = 10;
    a.maximum_claims_per_item = 100;
    b.maximum_claims_per_item = 100;
    a.maximum_relations_per_item = 50;
    b.maximum_relations_per_item = 50;
    memcpy(a.provider_identity_digest.bytes, "abc", 3);
    memcpy(b.provider_identity_digest.bytes, "abc", 3);

    memset(a.output_schema_digest.bytes, 1, 32);
    memset(b.output_schema_digest.bytes, 2, 32);

    hacf_digest id_a, id_b;
    elpis_typer_profile_identity(&a, &id_a);
    elpis_typer_profile_identity(&b, &id_b);
    TEST(identity_differs_with_output_schema, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) != 0);
}

static void test_profile_validate_confidence_scale(void) {
    elpis_evidence_typer_profile_v1 profile;
    elpis_typer_profile_init(&profile);
    profile.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    profile.confidence_scale = 0;
    profile.maximum_claims_per_item = 100;
    profile.maximum_relations_per_item = 50;

    TEST(zero_confidence_rejected, elpis_typer_profile_validate(&profile) != SEMANTIC_OK);

    profile.confidence_scale = 1;
    TEST(one_confidence_accepted, elpis_typer_profile_validate(&profile) == SEMANTIC_OK);
}

static void test_profile_validate_provider_limits(void) {
    elpis_evidence_typer_profile_v1 profile;
    elpis_typer_profile_init(&profile);
    profile.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    profile.confidence_scale = 10;
    profile.maximum_claims_per_item = 0;
    profile.maximum_relations_per_item = 50;

    TEST(zero_max_claims_rejected, elpis_typer_profile_validate(&profile) != SEMANTIC_OK);

    profile.maximum_claims_per_item = 100;
    profile.maximum_relations_per_item = 0;
    TEST(zero_max_relations_rejected, elpis_typer_profile_validate(&profile) != SEMANTIC_OK);
}

static void test_profile_validate_unknown_kind(void) {
    elpis_evidence_typer_profile_v1 profile;
    elpis_typer_profile_init(&profile);
    profile.provider_kind = 99;
    profile.confidence_scale = 10;
    profile.maximum_claims_per_item = 100;
    profile.maximum_relations_per_item = 50;

    TEST(unknown_kind_rejected, elpis_typer_profile_validate(&profile) != SEMANTIC_OK);
}

static void test_profile_validate_reserved_fields(void) {
    elpis_evidence_typer_profile_v1 profile;
    elpis_typer_profile_init(&profile);
    profile.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    profile.confidence_scale = 10;
    profile.maximum_claims_per_item = 100;
    profile.maximum_relations_per_item = 50;

    TEST(clean_profile_valid, elpis_typer_profile_validate(&profile) == SEMANTIC_OK);

    profile.reserved[0] = 0xFF;
    TEST(nonzero_reserved_rejected, elpis_typer_profile_validate(&profile) != SEMANTIC_OK);
}

static void test_profile_validate_nonzero_flags(void) {
    elpis_evidence_typer_profile_v1 profile;
    elpis_typer_profile_init(&profile);
    profile.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    profile.confidence_scale = 10;
    profile.maximum_claims_per_item = 100;
    profile.maximum_relations_per_item = 50;

    profile.provider_flags = 0xFF; /* unknown flag bits */
    TEST(unknown_flags_rejected, elpis_typer_profile_validate(&profile) != SEMANTIC_OK);

    profile.provider_flags = TYPER_FLAG_BATCH;
    TEST(known_flags_accepted, elpis_typer_profile_validate(&profile) == SEMANTIC_OK);
}

int main(void) {
    test_profile_init();
    test_profile_identity_deterministic();
    test_profile_identity_changes_with_kind();
    test_profile_identity_changes_with_config();
    test_profile_identity_changes_with_input_schema();
    test_profile_identity_changes_with_output_schema();
    test_profile_validate_confidence_scale();
    test_profile_validate_provider_limits();
    test_profile_validate_unknown_kind();
    test_profile_validate_reserved_fields();
    test_profile_validate_nonzero_flags();

    printf("typer_profile: %d/%d tests passed\n", tests_pass, tests_run);
    return (tests_pass == tests_run) ? 0 : 1;
}
