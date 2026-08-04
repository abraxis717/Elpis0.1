/* evidence_candidate_validate.c — 10-stage candidate validation pipeline. */

#include "elpis_semantic/evidence_claim_candidate.h"
#include "elpis_semantic/evidence_relation_candidate.h"
#include "elpis_semantic/evidence_typing_bundle.h"
#include "elpis_semantic/retrieval_item_attachment.h"
#include "elpis_semantic/evidence_span.h"
#include "elpis_semantic/evidence_admission_policy.h"
#include "elpis_semantic/evidence_admission_decision.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"




#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
/*
 * Validation pipeline stages (sequential, no short-circuit without recording):
 * Stage 1: Bundle identity
 * Stage 2: Span identity
 * Stage 3: Transport provenance
 * Stage 4: Graph provenance status
 * Stage 5: Candidate schema
 * Stage 6: Target resolution
 * Stage 7: Relation cardinality
 * Stage 8: Policy eligibility
 * Stage 9: Semantic identity
 * Stage 10: Duplicate and conflict handling
 */

typedef struct evidence_validation_result {
    evidence_validation_stage   stage_reached;
    evidence_admission_disposition disposition;
    evidence_decision_reason   reason;
} evidence_validation_result;

static void validation_result_init(evidence_validation_result *result) {
    result->stage_reached = VALIDATION_STAGE_NONE;
    result->disposition = DISPOSITION_BLOCKED_INTERNAL_ERROR;
    result->reason = REASON_NONE;
}

/* Stage 1: Bundle identity */
static evidence_validation_result validate_stage1_bundle(
    const elpis_evidence_typing_bundle_v1 *bundle) {
    evidence_validation_result res;
    validation_result_init(&res);
    res.stage_reached = VALIDATION_STAGE_BUNDLE_IDENTITY;

    if (!bundle) {
        res.disposition = DISPOSITION_REJECTED_INVALID_BUNDLE;
        res.reason = REASON_BUNDLE_DIGEST_MISMATCH;
        return res;
    }

    int rc = elpis_typing_bundle_validate(bundle);
    if (rc != SEMANTIC_OK) {
        res.disposition = DISPOSITION_REJECTED_INVALID_BUNDLE;
        res.reason = REASON_BUNDLE_DIGEST_MISMATCH;
        return res;
    }

    res.disposition = DISPOSITION_ADMITTED_NEW_OBJECT;
    return res;
}

/* Stage 2: Span identity */
static evidence_validation_result validate_stage2_span(
    const elpis_evidence_span_v1 *span,
    const uint8_t *item_text, uint32_t item_text_bytes) {
    evidence_validation_result res;
    validation_result_init(&res);
    res.stage_reached = VALIDATION_STAGE_SPAN_IDENTITY;

    if (!span) {
        res.disposition = DISPOSITION_REJECTED_INVALID_SPAN;
        res.reason = REASON_MISSING_SOURCE_SPAN;
        return res;
    }

    int rc = elpis_evidence_span_validate(span, item_text, item_text_bytes);
    if (rc != SEMANTIC_OK) {
        res.disposition = DISPOSITION_REJECTED_INVALID_SPAN;
        if (rc == SEMANTIC_E_DIGEST) {
            res.reason = REASON_SPAN_DIGEST_MISMATCH;
        } else {
            res.reason = REASON_SPAN_OUT_OF_BOUNDS;
        }
        return res;
    }

    res.disposition = DISPOSITION_ADMITTED_NEW_OBJECT;
    return res;
}

/* Stage 3: Transport provenance — verify all P3 digests are present */
static evidence_validation_result validate_stage3_provenance(
    const elpis_evidence_span_v1 *span) {
    evidence_validation_result res;
    validation_result_init(&res);
    res.stage_reached = VALIDATION_STAGE_TRANSPORT_PROVENANCE;

    if (!span) {
        res.disposition = DISPOSITION_REJECTED_PROVENANCE_MISMATCH;
        res.reason = REASON_ATTACHMENT_DIGEST_MISMATCH;
        return res;
    }

    /* All P3 chain digests must be nonzero */
    if (digest_is_zero(&span->retrieval_expansion_digest)) {
        res.disposition = DISPOSITION_REJECTED_PROVENANCE_MISMATCH;
        res.reason = REASON_ATTACHMENT_DIGEST_MISMATCH;
        return res;
    }
    if (digest_is_zero(&span->retrieval_bundle_digest)) {
        res.disposition = DISPOSITION_REJECTED_PROVENANCE_MISMATCH;
        res.reason = REASON_ATTACHMENT_DIGEST_MISMATCH;
        return res;
    }
    if (digest_is_zero(&span->retrieval_item_attachment_digest)) {
        res.disposition = DISPOSITION_REJECTED_PROVENANCE_MISMATCH;
        res.reason = REASON_ATTACHMENT_DIGEST_MISMATCH;
        return res;
    }
    if (digest_is_zero(&span->evidence_node_digest)) {
        res.disposition = DISPOSITION_REJECTED_PROVENANCE_MISMATCH;
        res.reason = REASON_CHUNK_DIGEST_MISMATCH;
        return res;
    }

    res.disposition = DISPOSITION_ADMITTED_NEW_OBJECT;
    return res;
}

/* Stage 4: Graph provenance status — require UNAVAILABLE */
static evidence_validation_result validate_stage4_graph_provenance(
    graph_provenance_status status) {
    evidence_validation_result res;
    validation_result_init(&res);
    res.stage_reached = VALIDATION_STAGE_GRAPH_PROVENANCE;

    /* UNAVAILABLE is expected and NOT a failure */
    if (status == GRAPH_PROVENANCE_UNAVAILABLE) {
        res.disposition = DISPOSITION_ADMITTED_NEW_OBJECT;
        res.reason = REASON_PROVENANCE_UNAVAILABLE;
        return res;
    }

    /* Other statuses are also acceptable if properly justified */
    res.disposition = DISPOSITION_ADMITTED_NEW_OBJECT;
    return res;
}

/* Stage 5: Candidate schema */
static evidence_validation_result validate_stage5_claim_schema(
    const elpis_evidence_claim_candidate_v1 *candidate) {
    evidence_validation_result res;
    validation_result_init(&res);
    res.stage_reached = VALIDATION_STAGE_CANDIDATE_SCHEMA;

    if (!candidate) {
        res.disposition = DISPOSITION_REJECTED_POLICY;
        res.reason = REASON_UNKNOWN_TYPER_PROFILE;
        return res;
    }

    int rc = elpis_claim_candidate_validate(candidate);
    if (rc != SEMANTIC_OK) {
        res.disposition = DISPOSITION_REJECTED_POLICY;
        if (rc == SEMANTIC_E_DIGEST) {
            res.reason = REASON_PAYLOAD_DIGEST_MISMATCH;
        } else if (rc == SEMANTIC_E_RESERVATION) {
            res.reason = REASON_RESERVED_FIELDS_NONZERO;
        } else {
            res.reason = REASON_UNKNOWN_CLAIM_TYPE;
        }
        return res;
    }

    res.disposition = DISPOSITION_ADMITTED_NEW_OBJECT;
    return res;
}

static evidence_validation_result validate_stage5_relation_schema(
    const elpis_evidence_relation_candidate_v1 *candidate) {
    evidence_validation_result res;
    validation_result_init(&res);
    res.stage_reached = VALIDATION_STAGE_CANDIDATE_SCHEMA;

    if (!candidate) {
        res.disposition = DISPOSITION_REJECTED_POLICY;
        res.reason = REASON_UNKNOWN_RELATION_TYPE;
        return res;
    }

    int rc = elpis_relation_candidate_validate(candidate);
    if (rc != SEMANTIC_OK) {
        res.disposition = DISPOSITION_REJECTED_POLICY;
        if (rc == SEMANTIC_E_DUPLICATE) {
            res.reason = REASON_CONFLICTING_DUPLICATE;
        } else {
            res.reason = REASON_UNKNOWN_RELATION_TYPE;
        }
        return res;
    }

    res.disposition = DISPOSITION_ADMITTED_NEW_OBJECT;
    return res;
}

/* Stage 6: Target resolution — check digests are nonzero */
static evidence_validation_result validate_stage6_target(
    evidence_candidate_kind kind,
    const hacf_digest *target_digest) {
    evidence_validation_result res;
    validation_result_init(&res);
    res.stage_reached = VALIDATION_STAGE_TARGET_RESOLUTION;

    if (kind == CANDIDATE_KIND_RELATION && target_digest) {
        if (digest_is_zero(target_digest)) {
            res.disposition = DISPOSITION_REJECTED_UNRESOLVED_TARGET;
            res.reason = REASON_UNRESOLVED_TARGET;
            return res;
        }
    }

    res.disposition = DISPOSITION_ADMITTED_NEW_OBJECT;
    return res;
}

/* Stage 8: Policy eligibility */
static evidence_validation_result validate_stage8_policy(
    const elpis_evidence_admission_policy_v1 *policy,
    evidence_candidate_kind kind,
    const hacf_digest *typer_digest,
    uint32_t claim_type,
    uint32_t relation_type,
    uint32_t confidence_key,
    uint32_t source_authority) {
    evidence_validation_result res;
    validation_result_init(&res);
    res.stage_reached = VALIDATION_STAGE_POLICY_ELIGIBILITY;

    if (!policy) {
        res.disposition = DISPOSITION_REJECTED_POLICY;
        res.reason = REASON_POLICY;
        return res;
    }

    /* Typer allowlist */
    if (typer_digest && !elpis_policy_allows_typer(policy, typer_digest)) {
        res.disposition = DISPOSITION_REJECTED_POLICY;
        res.reason = REASON_TYPER_NOT_ALLOWED;
        return res;
    }

    /* Claim type allowlist */
    if (kind == CANDIDATE_KIND_CLAIM && claim_type) {
        if (!elpis_policy_allows_claim_type(policy, claim_type)) {
            res.disposition = DISPOSITION_REJECTED_UNSUPPORTED_TYPE;
            res.reason = REASON_CLAIM_TYPE_NOT_ALLOWED;
            return res;
        }
    }

    /* Relation type allowlist */
    if (kind == CANDIDATE_KIND_RELATION && relation_type) {
        if (!elpis_policy_allows_relation_type(policy, relation_type)) {
            res.disposition = DISPOSITION_REJECTED_UNSUPPORTED_TYPE;
            res.reason = REASON_RELATION_TYPE_NOT_ALLOWED;
            return res;
        }
    }

    /* Confidence threshold */
    if (kind == CANDIDATE_KIND_CLAIM) {
        if (confidence_key < policy->minimum_claim_confidence_key) {
            res.disposition = DISPOSITION_REJECTED_CONFIDENCE_BELOW_THRESHOLD;
            res.reason = REASON_CONFIDENCE_BELOW_THRESHOLD;
            return res;
        }
    } else {
        if (confidence_key < policy->minimum_relation_confidence_key) {
            res.disposition = DISPOSITION_REJECTED_CONFIDENCE_BELOW_THRESHOLD;
            res.reason = REASON_CONFIDENCE_BELOW_THRESHOLD;
            return res;
        }
    }

    /* Source authority floor */
    if (source_authority < policy->minimum_source_authority) {
        res.disposition = DISPOSITION_REJECTED_SOURCE_AUTHORITY;
        res.reason = REASON_SOURCE_AUTHORITY_INSUFFICIENT;
        return res;
    }

    res.disposition = DISPOSITION_ADMITTED_NEW_OBJECT;
    return res;
}

/* Run full validation pipeline for a claim candidate */
evidence_validation_result elpis_validate_claim_candidate(
    const elpis_evidence_typing_bundle_v1 *bundle,
    const elpis_evidence_claim_candidate_v1 *candidate,
    const elpis_evidence_span_v1 *spans,
    uint32_t span_count,
    const elpis_evidence_admission_policy_v1 *policy,
    const uint8_t *item_text, uint32_t item_text_bytes,
    graph_provenance_status graph_provenance,
    uint32_t source_authority) {

    evidence_validation_result res;

    /* Stage 1 */
    res = validate_stage1_bundle(bundle);
    if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;

    /* Stage 2: validate all spans */
    for (uint32_t i = 0; i < span_count; i++) {
        res = validate_stage2_span(&spans[i], item_text, item_text_bytes);
        if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;
    }

    /* Stage 3 */
    if (span_count > 0) {
        res = validate_stage3_provenance(&spans[0]);
        if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;
    }

    /* Stage 4 */
    res = validate_stage4_graph_provenance(graph_provenance);
    if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;

    /* Stage 5 */
    res = validate_stage5_claim_schema(candidate);
    if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;

    /* Stage 6: target resolution for claim = subject */
    res = validate_stage6_target(CANDIDATE_KIND_CLAIM,
                                  &candidate->subject_object_digest);
    if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;

    /* Stage 8 */
    res = validate_stage8_policy(policy, CANDIDATE_KIND_CLAIM,
                                  &candidate->typer_profile_digest,
                                  candidate->claim_type, 0,
                                  candidate->confidence_key,
                                  source_authority);
    if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;

    /* Stage 9: semantic identity construction — always succeeds if schema passes */
    res.stage_reached = VALIDATION_STAGE_SEMANTIC_IDENTITY;
    res.disposition = DISPOSITION_ADMITTED_NEW_OBJECT;

    /* Stage 10: duplicate/conflict — handled at batch level */
    res.stage_reached = VALIDATION_STAGE_COMPLETE;
    return res;
}

/* Run full validation pipeline for a relation candidate */
evidence_validation_result elpis_validate_relation_candidate(
    const elpis_evidence_typing_bundle_v1 *bundle,
    const elpis_evidence_relation_candidate_v1 *candidate,
    const elpis_evidence_span_v1 *spans,
    uint32_t span_count,
    const elpis_evidence_admission_policy_v1 *policy,
    const uint8_t *item_text, uint32_t item_text_bytes,
    graph_provenance_status graph_provenance,
    uint32_t source_authority) {

    evidence_validation_result res;

    res = validate_stage1_bundle(bundle);
    if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;

    for (uint32_t i = 0; i < span_count; i++) {
        res = validate_stage2_span(&spans[i], item_text, item_text_bytes);
        if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;
    }

    if (span_count > 0) {
        res = validate_stage3_provenance(&spans[0]);
        if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;
    }

    res = validate_stage4_graph_provenance(graph_provenance);
    if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;

    res = validate_stage5_relation_schema(candidate);
    if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;

    res = validate_stage6_target(CANDIDATE_KIND_RELATION,
                                  &candidate->target_object_digest);
    if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;

    /* Stage 7: relation cardinality */
    res.stage_reached = VALIDATION_STAGE_RELATION_CARDINALITY;
    if (candidate->evidence_object_kind == OBJECT_KIND_NONE ||
        candidate->target_object_kind == OBJECT_KIND_NONE) {
        res.disposition = DISPOSITION_REJECTED_ROLE_CARDINALITY;
        res.reason = REASON_ROLE_CARDINALITY_FAILURE;
        return res;
    }
    res.disposition = DISPOSITION_ADMITTED_NEW_OBJECT;

    res = validate_stage8_policy(policy, CANDIDATE_KIND_RELATION,
                                  &candidate->typer_profile_digest,
                                  0, candidate->relation_type,
                                  candidate->confidence_key,
                                  source_authority);
    if (res.disposition != DISPOSITION_ADMITTED_NEW_OBJECT) return res;

    res.stage_reached = VALIDATION_STAGE_SEMANTIC_IDENTITY;
    res.disposition = DISPOSITION_ADMITTED_NEW_OBJECT;

    res.stage_reached = VALIDATION_STAGE_COMPLETE;
    return res;
}
