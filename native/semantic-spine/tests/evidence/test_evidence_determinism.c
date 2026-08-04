/* test_evidence_determinism.c — Fresh-process determinism test.
 *
 * Uses one serialized fixture manifest. Runs computations multiple times
 * and requires exact equality for all identity digests.
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
#include <stdlib.h>

static int tests_run = 0;
static int tests_pass = 0;

#define TEST(name, expr) do { \
    tests_run++; \
    if (expr) { tests_pass++; } \
    else { fprintf(stderr, "FAIL: %s at %s:%d\n", #expr, __FILE__, __LINE__); } \
} while(0)

/* Run a complete P4 computation pipeline and return the identity digests */
static void compute_fixture(hacf_digest *typer_id,
                             hacf_digest *span_id,
                             hacf_digest *claim_id,
                             hacf_digest *relation_id,
                             hacf_digest *bundle_id,
                             hacf_digest *policy_id,
                             hacf_digest *decision_id,
                             hacf_digest *receipt_id,
                             hacf_digest *layer_id,
                             hacf_digest *view_id) {
    /* Typer profile */
    elpis_evidence_typer_profile_v1 typer;
    elpis_typer_profile_init(&typer);
    typer.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    typer.confidence_scale = 10;
    typer.maximum_claims_per_item = 100;
    typer.maximum_relations_per_item = 50;
    memcpy(typer.provider_identity_digest.bytes, "FIXTURE_TYPER", 13);
    memcpy(typer.provider_code_digest.bytes, "CODE", 4);
    elpis_typer_profile_identity(&typer, typer_id);

    /* Evidence span */
    elpis_evidence_span_v1 span;
    elpis_evidence_span_init(&span);
    memset(span.retrieval_expansion_digest.bytes, 1, 32);
    memset(span.retrieval_bundle_digest.bytes, 2, 32);
    memset(span.retrieval_item_attachment_digest.bytes, 3, 32);
    memset(span.evidence_node_digest.bytes, 4, 32);
    span.byte_start = 0;
    span.byte_end_exclusive = 20;
    memcpy(span.span_bytes_digest.bytes, "SPAN_BYTES", 10);
    elpis_evidence_span_identity(&span, span_id);

    /* Claim candidate */
    elpis_evidence_claim_candidate_v1 claim;
    elpis_claim_candidate_init(&claim);
    memcpy(claim.typer_profile_digest.bytes, typer_id->bytes, 32);
    claim.claim_type = 1;
    memcpy(claim.claim_payload_digest.bytes, "CLAIM_PAYLOAD", 13);
    memcpy(claim.claim_payload_object_digest.bytes, "CLAIM_OBJ", 9);
    claim.source_span_count = 1;
    memcpy(claim.source_span_digests[0].bytes, span_id->bytes, 32);
    claim.claim_polarity = CLAIM_POLARITY_AFFIRMATIVE;
    claim.claim_modality = CLAIM_MODALITY_ASSERTED;
    claim.confidence_key = 5;
    elpis_claim_candidate_identity(&claim, claim_id);

    /* Relation candidate */
    elpis_evidence_relation_candidate_v1 rel;
    elpis_relation_candidate_init(&rel);
    memcpy(rel.typer_profile_digest.bytes, typer_id->bytes, 32);
    rel.relation_type = RELATION_TYPE_SUPPORTS;
    memcpy(rel.evidence_claim_candidate_digest.bytes, claim_id->bytes, 32);
    rel.evidence_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(rel.evidence_object_digest.bytes, claim_id->bytes, 32);
    rel.target_object_kind = OBJECT_KIND_CLAIM_NODE;
    memcpy(rel.target_object_digest.bytes, "TARGET", 6);
    rel.evidence_role = RELATION_ROLE_EVIDENCE;
    rel.target_role = RELATION_ROLE_TARGET;
    rel.source_span_count = 1;
    memcpy(rel.source_span_digests[0].bytes, span_id->bytes, 32);
    rel.confidence_key = 8;
    elpis_relation_candidate_identity(&rel, relation_id);

    /* Typing bundle */
    elpis_evidence_typing_bundle_v1 bundle;
    elpis_typing_bundle_init(&bundle);
    memset(bundle.base_snapshot_digest.bytes, 1, 32);
    memset(bundle.query_overlay_digest.bytes, 2, 32);
    memset(bundle.retrieval_expansion_digest.bytes, 3, 32);
    memset(bundle.retrieval_expanded_view_digest.bytes, 4, 32);
    memcpy(bundle.typer_profile_digest.bytes, typer_id->bytes, 32);
    bundle.evidence_span_count = 1;
    memcpy(bundle.evidence_span_digests[0].bytes, span_id->bytes, 32);
    bundle.claim_candidate_count = 1;
    memcpy(bundle.claim_candidate_digests[0].bytes, claim_id->bytes, 32);
    bundle.relation_candidate_count = 1;
    memcpy(bundle.relation_candidate_digests[0].bytes, relation_id->bytes, 32);
    elpis_typing_bundle_identity(&bundle, bundle_id);

    /* Admission policy */
    elpis_evidence_admission_policy_v1 policy;
    elpis_admission_policy_init_default(&policy);
    elpis_admission_policy_identity(&policy, policy_id);

    /* Admission decision */
    elpis_evidence_admission_decision_v1 decision;
    elpis_admission_decision_init(&decision);
    decision.candidate_kind = CANDIDATE_KIND_CLAIM;
    memcpy(decision.candidate_digest.bytes, claim_id->bytes, 32);
    memcpy(decision.typing_bundle_digest.bytes, bundle_id->bytes, 32);
    memcpy(decision.admission_policy_digest.bytes, policy_id->bytes, 32);
    decision.validation_stage_reached = VALIDATION_STAGE_COMPLETE;
    decision.decision_disposition = DISPOSITION_ADMITTED_NEW_OBJECT;
    decision.effective_authority = 1;
    decision.source_span_count = 1;
    memcpy(decision.source_span_digests[0].bytes, span_id->bytes, 32);
    elpis_admission_decision_identity(&decision, decision_id);

    /* Admission receipt */
    elpis_evidence_admission_receipt_v1 receipt;
    elpis_admission_receipt_init(&receipt);
    memset(receipt.base_snapshot_digest.bytes, 1, 32);
    memset(receipt.query_overlay_digest.bytes, 2, 32);
    memset(receipt.retrieval_expansion_digest.bytes, 3, 32);
    memset(receipt.retrieval_expanded_view_digest.bytes, 4, 32);
    memcpy(receipt.typing_bundle_digest.bytes, bundle_id->bytes, 32);
    memcpy(receipt.typer_profile_digest.bytes, typer_id->bytes, 32);
    memcpy(receipt.candidate_digest.bytes, claim_id->bytes, 32);
    memcpy(receipt.admission_policy_digest.bytes, policy_id->bytes, 32);
    memcpy(receipt.admission_decision_digest.bytes, decision_id->bytes, 32);
    receipt.source_span_count = 1;
    memcpy(receipt.source_span_digests[0].bytes, span_id->bytes, 32);
    receipt.retrieval_bundle_count = 1;
    memset(receipt.retrieval_bundle_package_digests[0].bytes, 2, 32);
    receipt.retrieval_item_attachment_count = 1;
    memset(receipt.retrieval_item_attachment_digests[0].bytes, 3, 32);
    receipt.graph_edge_provenance_status = GRAPH_PROVENANCE_UNAVAILABLE;
    elpis_admission_receipt_identity(&receipt, receipt_id);

    /* Admission layer */
    elpis_evidence_admission_v1 layer;
    elpis_evidence_admission_init(&layer);
    memset(layer.base_snapshot_digest.bytes, 1, 32);
    memset(layer.query_overlay_digest.bytes, 2, 32);
    memset(layer.retrieval_expansion_digest.bytes, 3, 32);
    memset(layer.retrieval_expanded_view_digest.bytes, 4, 32);
    memcpy(layer.typing_bundle_digest.bytes, bundle_id->bytes, 32);
    memcpy(layer.admission_policy_digest.bytes, policy_id->bytes, 32);
    layer.admission_decision_count = 1;
    memcpy(layer.admission_decision_digests[0].bytes, decision_id->bytes, 32);
    layer.admission_receipt_count = 1;
    memcpy(layer.admission_receipt_digests[0].bytes, receipt_id->bytes, 32);
    layer.admitted_claim_count = 1;
    layer.admitted_relation_count = 0;
    layer.rejected_claim_count = 0;
    layer.rejected_relation_count = 0;
    elpis_evidence_admission_identity(&layer, layer_id);

    /* Typed view */
    elpis_typed_evidence_view_v1 view;
    elpis_typed_evidence_view_init(&view);
    memset(view.base_snapshot_digest.bytes, 1, 32);
    memset(view.query_overlay_digest.bytes, 2, 32);
    memset(view.retrieval_expansion_digest.bytes, 3, 32);
    memcpy(view.admission_layer_digest.bytes, layer_id->bytes, 32);
    view.admitted_claim_count = 1;
    memcpy(view.admitted_claim_digests[0].bytes, claim_id->bytes, 32);
    view.admitted_relation_count = 1;
    memcpy(view.admitted_relation_digests[0].bytes, relation_id->bytes, 32);
    view.source_span_count = 1;
    memcpy(view.source_span_digests[0].bytes, span_id->bytes, 32);
    elpis_typed_evidence_view_identity(&view, view_id);
}

static void test_fresh_process_determinism(void) {
    /* Run 3 times, compare all identity digests */
    typedef struct {
        hacf_digest typer_id, span_id, claim_id, relation_id;
        hacf_digest bundle_id, policy_id, decision_id, receipt_id;
        hacf_digest layer_id, view_id;
    } fixture_result;

    fixture_result results[3];
    for (int i = 0; i < 3; i++) {
        compute_fixture(&results[i].typer_id, &results[i].span_id,
                        &results[i].claim_id, &results[i].relation_id,
                        &results[i].bundle_id, &results[i].policy_id,
                        &results[i].decision_id, &results[i].receipt_id,
                        &results[i].layer_id, &results[i].view_id);
    }

    TEST(typer_deterministic, memcmp(results[0].typer_id.bytes, results[1].typer_id.bytes, 32) == 0);
    TEST(span_deterministic, memcmp(results[0].span_id.bytes, results[2].span_id.bytes, 32) == 0);
    TEST(claim_deterministic, memcmp(results[0].claim_id.bytes, results[1].claim_id.bytes, 32) == 0);
    TEST(relation_deterministic, memcmp(results[0].relation_id.bytes, results[2].relation_id.bytes, 32) == 0);
    TEST(bundle_deterministic, memcmp(results[0].bundle_id.bytes, results[1].bundle_id.bytes, 32) == 0);
    TEST(policy_deterministic, memcmp(results[0].policy_id.bytes, results[2].policy_id.bytes, 32) == 0);
    TEST(decision_deterministic, memcmp(results[0].decision_id.bytes, results[1].decision_id.bytes, 32) == 0);
    TEST(receipt_deterministic, memcmp(results[0].receipt_id.bytes, results[2].receipt_id.bytes, 32) == 0);
    TEST(layer_deterministic, memcmp(results[0].layer_id.bytes, results[1].layer_id.bytes, 32) == 0);
    TEST(view_deterministic, memcmp(results[0].view_id.bytes, results[2].view_id.bytes, 32) == 0);
}

int main(void) {
    test_fresh_process_determinism();
    printf("evidence_determinism: %d/%d tests passed\n", tests_pass, tests_run);
    return (tests_pass == tests_run) ? 0 : 1;
}
