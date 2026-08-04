/* test_relation_candidate.c — Relation candidate tests. */
#include "elpis_semantic/evidence_relation_candidate.h"
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

static void test_relation_type_allowed(void) {
    TEST(mentions_allowed, elpis_relation_type_is_allowed(RELATION_TYPE_MENTIONS));
    TEST(defines_allowed, elpis_relation_type_is_allowed(RELATION_TYPE_DEFINES));
    TEST(supports_allowed, elpis_relation_type_is_allowed(RELATION_TYPE_SUPPORTS));
    TEST(contradicts_allowed, elpis_relation_type_is_allowed(RELATION_TYPE_CONTRADICTS));
    TEST(qualifies_allowed, elpis_relation_type_is_allowed(RELATION_TYPE_QUALIFIES));
    TEST(limits_scope_allowed, elpis_relation_type_is_allowed(RELATION_TYPE_LIMITS_SCOPE_OF));
    TEST(provides_context_allowed, elpis_relation_type_is_allowed(RELATION_TYPE_PROVIDES_CONTEXT_FOR));
}

static void test_relation_type_not_allowed_p4_v1(void) {
    /* SAME_AS(200), CAUSES(201), REQUIRES(202) should be rejected */
    TEST(same_as_rejected, !elpis_relation_type_is_allowed((evidence_relation_type)200));
    TEST(causes_rejected, !elpis_relation_type_is_allowed((evidence_relation_type)201));
    TEST(requires_rejected, !elpis_relation_type_is_allowed((evidence_relation_type)202));
}

static void test_relation_candidate_mentions_valid(void) {
    elpis_evidence_relation_candidate_v1 c;
    elpis_relation_candidate_init(&c);

    memcpy(c.typer_profile_digest.bytes, "X", 1);
    c.relation_type = RELATION_TYPE_MENTIONS;
    memcpy(c.evidence_claim_candidate_digest.bytes, "E", 1);
    c.evidence_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.evidence_object_digest.bytes, "EV", 2);
    c.target_object_kind = OBJECT_KIND_EXISTING_NODE;
    memcpy(c.target_object_digest.bytes, "T", 1);
    c.evidence_role = RELATION_ROLE_EVIDENCE;
    c.target_role = RELATION_ROLE_TARGET;
    c.source_span_count = 1;
    memcpy(c.source_span_digests[0].bytes, "S", 1);

    TEST(mentions_valid, elpis_relation_candidate_validate(&c) == SEMANTIC_OK);
}

static void test_relation_candidate_supports_valid(void) {
    elpis_evidence_relation_candidate_v1 c;
    elpis_relation_candidate_init(&c);

    memcpy(c.typer_profile_digest.bytes, "X", 1);
    c.relation_type = RELATION_TYPE_SUPPORTS;
    memcpy(c.evidence_claim_candidate_digest.bytes, "E", 1);
    c.evidence_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.evidence_object_digest.bytes, "EV", 2);
    c.target_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.target_object_digest.bytes, "T", 1);
    c.evidence_role = RELATION_ROLE_EVIDENCE;
    c.target_role = RELATION_ROLE_TARGET;
    c.source_span_count = 1;
    memcpy(c.source_span_digests[0].bytes, "S", 1);

    TEST(supports_valid, elpis_relation_candidate_validate(&c) == SEMANTIC_OK);
}

static void test_relation_candidate_contradicts_valid(void) {
    elpis_evidence_relation_candidate_v1 c;
    elpis_relation_candidate_init(&c);

    memcpy(c.typer_profile_digest.bytes, "X", 1);
    c.relation_type = RELATION_TYPE_CONTRADICTS;
    memcpy(c.evidence_claim_candidate_digest.bytes, "E", 1);
    c.evidence_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.evidence_object_digest.bytes, "EV", 2);
    c.target_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.target_object_digest.bytes, "T", 1);
    c.evidence_role = RELATION_ROLE_EVIDENCE;
    c.target_role = RELATION_ROLE_TARGET;
    c.source_span_count = 1;
    memcpy(c.source_span_digests[0].bytes, "S", 1);

    TEST(contradicts_valid, elpis_relation_candidate_validate(&c) == SEMANTIC_OK);
}

static void test_relation_candidate_qualifies_valid(void) {
    elpis_evidence_relation_candidate_v1 c;
    elpis_relation_candidate_init(&c);

    memcpy(c.typer_profile_digest.bytes, "X", 1);
    c.relation_type = RELATION_TYPE_QUALIFIES;
    memcpy(c.evidence_claim_candidate_digest.bytes, "E", 1);
    c.evidence_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.evidence_object_digest.bytes, "EV", 2);
    c.target_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.target_object_digest.bytes, "T", 1);
    c.evidence_role = RELATION_ROLE_EVIDENCE;
    c.target_role = RELATION_ROLE_TARGET;
    c.source_span_count = 1;
    memcpy(c.source_span_digests[0].bytes, "S", 1);

    TEST(qualifies_valid, elpis_relation_candidate_validate(&c) == SEMANTIC_OK);
}

static void test_relation_candidate_limits_scope_valid(void) {
    elpis_evidence_relation_candidate_v1 c;
    elpis_relation_candidate_init(&c);

    memcpy(c.typer_profile_digest.bytes, "X", 1);
    c.relation_type = RELATION_TYPE_LIMITS_SCOPE_OF;
    memcpy(c.evidence_claim_candidate_digest.bytes, "E", 1);
    c.evidence_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.evidence_object_digest.bytes, "EV", 2);
    c.target_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.target_object_digest.bytes, "T", 1);
    c.evidence_role = RELATION_ROLE_EVIDENCE;
    c.target_role = RELATION_ROLE_TARGET;
    c.source_span_count = 1;
    memcpy(c.source_span_digests[0].bytes, "S", 1);

    TEST(limits_scope_valid, elpis_relation_candidate_validate(&c) == SEMANTIC_OK);
}

static void test_relation_candidate_provides_context_valid(void) {
    elpis_evidence_relation_candidate_v1 c;
    elpis_relation_candidate_init(&c);

    memcpy(c.typer_profile_digest.bytes, "X", 1);
    c.relation_type = RELATION_TYPE_PROVIDES_CONTEXT_FOR;
    memcpy(c.evidence_claim_candidate_digest.bytes, "E", 1);
    c.evidence_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.evidence_object_digest.bytes, "EV", 2);
    c.target_object_kind = OBJECT_KIND_EXISTING_NODE;
    memcpy(c.target_object_digest.bytes, "T", 1);
    c.evidence_role = RELATION_ROLE_EVIDENCE;
    c.target_role = RELATION_ROLE_TARGET;
    c.source_span_count = 1;
    memcpy(c.source_span_digests[0].bytes, "S", 1);

    TEST(provides_context_valid, elpis_relation_candidate_validate(&c) == SEMANTIC_OK);
}

static void test_relation_candidate_target_missing(void) {
    elpis_evidence_relation_candidate_v1 c;
    elpis_relation_candidate_init(&c);
    memcpy(c.typer_profile_digest.bytes, "X", 1);
    c.relation_type = RELATION_TYPE_SUPPORTS;
    c.evidence_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.evidence_object_digest.bytes, "EV", 2);
    c.target_object_kind = OBJECT_KIND_NONE; /* missing */
    c.evidence_role = RELATION_ROLE_EVIDENCE;
    c.target_role = RELATION_ROLE_TARGET;

    TEST(target_missing_rejected, elpis_relation_candidate_validate(&c) != SEMANTIC_OK);
}

static void test_relation_candidate_ordinal_collision(void) {
    elpis_evidence_relation_candidate_v1 c;
    elpis_relation_candidate_init(&c);
    memcpy(c.typer_profile_digest.bytes, "X", 1);
    c.relation_type = RELATION_TYPE_SUPPORTS;
    memcpy(c.evidence_claim_candidate_digest.bytes, "E", 1);
    c.evidence_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.evidence_object_digest.bytes, "EV", 2);
    c.target_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.target_object_digest.bytes, "T", 1);
    c.evidence_role = RELATION_ROLE_EVIDENCE;
    c.target_role = RELATION_ROLE_TARGET;
    c.source_span_count = 1;
    memcpy(c.source_span_digests[0].bytes, "S", 1);

    c.additional_participant_count = 2;
    c.additional_participants[0].ordinal = 5;
    c.additional_participants[1].ordinal = 5; /* collision */
    c.additional_participants[0].role = RELATION_ROLE_QUALIFIER;
    c.additional_participants[1].role = RELATION_ROLE_QUALIFIER;

    TEST(ordinal_collision_rejected, elpis_relation_candidate_validate(&c) != SEMANTIC_OK);
}

static void test_relation_candidate_source_span_missing(void) {
    elpis_evidence_relation_candidate_v1 c;
    elpis_relation_candidate_init(&c);
    memcpy(c.typer_profile_digest.bytes, "X", 1);
    c.relation_type = RELATION_TYPE_SUPPORTS;
    memcpy(c.evidence_claim_candidate_digest.bytes, "E", 1);
    c.evidence_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.evidence_object_digest.bytes, "EV", 2);
    c.target_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(c.target_object_digest.bytes, "T", 1);
    c.evidence_role = RELATION_ROLE_EVIDENCE;
    c.target_role = RELATION_ROLE_TARGET;
    c.source_span_count = 1;
    memset(c.source_span_digests[0].bytes, 0, 32); /* zero digest */

    TEST(source_span_zero_rejected, elpis_relation_candidate_validate(&c) != SEMANTIC_OK);
}

int main(void) {
    test_relation_type_allowed();
    test_relation_type_not_allowed_p4_v1();
    test_relation_candidate_mentions_valid();
    test_relation_candidate_supports_valid();
    test_relation_candidate_contradicts_valid();
    test_relation_candidate_qualifies_valid();
    test_relation_candidate_limits_scope_valid();
    test_relation_candidate_provides_context_valid();
    test_relation_candidate_target_missing();
    test_relation_candidate_ordinal_collision();
    test_relation_candidate_source_span_missing();

    printf("relation_candidate: %d/%d tests passed\n", tests_pass, tests_run);
    return (tests_pass == tests_run) ? 0 : 1;
}
