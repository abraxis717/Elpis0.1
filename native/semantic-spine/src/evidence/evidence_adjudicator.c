/* evidence_adjudicator.c — Admission decision engine. */

#include "elpis_semantic/evidence_admission_decision.h"
#include "elpis_semantic/evidence_admission_receipt.h"
#include "elpis_semantic/evidence_admission_policy.h"
#include "elpis_semantic/evidence_claim_candidate.h"
#include "elpis_semantic/evidence_relation_candidate.h"
#include "elpis_semantic/evidence_typing_bundle.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"




#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
static const char DECISION_DOMAIN[] = "elpis.semantic.evidence_admission_decision.v1";

void elpis_admission_decision_init(elpis_evidence_admission_decision_v1 *decision) {
    memset(decision, 0, sizeof(*decision));
    decision->abi_version = EVIDENCE_ADMISSION_DECISION_ABI_VERSION;
}

int elpis_admission_decision_identity(const elpis_evidence_admission_decision_v1 *decision,
                                       hacf_digest *out) {
    if (!decision || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    elpis_sha256_update(&ctx, (const uint8_t *)DECISION_DOMAIN,
                       strlen(DECISION_DOMAIN));

    uint32_t v = __builtin_bswap32(decision->abi_version);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    v = __builtin_bswap32(decision->candidate_kind);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    elpis_sha256_update(&ctx, decision->candidate_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, decision->typing_bundle_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, decision->admission_policy_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(decision->validation_stage_reached);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(decision->decision_disposition);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    v = __builtin_bswap32(decision->decision_reason);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    v = __builtin_bswap32(decision->semantic_object_kind);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    elpis_sha256_update(&ctx, decision->semantic_object_digest.bytes, HACF_DIGEST_BYTES);

    v = __builtin_bswap32(decision->effective_authority);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);

    v = __builtin_bswap32(decision->source_span_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < decision->source_span_count; i++) {
        elpis_sha256_update(&ctx, decision->source_span_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    v = __builtin_bswap32(decision->source_attachment_count);
    elpis_sha256_update(&ctx, (const uint8_t *)&v, 4);
    for (uint32_t i = 0; i < decision->source_attachment_count; i++) {
        elpis_sha256_update(&ctx, decision->source_attachment_digests[i].bytes,
                          HACF_DIGEST_BYTES);
    }

    elpis_sha256_update(&ctx, decision->decision_diagnostic_digest.bytes, HACF_DIGEST_BYTES);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_admission_decision_validate(const elpis_evidence_admission_decision_v1 *decision) {
    if (!decision) return SEMANTIC_E_INVAL;

    if (decision->abi_version != EVIDENCE_ADMISSION_DECISION_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    /* Candidate kind */
    if (decision->candidate_kind != CANDIDATE_KIND_CLAIM &&
        decision->candidate_kind != CANDIDATE_KIND_RELATION)
        return SEMANTIC_E_INVAL;

    /* Disposition must be valid */
    if (decision->decision_disposition == 0)
        return SEMANTIC_E_INVAL;

    /* Reserved */
    for (uint32_t i = 0; i < sizeof(decision->reserved); i++) {
        if (decision->reserved[i] != 0)
            return SEMANTIC_E_RESERVATION;
    }

    return SEMANTIC_OK;
}

int elpis_disposition_is_admitted(evidence_admission_disposition disposition) {
    return disposition == DISPOSITION_ADMITTED_NEW_OBJECT ||
           disposition == DISPOSITION_ADMITTED_EXISTING_OBJECT_NEW_ASSERTION;
}

int elpis_disposition_is_rejected(evidence_admission_disposition disposition) {
    return disposition >= 100 && disposition < 200;
}

const char *elpis_disposition_string(evidence_admission_disposition disposition) {
    switch (disposition) {
        case DISPOSITION_ADMITTED_NEW_OBJECT:
            return "ADMITTED_NEW_OBJECT";
        case DISPOSITION_ADMITTED_EXISTING_OBJECT_NEW_ASSERTION:
            return "ADMITTED_EXISTING_OBJECT_NEW_ASSERTION";
        case DISPOSITION_REJECTED_INVALID_BUNDLE:
            return "REJECTED_INVALID_BUNDLE";
        case DISPOSITION_REJECTED_INVALID_SPAN:
            return "REJECTED_INVALID_SPAN";
        case DISPOSITION_REJECTED_PROVENANCE_MISMATCH:
            return "REJECTED_PROVENANCE_MISMATCH";
        case DISPOSITION_REJECTED_UNSUPPORTED_TYPE:
            return "REJECTED_UNSUPPORTED_TYPE";
        case DISPOSITION_REJECTED_UNRESOLVED_TARGET:
            return "REJECTED_UNRESOLVED_TARGET";
        case DISPOSITION_REJECTED_ROLE_CARDINALITY:
            return "REJECTED_ROLE_CARDINALITY";
        case DISPOSITION_REJECTED_CONFIDENCE_BELOW_THRESHOLD:
            return "REJECTED_CONFIDENCE_BELOW_THRESHOLD";
        case DISPOSITION_REJECTED_SOURCE_AUTHORITY:
            return "REJECTED_SOURCE_AUTHORITY";
        case DISPOSITION_REJECTED_CONTEXT_PARENT:
            return "REJECTED_CONTEXT_PARENT";
        case DISPOSITION_REJECTED_SOURCE_DIVERSITY:
            return "REJECTED_SOURCE_DIVERSITY";
        case DISPOSITION_REJECTED_DUPLICATE:
            return "REJECTED_DUPLICATE";
        case DISPOSITION_REJECTED_CONFLICTING_DUPLICATE:
            return "REJECTED_CONFLICTING_DUPLICATE";
        case DISPOSITION_REJECTED_LIMIT_EXCEEDED:
            return "REJECTED_LIMIT_EXCEEDED";
        case DISPOSITION_REJECTED_POLICY:
            return "REJECTED_POLICY";
        case DISPOSITION_BLOCKED_INTERNAL_ERROR:
            return "BLOCKED_INTERNAL_ERROR";
        default:
            return "UNKNOWN_DISPOSITION";
    }
}

const char *elpis_reason_string(evidence_decision_reason reason) {
    switch (reason) {
        case REASON_NONE: return "NONE";
        case REASON_BUNDLE_DIGEST_MISMATCH: return "BUNDLE_DIGEST_MISMATCH";
        case REASON_SPAN_BYTE_MISMATCH: return "SPAN_BYTE_MISMATCH";
        case REASON_SPAN_OUT_OF_BOUNDS: return "SPAN_OUT_OF_BOUNDS";
        case REASON_SPAN_DIGEST_MISMATCH: return "SPAN_DIGEST_MISMATCH";
        case REASON_ATTACHMENT_DIGEST_MISMATCH: return "ATTACHMENT_DIGEST_MISMATCH";
        case REASON_CHUNK_DIGEST_MISMATCH: return "CHUNK_DIGEST_MISMATCH";
        case REASON_TEXT_DIGEST_MISMATCH: return "TEXT_DIGEST_MISMATCH";
        case REASON_PROVENANCE_UNAVAILABLE: return "PROVENANCE_UNAVAILABLE";
        case REASON_UNKNOWN_TYPER_PROFILE: return "UNKNOWN_TYPER_PROFILE";
        case REASON_UNKNOWN_CLAIM_TYPE: return "UNKNOWN_CLAIM_TYPE";
        case REASON_UNKNOWN_RELATION_TYPE: return "UNKNOWN_RELATION_TYPE";
        case REASON_PAYLOAD_DIGEST_MISMATCH: return "PAYLOAD_DIGEST_MISMATCH";
        case REASON_MISSING_SOURCE_SPAN: return "MISSING_SOURCE_SPAN";
        case REASON_SPAN_FROM_ANOTHER_EXPANSION: return "SPAN_FROM_ANOTHER_EXPANSION";
        case REASON_UNKNOWN_SUBJECT: return "UNKNOWN_SUBJECT";
        case REASON_CONFIDENCE_OUT_OF_RANGE: return "CONFIDENCE_OUT_OF_RANGE";
        case REASON_UNRESOLVED_TARGET: return "UNRESOLVED_TARGET";
        case REASON_ROLE_CARDINALITY_FAILURE: return "ROLE_CARDINALITY_FAILURE";
        case REASON_CONFIDENCE_BELOW_THRESHOLD: return "CONFIDENCE_BELOW_THRESHOLD";
        case REASON_SOURCE_AUTHORITY_INSUFFICIENT: return "SOURCE_AUTHORITY_INSUFFICIENT";
        case REASON_CONTEXT_PARENT_UNAVAILABLE: return "CONTEXT_PARENT_UNAVAILABLE";
        case REASON_DISTINCT_SOURCE_REQUIREMENT: return "DISTINCT_SOURCE_REQUIREMENT";
        case REASON_DISTINCT_DOCUMENT_REQUIREMENT: return "DISTINCT_DOCUMENT_REQUIREMENT";
        case REASON_DISTINCT_BUNDLE_REQUIREMENT: return "DISTINCT_BUNDLE_REQUIREMENT";
        case REASON_EXACT_DUPLICATE_COLLAPSED: return "EXACT_DUPLICATE_COLLAPSED";
        case REASON_CONFLICTING_DUPLICATE: return "CONFLICTING_DUPLICATE";
        case REASON_ADMISSION_LIMIT_EXCEEDED: return "ADMISSION_LIMIT_EXCEEDED";
        case REASON_TYPER_NOT_ALLOWED: return "TYPER_NOT_ALLOWED";
        case REASON_CLAIM_TYPE_NOT_ALLOWED: return "CLAIM_TYPE_NOT_ALLOWED";
        case REASON_RELATION_TYPE_NOT_ALLOWED: return "RELATION_TYPE_NOT_ALLOWED";
        case REASON_INTERNAL_ERROR: return "INTERNAL_ERROR";
        case REASON_RESERVED_FIELDS_NONZERO: return "RESERVED_FIELDS_NONZERO";
        case REASON_COUNT_EXCEEDED: return "COUNT_EXCEEDED";
        default: return "UNKNOWN_REASON";
    }
}

/* Compute effective authority: minimum of source authority and policy ceiling */
uint32_t elpis_compute_effective_authority(
    uint32_t source_authority,
    uint32_t policy_ceiling,
    uint32_t candidate_authority,
    uint32_t provider_authority) {

    uint32_t effective = source_authority;
    if (policy_ceiling && policy_ceiling < effective) effective = policy_ceiling;
    if (candidate_authority && candidate_authority < effective)
        effective = candidate_authority;
    if (provider_authority && provider_authority < effective)
        effective = provider_authority;
    return effective;
}

/* Authority ceiling for relation type */
uint32_t elpis_authority_ceiling_for_relation(evidence_relation_type type) {
    /* ADVISORY = 1, PROVISIONAL = 2 */
    switch (type) {
        case RELATION_TYPE_MENTIONS:
        case RELATION_TYPE_DEFINES:
        case RELATION_TYPE_PROVIDES_CONTEXT_FOR:
            return 1u; /* ADVISORY */
        case RELATION_TYPE_SUPPORTS:
        case RELATION_TYPE_CONTRADICTS:
        case RELATION_TYPE_QUALIFIES:
        case RELATION_TYPE_LIMITS_SCOPE_OF:
            return 2u; /* PROVISIONAL */
        default:
            return 0u; /* unknown = fail closed */
    }
}
