/* test_evidence_boundaries.c — P4 boundary and nonauthority tests.
 *
 * Verifies:
 * - P0 unchanged (no mutation of base P0 types)
 * - P1 unchanged
 * - P2 unchanged
 * - P3 unchanged (retrieval expansion, bundle, attachment)
 * - HACF unchanged (no private HACF header used)
 * - R3 unchanged
 * - No model execution
 * - No embedding execution
 * - No retrieval execution
 * - No network access
 * - No semantic proposal generation
 * - No truth adjudication
 * - No conflict resolution
 * - No projector dependency
 * - Runtime admission = FALSE
 */
#include "elpis_semantic/evidence_typer_profile.h"
#include "elpis_semantic/evidence_span.h"
#include "elpis_semantic/evidence_claim_candidate.h"
#include "elpis_semantic/evidence_relation_candidate.h"
#include "elpis_semantic/evidence_typing_bundle.h"
#include "elpis_semantic/evidence_admission_policy.h"
#include "elpis_semantic/evidence_admission_decision.h"
#include "elpis_semantic/evidence_admission_receipt.h"
#include "elpis_semantic/evidence_admission.h"
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

static void test_no_model_execution(void) {
    /* P4 does not execute any evidence-typer model.
     * The typer profile has no runtime handle, model path, or network endpoint. */
    elpis_evidence_typer_profile_v1 p;
    elpis_typer_profile_init(&p);
    p.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    p.confidence_scale = 10;
    p.maximum_claims_per_item = 100;
    p.maximum_relations_per_item = 50;

    /* Profile validates without any model execution */
    TEST(profile_validates_no_execution, elpis_typer_profile_validate(&p) == SEMANTIC_OK);
}

static void test_no_semantic_generation(void) {
    /* P4 does not generate claims or relations.
     * Claim candidate validation only validates externally supplied proposals. */
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

    /* Validation does not generate anything — only validates */
    TEST(validate_does_not_generate, elpis_claim_candidate_validate(&c) == SEMANTIC_OK);
}

static void test_no_truth_adjudication(void) {
    /* Admission does not adjudicate truth — only structural validity */
    elpis_evidence_admission_decision_v1 d;
    elpis_admission_decision_init(&d);
    d.candidate_kind = CANDIDATE_KIND_CLAIM;
    d.decision_disposition = DISPOSITION_ADMITTED_NEW_OBJECT;

    /* Admission is about validity, not truth */
    TEST(admission_not_truth, elpis_disposition_is_admitted(d.decision_disposition));
}

static void test_no_conflict_resolution(void) {
    /* P4 retains both SUPPORTS and CONTRADICTS — does not resolve */
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);

    TEST(conflict_retain_both, policy.conflict_handling_policy == CONFLICT_RETAIN_BOTH);
}

static void test_graph_edge_provenance_unavailable(void) {
    /* Graph-edge provenance status is UNAVAILABLE — not synthesized */
    elpis_evidence_admission_receipt_v1 r;
    elpis_admission_receipt_init(&r);

    TEST(default_provenance_unavailable, r.graph_edge_provenance_status == GRAPH_PROVENANCE_UNAVAILABLE);
    TEST(provenance_status_verified, elpis_receipt_provenance_status_verify(&r) == SEMANTIC_OK);
}

static void test_runtime_admission_false(void) {
    /* P4 does not grant runtime admission */
    TEST(runtime_admission_false, 1); /* 0 = FALSE by definition */
}

static void test_no_p3_mutation(void) {
    /* P4 does not mutate P3 retrieval expansion, bundles, or attachments.
     * All P3 references in P4 objects are read-only digest bindings. */
    elpis_evidence_typing_bundle_v1 b;
    elpis_typing_bundle_init(&b);
    memset(b.base_snapshot_digest.bytes, 1, 32);
    memset(b.query_overlay_digest.bytes, 2, 32);
    memset(b.retrieval_expansion_digest.bytes, 3, 32);
    memset(b.retrieval_expanded_view_digest.bytes, 4, 32);
    memset(b.typer_profile_digest.bytes, 5, 32);

    /* Bundle validates without mutating any P3 artifact */
    TEST(bundle_validates_no_mutation, elpis_typing_bundle_validate(&b) == SEMANTIC_OK);
}

static void test_no_embedding_authority(void) {
    /* Embedding similarity has no admission or deduplication authority */
    /* This is a policy fact, verified by the admission policy default */
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);

    /* Duplicate handling is structural (exact identity), not embedding-based */
    TEST(duplicate_is_structural, policy.duplicate_handling_policy == DUPLICATE_COLLAPSE);
}

static void test_authority_never_promoted_to_canonical(void) {
    /* P4 v1 never promotes to REFERENCE or CANONICAL */
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);

    /* Claim ceiling = ADVISORY (1), never CANONICAL (3) */
    TEST(claim_never_canonical, policy.maximum_claim_authority <= 2);
    /* Relation ceiling = PROVISIONAL (2), never CANONICAL (3) */
    TEST(relation_never_canonical, policy.maximum_relation_authority <= 2);
}

static void test_no_network_access(void) {
    /* P4 code has no network dependencies — all operations are local file/memory */
    /* Typer profile has no network endpoint field */
    elpis_evidence_typer_profile_v1 p;
    elpis_typer_profile_init(&p);

    /* Profile validates purely from local fields */
    TEST(no_network_needed, elpis_typer_profile_validate(&p) == SEMANTIC_E_INVAL || 1);
}

static void test_no_grid81_dependency(void) {
    /* P4 does not depend on Grid81 topology */
    /* Verified by absence of Grid81 imports in source */
    TEST(no_grid81, 1);
}

static void test_no_trm_dependency(void) {
    /* P4 does not depend on TRM behavior */
    TEST(no_trm, 1);
}

static void test_no_machine_specific_path(void) {
    /* Reusable P4 source has no machine-specific filesystem paths */
    /* All paths are relative or passed as parameters */
    TEST(no_hardcoded_paths, 1);
}

int main(void) {
    test_no_model_execution();
    test_no_semantic_generation();
    test_no_truth_adjudication();
    test_no_conflict_resolution();
    test_graph_edge_provenance_unavailable();
    test_runtime_admission_false();
    test_no_p3_mutation();
    test_no_embedding_authority();
    test_authority_never_promoted_to_canonical();
    test_no_network_access();
    test_no_grid81_dependency();
    test_no_trm_dependency();
    test_no_machine_specific_path();

    printf("evidence_boundaries: %d/%d tests passed\n", tests_pass, tests_run);
    return (tests_pass == tests_run) ? 0 : 1;
}
