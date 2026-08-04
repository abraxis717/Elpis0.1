#define _POSIX_C_SOURCE 200809L
/* test_evidence_persistence.c — Persistence roundtrip tests. */
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
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>

static int tests_run = 0;
static int tests_pass = 0;

#define TEST(name, expr) do { \
    tests_run++; \
    if (expr) { tests_pass++; } \
    else { fprintf(stderr, "FAIL: %s at %s:%d\n", #expr, __FILE__, __LINE__); } \
} while(0)

/* Forward decls from evidence_writer.c */
typedef enum evidence_record_type {
    REC_TYPER_PROFILE = 1, REC_EVIDENCE_SPAN = 2, REC_CLAIM_CANDIDATE = 3,
    REC_RELATION_CANDIDATE = 4, REC_TYPING_BUNDLE = 5, REC_ADMISSION_POLICY = 6,
    REC_ADMISSION_DECISION = 7, REC_ADMISSION_RECEIPT = 8,
    REC_ADMISSION_LAYER = 9, REC_TYPED_VIEW_MANIFEST = 10
} evidence_record_type;

extern int elpis_evidence_write_record(const char *dir, const char *name,
                                        evidence_record_type type, uint32_t abi,
                                        const uint8_t *payload, uint32_t length);

/* Forward decls from evidence_reader.c */
extern int elpis_read_typer_profile(const char *path, elpis_evidence_typer_profile_v1 *out);
extern int elpis_read_evidence_span(const char *path, elpis_evidence_span_v1 *out);
extern int elpis_read_claim_candidate(const char *path, elpis_evidence_claim_candidate_v1 *out);
extern int elpis_read_admission_policy(const char *path, elpis_evidence_admission_policy_v1 *out);
extern int elpis_read_admission_decision(const char *path, elpis_evidence_admission_decision_v1 *out);
extern int elpis_read_admission_receipt(const char *path, elpis_evidence_admission_receipt_v1 *out);
extern int elpis_read_admission_layer(const char *path, elpis_evidence_admission_v1 *out);
extern int elpis_read_typed_evidence_view(const char *path, elpis_typed_evidence_view_v1 *out);

static const char *TEST_DIR = "/tmp/elpis_p4_test";

static void setup(void) {
    system("mkdir -p /tmp/elpis_p4_test");
    system("rm -rf /tmp/elpis_p4_test/*");
}

static void cleanup(void) {
    system("rm -rf /tmp/elpis_p4_test");
}

static void test_typer_profile_roundtrip(void) {
    elpis_evidence_typer_profile_v1 orig, loaded;
    elpis_typer_profile_init(&orig);
    orig.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    orig.confidence_scale = 10;
    orig.maximum_claims_per_item = 100;
    orig.maximum_relations_per_item = 50;
    memcpy(orig.provider_identity_digest.bytes, "X", 1);
    elpis_typer_profile_identity(&orig, &orig.profile_identity);

    int rc = elpis_evidence_write_record(TEST_DIR, "typer.bin",
                                          REC_TYPER_PROFILE, orig.abi_version,
                                          (const uint8_t *)&orig, sizeof(orig));
    TEST(write_ok, rc == 0);

    rc = elpis_read_typer_profile("/tmp/elpis_p4_test/typer.bin", &loaded);
    TEST(read_ok, rc == 0);
    TEST(kind_match, loaded.provider_kind == orig.provider_kind);
    TEST(confidence_match, loaded.confidence_scale == orig.confidence_scale);
    TEST(identity_match, memcmp(loaded.profile_identity.bytes, orig.profile_identity.bytes,
                                 HACF_DIGEST_BYTES) == 0);
}

static void test_span_roundtrip(void) {
    elpis_evidence_span_v1 orig, loaded;
    elpis_evidence_span_init(&orig);
    memset(orig.retrieval_expansion_digest.bytes, 1, 32);
    memset(orig.retrieval_bundle_digest.bytes, 1, 32);
    memset(orig.retrieval_item_attachment_digest.bytes, 1, 32);
    memset(orig.evidence_node_digest.bytes, 1, 32);
    orig.byte_start = 0;
    orig.byte_end_exclusive = 10;
    elpis_evidence_span_identity(&orig, &orig.span_identity);

    int rc = elpis_evidence_write_record(TEST_DIR, "span.bin",
                                          REC_EVIDENCE_SPAN, orig.abi_version,
                                          (const uint8_t *)&orig, sizeof(orig));
    TEST(write_ok, rc == 0);

    rc = elpis_read_evidence_span("/tmp/elpis_p4_test/span.bin", &loaded);
    TEST(read_ok, rc == 0);
    TEST(start_match, loaded.byte_start == orig.byte_start);
    TEST(end_match, loaded.byte_end_exclusive == orig.byte_end_exclusive);
}

static void test_claim_candidate_roundtrip(void) {
    elpis_evidence_claim_candidate_v1 orig, loaded;
    elpis_claim_candidate_init(&orig);
    memcpy(orig.typer_profile_digest.bytes, "X", 1);
    orig.claim_type = 1;
    memcpy(orig.claim_payload_digest.bytes, "P", 1);
    memcpy(orig.claim_payload_object_digest.bytes, "O", 1);
    orig.source_span_count = 1;
    memcpy(orig.source_span_digests[0].bytes, "S", 1);
    orig.claim_polarity = CLAIM_POLARITY_AFFIRMATIVE;
    orig.claim_modality = CLAIM_MODALITY_ASSERTED;
    orig.confidence_key = 5;
    elpis_claim_candidate_identity(&orig, &orig.candidate_identity);

    int rc = elpis_evidence_write_record(TEST_DIR, "claim.bin",
                                          REC_CLAIM_CANDIDATE, orig.abi_version,
                                          (const uint8_t *)&orig, sizeof(orig));
    TEST(write_ok, rc == 0);

    rc = elpis_read_claim_candidate("/tmp/elpis_p4_test/claim.bin", &loaded);
    TEST(read_ok, rc == 0);
    TEST(type_match, loaded.claim_type == orig.claim_type);
    TEST(polarity_match, loaded.claim_polarity == orig.claim_polarity);
}

static void test_policy_roundtrip(void) {
    elpis_evidence_admission_policy_v1 orig, loaded;
    elpis_admission_policy_init_default(&orig);
    elpis_admission_policy_identity(&orig, &orig.policy_identity);

    int rc = elpis_evidence_write_record(TEST_DIR, "policy.bin",
                                          REC_ADMISSION_POLICY, orig.abi_version,
                                          (const uint8_t *)&orig, sizeof(orig));
    TEST(write_ok, rc == 0);

    rc = elpis_read_admission_policy("/tmp/elpis_p4_test/policy.bin", &loaded);
    TEST(read_ok, rc == 0);
    TEST(strict_match, loaded.policy_flags == orig.policy_flags);
    TEST(ceiling_match, loaded.maximum_claim_authority == orig.maximum_claim_authority);
}

static void test_decision_roundtrip(void) {
    elpis_evidence_admission_decision_v1 orig, loaded;
    elpis_admission_decision_init(&orig);
    orig.candidate_kind = CANDIDATE_KIND_CLAIM;
    memcpy(orig.candidate_digest.bytes, "C", 1);
    memset(orig.typing_bundle_digest.bytes, 1, 32);
    memset(orig.admission_policy_digest.bytes, 2, 32);
    orig.validation_stage_reached = VALIDATION_STAGE_COMPLETE;
    orig.decision_disposition = DISPOSITION_ADMITTED_NEW_OBJECT;
    elpis_admission_decision_identity(&orig, &orig.decision_identity);

    int rc = elpis_evidence_write_record(TEST_DIR, "decision.bin",
                                          REC_ADMISSION_DECISION, orig.abi_version,
                                          (const uint8_t *)&orig, sizeof(orig));
    TEST(write_ok, rc == 0);

    rc = elpis_read_admission_decision("/tmp/elpis_p4_test/decision.bin", &loaded);
    TEST(read_ok, rc == 0);
    TEST(kind_match, loaded.candidate_kind == orig.candidate_kind);
    TEST(disposition_match, loaded.decision_disposition == orig.decision_disposition);
}

static void test_receipt_roundtrip(void) {
    elpis_evidence_admission_receipt_v1 orig, loaded;
    elpis_admission_receipt_init(&orig);
    memset(orig.base_snapshot_digest.bytes, 1, 32);
    memset(orig.query_overlay_digest.bytes, 2, 32);
    memset(orig.retrieval_expansion_digest.bytes, 3, 32);
    memset(orig.typing_bundle_digest.bytes, 4, 32);
    memcpy(orig.candidate_digest.bytes, "C", 1);
    memset(orig.admission_policy_digest.bytes, 5, 32);
    memset(orig.admission_decision_digest.bytes, 6, 32);
    orig.graph_edge_provenance_status = GRAPH_PROVENANCE_UNAVAILABLE;
    elpis_admission_receipt_identity(&orig, &orig.receipt_digest);

    int rc = elpis_evidence_write_record(TEST_DIR, "receipt.bin",
                                          REC_ADMISSION_RECEIPT, orig.abi_version,
                                          (const uint8_t *)&orig, sizeof(orig));
    TEST(write_ok, rc == 0);

    rc = elpis_read_admission_receipt("/tmp/elpis_p4_test/receipt.bin", &loaded);
    TEST(read_ok, rc == 0);
    TEST(provenance_status, loaded.graph_edge_provenance_status == GRAPH_PROVENANCE_UNAVAILABLE);
}

static void test_admission_layer_roundtrip(void) {
    elpis_evidence_admission_v1 orig, loaded;
    elpis_evidence_admission_init(&orig);
    memset(orig.base_snapshot_digest.bytes, 1, 32);
    memset(orig.query_overlay_digest.bytes, 2, 32);
    memset(orig.retrieval_expansion_digest.bytes, 3, 32);
    memset(orig.typing_bundle_digest.bytes, 4, 32);
    memset(orig.admission_policy_digest.bytes, 5, 32);
    orig.admission_decision_count = 5;
    orig.admission_receipt_count = 5;
    orig.admitted_claim_count = 2;
    orig.admitted_relation_count = 1;
    orig.rejected_claim_count = 1;
    orig.rejected_relation_count = 1;
    elpis_evidence_admission_identity(&orig, &orig.admission_layer_digest);

    int rc = elpis_evidence_write_record(TEST_DIR, "layer.bin",
                                          REC_ADMISSION_LAYER, orig.abi_version,
                                          (const uint8_t *)&orig, sizeof(orig));
    TEST(write_ok, rc == 0);

    rc = elpis_read_admission_layer("/tmp/elpis_p4_test/layer.bin", &loaded);
    TEST(read_ok, rc == 0);
    TEST(counts_match, loaded.admission_decision_count == orig.admission_decision_count);
}

static void test_truncation_rejected(void) {
    /* Write a valid file then truncate it */
    elpis_evidence_typer_profile_v1 orig;
    elpis_typer_profile_init(&orig);
    orig.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    orig.confidence_scale = 10;
    orig.maximum_claims_per_item = 100;
    orig.maximum_relations_per_item = 50;

    elpis_evidence_write_record(TEST_DIR, "truncated.bin",
                                 REC_TYPER_PROFILE, orig.abi_version,
                                 (const uint8_t *)&orig, sizeof(orig));

    /* Truncate to half */
    FILE *fp = fopen("/tmp/elpis_p4_test/truncated.bin", "r+b");
    if (fp) {
        fseek(fp, sizeof(orig) / 2, SEEK_SET);
        ftruncate(fileno(fp), ftell(fp));
        fclose(fp);
    }

    elpis_evidence_typer_profile_v1 loaded;
    int rc = elpis_read_typer_profile("/tmp/elpis_p4_test/truncated.bin", &loaded);
    TEST(truncation_rejected, rc != 0);
}

static void test_atomic_no_replace(void) {
    elpis_evidence_typer_profile_v1 orig;
    elpis_typer_profile_init(&orig);
    orig.provider_kind = TYPER_KIND_EXTERNAL_MODEL;
    orig.confidence_scale = 10;
    orig.maximum_claims_per_item = 100;
    orig.maximum_relations_per_item = 50;

    int rc1 = elpis_evidence_write_record(TEST_DIR, "existing.bin",
                                           REC_TYPER_PROFILE, orig.abi_version,
                                           (const uint8_t *)&orig, sizeof(orig));
    TEST(first_write_ok, rc1 == 0);

    /* Second write to same name should fail (atomic no-replace) */
    int rc2 = elpis_evidence_write_record(TEST_DIR, "existing.bin",
                                           REC_TYPER_PROFILE, orig.abi_version,
                                           (const uint8_t *)&orig, sizeof(orig));
    TEST(second_write_rejected, rc2 != 0);
}

int main(void) {
    setup();
    test_typer_profile_roundtrip();
    test_span_roundtrip();
    test_claim_candidate_roundtrip();
    test_policy_roundtrip();
    test_decision_roundtrip();
    test_receipt_roundtrip();
    test_admission_layer_roundtrip();
    test_truncation_rejected();
    test_atomic_no_replace();
    cleanup();

    printf("evidence_persistence: %d/%d tests passed\n", tests_pass, tests_run);
    return (tests_pass == tests_run) ? 0 : 1;
}
