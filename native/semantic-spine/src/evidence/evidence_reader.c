/* evidence_reader.c — Verified deserialization for P4 evidence objects.
 *
 * Readers must:
 *  1. Parse exact field widths.
 *  2. Validate bounds.
 *  3. Validate reserved fields.
 *  4. Reconstruct canonical identity bytes.
 *  5. Verify stored digest.
 *  6. Verify HACF package identity where present.
 *  7. Reject trailing bytes.
 *  8. Reject truncation.
 *  9. Reject invalid enum values.
 * 10. Reject altered counts.
 * 11. Reject altered offsets.
 * 12. Reject altered authority.
 * 13. Reject altered decision dispositions.
 * 14. Reject altered provenance availability.
 */

#include "elpis/cascade.h"
#include "elpis/fms.h"
#include "elpis/fms_pal.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
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


/* Shared types from evidence_writer.c */
#ifndef EVIDENCE_RECORD_TYPE_ENUM
#define EVIDENCE_RECORD_TYPE_ENUM
typedef enum evidence_record_type {
    REC_TYPER_PROFILE        = 1u,
    REC_EVIDENCE_SPAN        = 2u,
    REC_CLAIM_CANDIDATE      = 3u,
    REC_RELATION_CANDIDATE   = 4u,
    REC_TYPING_BUNDLE        = 5u,
    REC_ADMISSION_POLICY     = 6u,
    REC_ADMISSION_DECISION   = 7u,
    REC_ADMISSION_RECEIPT    = 8u,
    REC_ADMISSION_LAYER      = 9u,
    REC_TYPED_VIEW_MANIFEST  = 10u,
    REC_TYPING_BUNDLE_POLICY = 11u
} evidence_record_type;
#endif

/* Forward declaration from evidence_writer.c */
extern int elpis_evidence_read_record(
    const char *filepath,
    evidence_record_type *out_type,
    uint32_t *out_abi_version,
    uint8_t *out_payload,
    uint32_t out_payload_capacity,
    uint32_t *out_payload_length,
    hacf_digest *out_stored_digest);




#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
#include <stdio.h>

/* Reuse reader function from evidence_writer.c */
extern int elpis_evidence_read_record(
    const char *filepath,
    evidence_record_type *out_type,
    uint32_t *out_abi_version,
    uint8_t *out_payload,
    uint32_t out_payload_capacity,
    uint32_t *out_payload_length,
    hacf_digest *out_stored_digest);

/* Read a typer profile from a persisted file */
int elpis_read_typer_profile(const char *filepath,
                              elpis_evidence_typer_profile_v1 *out) {
    uint8_t payload[4096];
    uint32_t len = 0;
    evidence_record_type rec_type;
    uint32_t abi;
    hacf_digest digest;

    int rc = elpis_evidence_read_record(filepath, &rec_type, &abi,
                                         payload, sizeof(payload),
                                         &len, &digest);
    if (rc != 0) return rc;

    if (rec_type != REC_TYPER_PROFILE) return -9;
    if (abi != EVIDENCE_TYPER_PROFILE_ABI_VERSION) return -9;
    if (len != sizeof(elpis_evidence_typer_profile_v1)) return -9;

    memcpy(out, payload, sizeof(*out));

    /* Validate */
    rc = elpis_typer_profile_validate(out);
    if (rc != 0) return rc;

    /* Verify identity */
    hacf_digest computed;
    rc = elpis_typer_profile_identity(out, &computed);
    if (rc != 0) return rc;

    if (memcmp(computed.bytes, out->profile_identity.bytes, HACF_DIGEST_BYTES) != 0)
        return -10; /* Identity mismatch */

    return 0;
}

/* Read an evidence span from a persisted file */
int elpis_read_evidence_span(const char *filepath, elpis_evidence_span_v1 *out) {
    uint8_t payload[4096];
    uint32_t len = 0;
    evidence_record_type rec_type;
    uint32_t abi;
    hacf_digest digest;

    int rc = elpis_evidence_read_record(filepath, &rec_type, &abi,
                                         payload, sizeof(payload),
                                         &len, &digest);
    if (rc != 0) return rc;

    if (rec_type != REC_EVIDENCE_SPAN) return -9;
    if (abi != EVIDENCE_SPAN_ABI_VERSION) return -9;
    if (len != sizeof(elpis_evidence_span_v1)) return -9;

    memcpy(out, payload, sizeof(*out));

    rc = elpis_evidence_span_validate(out, NULL, 0);
    if (rc != 0) return rc;

    hacf_digest computed;
    rc = elpis_evidence_span_identity(out, &computed);
    if (rc != 0) return rc;

    if (memcmp(computed.bytes, out->span_identity.bytes, HACF_DIGEST_BYTES) != 0)
        return -10;

    return 0;
}

/* Read a claim candidate from a persisted file */
int elpis_read_claim_candidate(const char *filepath,
                                elpis_evidence_claim_candidate_v1 *out) {
    uint8_t payload[8192];
    uint32_t len = 0;
    evidence_record_type rec_type;
    uint32_t abi;
    hacf_digest digest;

    int rc = elpis_evidence_read_record(filepath, &rec_type, &abi,
                                         payload, sizeof(payload),
                                         &len, &digest);
    if (rc != 0) return rc;

    if (rec_type != REC_CLAIM_CANDIDATE) return -9;
    if (abi != EVIDENCE_CLAIM_CANDIDATE_ABI_VERSION) return -9;
    if (len != sizeof(elpis_evidence_claim_candidate_v1)) return -9;

    memcpy(out, payload, sizeof(*out));

    rc = elpis_claim_candidate_validate(out);
    if (rc != 0) return rc;

    hacf_digest computed;
    rc = elpis_claim_candidate_identity(out, &computed);
    if (rc != 0) return rc;

    if (memcmp(computed.bytes, out->candidate_identity.bytes, HACF_DIGEST_BYTES) != 0)
        return -10;

    return 0;
}

/* Read a relation candidate from a persisted file */
int elpis_read_relation_candidate(const char *filepath,
                                   elpis_evidence_relation_candidate_v1 *out) {
    uint8_t payload[8192];
    uint32_t len = 0;
    evidence_record_type rec_type;
    uint32_t abi;
    hacf_digest digest;

    int rc = elpis_evidence_read_record(filepath, &rec_type, &abi,
                                         payload, sizeof(payload),
                                         &len, &digest);
    if (rc != 0) return rc;

    if (rec_type != REC_RELATION_CANDIDATE) return -9;
    if (abi != EVIDENCE_RELATION_CANDIDATE_ABI_VERSION) return -9;
    if (len != sizeof(elpis_evidence_relation_candidate_v1)) return -9;

    memcpy(out, payload, sizeof(*out));

    rc = elpis_relation_candidate_validate(out);
    if (rc != 0) return rc;

    hacf_digest computed;
    rc = elpis_relation_candidate_identity(out, &computed);
    if (rc != 0) return rc;

    if (memcmp(computed.bytes, out->candidate_identity.bytes, HACF_DIGEST_BYTES) != 0)
        return -10;

    return 0;
}

/* Read a typing bundle from a persisted file */
int elpis_read_typing_bundle(const char *filepath,
                              elpis_evidence_typing_bundle_v1 *out) {
    uint8_t payload[65536];
    uint32_t len = 0;
    evidence_record_type rec_type;
    uint32_t abi;
    hacf_digest digest;

    int rc = elpis_evidence_read_record(filepath, &rec_type, &abi,
                                         payload, sizeof(payload),
                                         &len, &digest);
    if (rc != 0) return rc;

    if (rec_type != REC_TYPING_BUNDLE) return -9;
    if (abi != EVIDENCE_TYPING_BUNDLE_ABI_VERSION) return -9;
    if (len != sizeof(elpis_evidence_typing_bundle_v1)) return -9;

    memcpy(out, payload, sizeof(*out));

    rc = elpis_typing_bundle_validate(out);
    if (rc != 0) return rc;

    hacf_digest computed;
    rc = elpis_typing_bundle_identity(out, &computed);
    if (rc != 0) return rc;

    if (memcmp(computed.bytes, out->typing_bundle_digest.bytes,
               HACF_DIGEST_BYTES) != 0)
        return -10;

    return 0;
}

/* Read an admission policy from a persisted file */
int elpis_read_admission_policy(const char *filepath,
                                 elpis_evidence_admission_policy_v1 *out) {
    uint8_t payload[8192];
    uint32_t len = 0;
    evidence_record_type rec_type;
    uint32_t abi;
    hacf_digest digest;

    int rc = elpis_evidence_read_record(filepath, &rec_type, &abi,
                                         payload, sizeof(payload),
                                         &len, &digest);
    if (rc != 0) return rc;

    if (rec_type != REC_ADMISSION_POLICY) return -9;
    if (abi != EVIDENCE_ADMISSION_POLICY_ABI_VERSION) return -9;
    if (len != sizeof(elpis_evidence_admission_policy_v1)) return -9;

    memcpy(out, payload, sizeof(*out));

    rc = elpis_admission_policy_validate(out);
    if (rc != 0) return rc;

    hacf_digest computed;
    rc = elpis_admission_policy_identity(out, &computed);
    if (rc != 0) return rc;

    if (memcmp(computed.bytes, out->policy_identity.bytes,
               HACF_DIGEST_BYTES) != 0)
        return -10;

    return 0;
}

/* Read an admission decision from a persisted file */
int elpis_read_admission_decision(const char *filepath,
                                   elpis_evidence_admission_decision_v1 *out) {
    uint8_t payload[16384];
    uint32_t len = 0;
    evidence_record_type rec_type;
    uint32_t abi;
    hacf_digest digest;

    int rc = elpis_evidence_read_record(filepath, &rec_type, &abi,
                                         payload, sizeof(payload),
                                         &len, &digest);
    if (rc != 0) return rc;

    if (rec_type != REC_ADMISSION_DECISION) return -9;
    if (abi != EVIDENCE_ADMISSION_DECISION_ABI_VERSION) return -9;
    if (len != sizeof(elpis_evidence_admission_decision_v1)) return -9;

    memcpy(out, payload, sizeof(*out));

    rc = elpis_admission_decision_validate(out);
    if (rc != 0) return rc;

    /* Verify disposition is valid enum */
    if (out->decision_disposition == 0) return -9;

    hacf_digest computed;
    rc = elpis_admission_decision_identity(out, &computed);
    if (rc != 0) return rc;

    if (memcmp(computed.bytes, out->decision_identity.bytes,
               HACF_DIGEST_BYTES) != 0)
        return -10;

    return 0;
}

/* Read an admission receipt from a persisted file */
int elpis_read_admission_receipt(const char *filepath,
                                  elpis_evidence_admission_receipt_v1 *out) {
    uint8_t payload[32768];
    uint32_t len = 0;
    evidence_record_type rec_type;
    uint32_t abi;
    hacf_digest digest;

    int rc = elpis_evidence_read_record(filepath, &rec_type, &abi,
                                         payload, sizeof(payload),
                                         &len, &digest);
    if (rc != 0) return rc;

    if (rec_type != REC_ADMISSION_RECEIPT) return -9;
    if (abi != EVIDENCE_ADMISSION_RECEIPT_ABI_VERSION) return -9;
    if (len != sizeof(elpis_evidence_admission_receipt_v1)) return -9;

    memcpy(out, payload, sizeof(*out));

    rc = elpis_admission_receipt_validate(out);
    if (rc != 0) return rc;

    /* Verify provenance status */
    rc = elpis_receipt_provenance_status_verify(out);
    if (rc != 0) return rc;

    hacf_digest computed;
    rc = elpis_admission_receipt_identity(out, &computed);
    if (rc != 0) return rc;

    if (memcmp(computed.bytes, out->receipt_digest.bytes,
               HACF_DIGEST_BYTES) != 0)
        return -10;

    return 0;
}

/* Read an admission layer from a persisted file */
int elpis_read_admission_layer(const char *filepath,
                                elpis_evidence_admission_v1 *out) {
    uint8_t payload[65536];
    uint32_t len = 0;
    evidence_record_type rec_type;
    uint32_t abi;
    hacf_digest digest;

    int rc = elpis_evidence_read_record(filepath, &rec_type, &abi,
                                         payload, sizeof(payload),
                                         &len, &digest);
    if (rc != 0) return rc;

    if (rec_type != REC_ADMISSION_LAYER) return -9;
    if (abi != EVIDENCE_ADMISSION_ABI_VERSION) return -9;
    if (len != sizeof(elpis_evidence_admission_v1)) return -9;

    memcpy(out, payload, sizeof(*out));

    rc = elpis_evidence_admission_validate(out);
    if (rc != 0) return rc;

    hacf_digest computed;
    rc = elpis_evidence_admission_identity(out, &computed);
    if (rc != 0) return rc;

    if (memcmp(computed.bytes, out->admission_layer_digest.bytes,
               HACF_DIGEST_BYTES) != 0)
        return -10;

    return 0;
}

/* Read a typed-evidence view manifest from a persisted file */
int elpis_read_typed_evidence_view(const char *filepath,
                                    elpis_typed_evidence_view_v1 *out) {
    uint8_t payload[132000];
    uint32_t len = 0;
    evidence_record_type rec_type;
    uint32_t abi;
    hacf_digest digest;

    int rc = elpis_evidence_read_record(filepath, &rec_type, &abi,
                                         payload, sizeof(payload),
                                         &len, &digest);
    if (rc != 0) return rc;

    if (rec_type != REC_TYPED_VIEW_MANIFEST) return -9;
    if (abi != TYPED_EVIDENCE_VIEW_ABI_VERSION) return -9;
    if (len != sizeof(elpis_typed_evidence_view_v1)) return -9;

    memcpy(out, payload, sizeof(*out));

    rc = elpis_typed_evidence_view_validate(out);
    if (rc != 0) return rc;

    hacf_digest computed;
    rc = elpis_typed_evidence_view_identity(out, &computed);
    if (rc != 0) return rc;

    if (memcmp(computed.bytes, out->typed_evidence_view_digest.bytes,
               HACF_DIGEST_BYTES) != 0)
        return -10;

    return 0;
}
