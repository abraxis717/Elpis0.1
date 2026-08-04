/* elpis_semantic/evidence_admission_decision.h — Admission decision.
 *
 * A deterministic result of applying sealed admission policy and structural
 * validation to a candidate. Errors never default to admission.
 *
 * Identity domain: "elpis.semantic.evidence_admission_decision.v1"
 */
#ifndef ELPIS_SEMANTIC_EVIDENCE_ADMISSION_DECISION_H
#define ELPIS_SEMANTIC_EVIDENCE_ADMISSION_DECISION_H

#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EVIDENCE_ADMISSION_DECISION_ABI_VERSION 1u

/* Candidate kind */
typedef enum evidence_candidate_kind {
    CANDIDATE_KIND_CLAIM     = 1u,
    CANDIDATE_KIND_RELATION  = 2u
} evidence_candidate_kind;

/* Semantic object kind for resolved identity */
typedef enum evidence_semantic_object_kind {
    SEMANTIC_OBJECT_KIND_NONE     = 0u,
    SEMANTIC_OBJECT_KIND_CLAIM    = 1u,
    SEMANTIC_OBJECT_KIND_RELATION = 2u
} evidence_semantic_object_kind;

/* Validation stages */
typedef enum evidence_validation_stage {
    VALIDATION_STAGE_NONE               = 0u,
    VALIDATION_STAGE_BUNDLE_IDENTITY    = 1u,
    VALIDATION_STAGE_SPAN_IDENTITY      = 2u,
    VALIDATION_STAGE_TRANSPORT_PROVENANCE = 3u,
    VALIDATION_STAGE_GRAPH_PROVENANCE   = 4u,
    VALIDATION_STAGE_CANDIDATE_SCHEMA   = 5u,
    VALIDATION_STAGE_TARGET_RESOLUTION  = 6u,
    VALIDATION_STAGE_RELATION_CARDINALITY = 7u,
    VALIDATION_STAGE_POLICY_ELIGIBILITY = 8u,
    VALIDATION_STAGE_SEMANTIC_IDENTITY  = 9u,
    VALIDATION_STAGE_DUPLICATE_CONFLICT = 10u,
    VALIDATION_STAGE_COMPLETE           = 11u
} evidence_validation_stage;

/* Admission dispositions */
typedef enum evidence_admission_disposition {
    DISPOSITION_ADMITTED_NEW_OBJECT                    = 1u,
    DISPOSITION_ADMITTED_EXISTING_OBJECT_NEW_ASSERTION  = 2u,
    DISPOSITION_REJECTED_INVALID_BUNDLE                 = 100u,
    DISPOSITION_REJECTED_INVALID_SPAN                   = 101u,
    DISPOSITION_REJECTED_PROVENANCE_MISMATCH            = 102u,
    DISPOSITION_REJECTED_UNSUPPORTED_TYPE               = 103u,
    DISPOSITION_REJECTED_UNRESOLVED_TARGET              = 104u,
    DISPOSITION_REJECTED_ROLE_CARDINALITY               = 105u,
    DISPOSITION_REJECTED_CONFIDENCE_BELOW_THRESHOLD     = 106u,
    DISPOSITION_REJECTED_SOURCE_AUTHORITY               = 107u,
    DISPOSITION_REJECTED_CONTEXT_PARENT                 = 108u,
    DISPOSITION_REJECTED_SOURCE_DIVERSITY               = 109u,
    DISPOSITION_REJECTED_DUPLICATE                      = 110u,
    DISPOSITION_REJECTED_CONFLICTING_DUPLICATE          = 111u,
    DISPOSITION_REJECTED_LIMIT_EXCEEDED                 = 112u,
    DISPOSITION_REJECTED_POLICY                         = 113u,
    DISPOSITION_BLOCKED_INTERNAL_ERROR                  = 200u
} evidence_admission_disposition;

/* Diagnostic reasons */
typedef enum evidence_decision_reason {
    REASON_NONE                          = 0u,
    REASON_BUNDLE_DIGEST_MISMATCH        = 1u,
    REASON_SPAN_BYTE_MISMATCH            = 2u,
    REASON_SPAN_OUT_OF_BOUNDS            = 3u,
    REASON_SPAN_DIGEST_MISMATCH          = 4u,
    REASON_ATTACHMENT_DIGEST_MISMATCH    = 5u,
    REASON_CHUNK_DIGEST_MISMATCH         = 6u,
    REASON_TEXT_DIGEST_MISMATCH          = 7u,
    REASON_PROVENANCE_UNAVAILABLE        = 8u,
    REASON_UNKNOWN_TYPER_PROFILE         = 9u,
    REASON_UNKNOWN_CLAIM_TYPE            = 10u,
    REASON_UNKNOWN_RELATION_TYPE         = 11u,
    REASON_PAYLOAD_DIGEST_MISMATCH       = 12u,
    REASON_MISSING_SOURCE_SPAN           = 13u,
    REASON_SPAN_FROM_ANOTHER_EXPANSION   = 14u,
    REASON_UNKNOWN_SUBJECT               = 15u,
    REASON_CONFIDENCE_OUT_OF_RANGE       = 16u,
    REASON_UNRESOLVED_TARGET             = 17u,
    REASON_ROLE_CARDINALITY_FAILURE      = 18u,
    REASON_CONFIDENCE_BELOW_THRESHOLD    = 19u,
    REASON_SOURCE_AUTHORITY_INSUFFICIENT = 20u,
    REASON_CONTEXT_PARENT_UNAVAILABLE    = 21u,
    REASON_DISTINCT_SOURCE_REQUIREMENT   = 22u,
    REASON_DISTINCT_DOCUMENT_REQUIREMENT = 23u,
    REASON_DISTINCT_BUNDLE_REQUIREMENT   = 24u,
    REASON_EXACT_DUPLICATE_COLLAPSED     = 25u,
    REASON_CONFLICTING_DUPLICATE         = 26u,
    REASON_ADMISSION_LIMIT_EXCEEDED      = 27u,
    REASON_TYPER_NOT_ALLOWED             = 28u,
    REASON_CLAIM_TYPE_NOT_ALLOWED        = 29u,
    REASON_RELATION_TYPE_NOT_ALLOWED     = 30u,
    REASON_POLICY                        = 299u,
    REASON_INTERNAL_ERROR                = 200u,
    REASON_RESERVED_FIELDS_NONZERO       = 201u,
    REASON_COUNT_EXCEEDED                = 202u
} evidence_decision_reason;

#define EVIDENCE_DECISION_MAX_SPANS   64u
#define EVIDENCE_DECISION_MAX_ITEMS   64u

typedef struct elpis_evidence_admission_decision_v1 {
    uint32_t                            abi_version;
    evidence_candidate_kind             candidate_kind;
    hacf_digest                         candidate_digest;
    hacf_digest                         typing_bundle_digest;
    hacf_digest                         admission_policy_digest;
    evidence_validation_stage           validation_stage_reached;
    evidence_admission_disposition      decision_disposition;
    evidence_decision_reason            decision_reason;
    evidence_semantic_object_kind       semantic_object_kind;
    hacf_digest                         semantic_object_digest;
    uint32_t                            effective_authority;
    hacf_digest                         source_span_digests[EVIDENCE_DECISION_MAX_SPANS];
    uint32_t                            source_span_count;
    hacf_digest                         source_attachment_digests[EVIDENCE_DECISION_MAX_ITEMS];
    uint32_t                            source_attachment_count;
    hacf_digest                         decision_diagnostic_digest;
    hacf_digest                         decision_identity;
    uint8_t                             reserved[32];
} elpis_evidence_admission_decision_v1;

/* Zero-initialize and set abi_version */
void elpis_admission_decision_init(elpis_evidence_admission_decision_v1 *decision);

/* Compute decision identity.
 * Domain: "elpis.semantic.evidence_admission_decision.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || candidate_kind(4 BE) || candidate_digest(32)
 *             || typing_bundle_digest(32) || admission_policy_digest(32)
 *             || validation_stage_reached(4 BE)
 *             || decision_disposition(4 BE) || decision_reason(4 BE)
 *             || semantic_object_kind(4 BE) || semantic_object_digest(32)
 *             || effective_authority(4 BE)
 *             || source_span_count(4 BE) || for each span: digest(32)
 *             || source_attachment_count(4 BE) || for each: digest(32)
 *             || decision_diagnostic_digest(32). */
int elpis_admission_decision_identity(const elpis_evidence_admission_decision_v1 *decision,
                                       hacf_digest *out);

/* Validate decision fields */
int elpis_admission_decision_validate(const elpis_evidence_admission_decision_v1 *decision);

/* Check if disposition is an admission (not rejection) */
int elpis_disposition_is_admitted(evidence_admission_disposition disposition);

/* Check if disposition is a rejection */
int elpis_disposition_is_rejected(evidence_admission_disposition disposition);

/* Get human-readable disposition string */
const char *elpis_disposition_string(evidence_admission_disposition disposition);

/* Get human-readable reason string */
const char *elpis_reason_string(evidence_decision_reason reason);

#ifdef __cplusplus
}
#endif
#endif
