/* test_adjudicator.c — Admission decision tests. */
#include "elpis_semantic/evidence_admission_decision.h"
#include "elpis_semantic/evidence_admission_policy.h"
#include "elpis_semantic/evidence_typing_bundle.h"
#include "elpis_semantic/evidence_claim_candidate.h"
#include "elpis_semantic/evidence_relation_candidate.h"
#include "elpis_semantic/evidence_span.h"
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

/* Forward decl from evidence_candidate_validate.c */
typedef struct evidence_validation_result {
    int   stage_reached;
    int   disposition;
    int   reason;
} evidence_validation_result;

static void test_decision_init(void) {
    elpis_evidence_admission_decision_v1 d;
    elpis_admission_decision_init(&d);
    TEST(init_abi, d.abi_version == EVIDENCE_ADMISSION_DECISION_ABI_VERSION);
    TEST(init_reserved, memcmp(d.reserved, (const uint8_t[48]){0}, sizeof(d.reserved)) == 0);
}

static void test_decision_disposition_is_admitted(void) {
    TEST(new_object_is_admitted, elpis_disposition_is_admitted(DISPOSITION_ADMITTED_NEW_OBJECT));
    TEST(existing_object_is_admitted, elpis_disposition_is_admitted(DISPOSITION_ADMITTED_EXISTING_OBJECT_NEW_ASSERTION));
    TEST(rejected_not_admitted, !elpis_disposition_is_admitted(DISPOSITION_REJECTED_POLICY));
    TEST(blocked_not_admitted, !elpis_disposition_is_admitted(DISPOSITION_BLOCKED_INTERNAL_ERROR));
}

static void test_decision_disposition_is_rejected(void) {
    TEST(rejected_is_rejected, elpis_disposition_is_rejected(DISPOSITION_REJECTED_POLICY));
    TEST(rejected_span_is_rejected, elpis_disposition_is_rejected(DISPOSITION_REJECTED_INVALID_SPAN));
    TEST(admitted_not_rejected, !elpis_disposition_is_rejected(DISPOSITION_ADMITTED_NEW_OBJECT));
    TEST(blocked_not_rejected, !elpis_disposition_is_rejected(DISPOSITION_BLOCKED_INTERNAL_ERROR));
}

static void test_decision_strings(void) {
    TEST(admitted_string, strcmp(elpis_disposition_string(DISPOSITION_ADMITTED_NEW_OBJECT), "ADMITTED_NEW_OBJECT") == 0);
    TEST(rejected_string, strcmp(elpis_disposition_string(DISPOSITION_REJECTED_POLICY), "REJECTED_POLICY") == 0);
    TEST(blocked_string, strcmp(elpis_disposition_string(DISPOSITION_BLOCKED_INTERNAL_ERROR), "BLOCKED_INTERNAL_ERROR") == 0);
}

static void test_decision_identity_deterministic(void) {
    elpis_evidence_admission_decision_v1 a, b;
    elpis_admission_decision_init(&a);
    elpis_admission_decision_init(&b);

    a.candidate_kind = CANDIDATE_KIND_CLAIM;
    b.candidate_kind = CANDIDATE_KIND_CLAIM;
    memcpy(a.candidate_digest.bytes, "C", 1);
    memcpy(b.candidate_digest.bytes, "C", 1);
    memset(a.typing_bundle_digest.bytes, 1, 32);
    memset(b.typing_bundle_digest.bytes, 1, 32);
    memset(a.admission_policy_digest.bytes, 2, 32);
    memset(b.admission_policy_digest.bytes, 2, 32);
    a.validation_stage_reached = VALIDATION_STAGE_COMPLETE;
    b.validation_stage_reached = VALIDATION_STAGE_COMPLETE;
    a.decision_disposition = DISPOSITION_ADMITTED_NEW_OBJECT;
    b.decision_disposition = DISPOSITION_ADMITTED_NEW_OBJECT;

    hacf_digest id_a, id_b;
    elpis_admission_decision_identity(&a, &id_a);
    elpis_admission_decision_identity(&b, &id_b);
    TEST(identity_deterministic, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) == 0);
}

static void test_decision_validate(void) {
    elpis_evidence_admission_decision_v1 d;
    elpis_admission_decision_init(&d);
    d.candidate_kind = CANDIDATE_KIND_CLAIM;
    d.decision_disposition = DISPOSITION_ADMITTED_NEW_OBJECT;

    TEST(valid_decision, elpis_admission_decision_validate(&d) == SEMANTIC_OK);

    d.candidate_kind = 99;
    TEST(unknown_kind_rejected, elpis_admission_decision_validate(&d) != SEMANTIC_OK);

    d.candidate_kind = CANDIDATE_KIND_CLAIM;
    d.decision_disposition = 0;
    TEST(zero_disposition_rejected, elpis_admission_decision_validate(&d) != SEMANTIC_OK);
}

static void test_authority_ceiling_for_relation(void) {
    extern uint32_t elpis_authority_ceiling_for_relation(int type);

    /* MENTIONS = ADVISORY (1) */
    TEST(mentions_advisory, elpis_authority_ceiling_for_relation(RELATION_TYPE_MENTIONS) == 1);
    /* DEFINES = ADVISORY (1) */
    TEST(defines_advisory, elpis_authority_ceiling_for_relation(RELATION_TYPE_DEFINES) == 1);
    /* SUPPORTS = PROVISIONAL (2) */
    TEST(supports_provisional, elpis_authority_ceiling_for_relation(RELATION_TYPE_SUPPORTS) == 2);
    /* CONTRADICTS = PROVISIONAL (2) */
    TEST(contradicts_provisional, elpis_authority_ceiling_for_relation(RELATION_TYPE_CONTRADICTS) == 2);
    /* QUALIFIES = PROVISIONAL (2) */
    TEST(qualifies_provisional, elpis_authority_ceiling_for_relation(RELATION_TYPE_QUALIFIES) == 2);
    /* PROVIDES_CONTEXT_FOR = ADVISORY (1) */
    TEST(context_advisory, elpis_authority_ceiling_for_relation(RELATION_TYPE_PROVIDES_CONTEXT_FOR) == 1);
}

static void test_effective_authority(void) {
    extern uint32_t elpis_compute_effective_authority(uint32_t source, uint32_t policy,
                                                       uint32_t candidate, uint32_t provider);

    /* Source authority controls when lower */
    TEST(source_lower, elpis_compute_effective_authority(1, 2, 0, 0) == 1);
    /* Policy ceiling controls when lower */
    TEST(policy_lower, elpis_compute_effective_authority(3, 1, 0, 0) == 1);
    /* Multiple ceilings */
    TEST(multiple_ceilings, elpis_compute_effective_authority(3, 2, 1, 0) == 1);
    /* Source alone */
    TEST(source_alone, elpis_compute_effective_authority(2, 0, 0, 0) == 2);
}

static void test_internal_error_never_admits(void) {
    TEST(blocked_not_admitted, !elpis_disposition_is_admitted(DISPOSITION_BLOCKED_INTERNAL_ERROR));
    TEST(blocked_not_rejected, !elpis_disposition_is_rejected(DISPOSITION_BLOCKED_INTERNAL_ERROR));
}

int main(void) {
    test_decision_init();
    test_decision_disposition_is_admitted();
    test_decision_disposition_is_rejected();
    test_decision_strings();
    test_decision_identity_deterministic();
    test_decision_validate();
    test_authority_ceiling_for_relation();
    test_effective_authority();
    test_internal_error_never_admits();

    printf("adjudicator: %d/%d tests passed\n", tests_pass, tests_run);
    return (tests_pass == tests_run) ? 0 : 1;
}
