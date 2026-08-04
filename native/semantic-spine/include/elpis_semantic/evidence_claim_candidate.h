/* elpis_semantic/evidence_claim_candidate.h — Claim candidate contract.
 *
 * A claim candidate is an externally supplied proposal for one semantic node.
 * P4 does not generate claims — it validates and admits/rejects proposals
 * from an external evidence typer.
 *
 * Identity domain: "elpis.semantic.claim_candidate.v1"
 */
#ifndef ELPIS_SEMANTIC_EVIDENCE_CLAIM_CANDIDATE_H
#define ELPIS_SEMANTIC_EVIDENCE_CLAIM_CANDIDATE_H

#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EVIDENCE_CLAIM_CANDIDATE_ABI_VERSION 1u

/* Claim polarity */
typedef enum evidence_claim_polarity {
    CLAIM_POLARITY_AFFIRMATIVE  = 1u,
    CLAIM_POLARITY_NEGATIVE     = 2u,
    CLAIM_POLARITY_NEUTRAL      = 3u,
    CLAIM_POLARITY_UNSPECIFIED  = 4u
} evidence_claim_polarity;

/* Claim modality */
typedef enum evidence_claim_modality {
    CLAIM_MODALITY_ASSERTED       = 1u,
    CLAIM_MODALITY_POSSIBLE       = 2u,
    CLAIM_MODALITY_PROBABLE       = 3u,
    CLAIM_MODALITY_CONDITIONAL    = 4u,
    CLAIM_MODALITY_COUNTERFACTUAL = 5u,
    CLAIM_MODALITY_QUOTED_ONLY    = 6u,
    CLAIM_MODALITY_UNSPECIFIED    = 7u
} evidence_claim_modality;

/* Subject object kind */
typedef enum evidence_subject_kind {
    SUBJECT_KIND_NONE    = 0u,
    SUBJECT_KIND_DIGEST  = 1u  /* subject identified by a known digest */
} evidence_subject_kind;

/* Candidate flags */
#define CLAIM_CANDIDATE_FLAG_NONE  0u
#define CLAIM_CANDIDATE_FLAG_MASK  0x01u

#define EVIDENCE_MAX_SOURCE_SPANS 64u

typedef struct elpis_evidence_claim_candidate_v1 {
    uint32_t                            abi_version;
    hacf_digest                         typer_profile_digest;
    uint32_t                            claim_type;          /* claim type ID from registry */
    hacf_digest                         claim_payload_digest;
    hacf_digest                         claim_payload_object_digest;
    hacf_digest                         source_span_digests[EVIDENCE_MAX_SOURCE_SPANS];
    uint32_t                            source_span_count;
    evidence_subject_kind               subject_object_kind;
    hacf_digest                         subject_object_digest;
    evidence_claim_polarity             claim_polarity;
    evidence_claim_modality             claim_modality;
    hacf_digest                         claim_scope_digest;
    hacf_digest                         claim_qualifier_digest;
    uint32_t                            confidence_key;
    uint32_t                            candidate_flags;
    hacf_digest                         candidate_identity;
    uint8_t                             reserved[32];
} elpis_evidence_claim_candidate_v1;

/* Zero-initialize and set abi_version */
void elpis_claim_candidate_init(elpis_evidence_claim_candidate_v1 *candidate);

/* Compute candidate identity.
 * Domain: "elpis.semantic.claim_candidate.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || typer_profile_digest(32) || claim_type(4 BE)
 *             || claim_payload_digest(32) || claim_payload_object_digest(32)
 *             || source_span_count(4 BE) || for each span: digest(32)
 *             || subject_object_kind(4 BE) || subject_object_digest(32)
 *             || claim_polarity(4 BE) || claim_modality(4 BE)
 *             || claim_scope_digest(32) || claim_qualifier_digest(32)
 *             || confidence_key(4 BE) || candidate_flags(4 BE). */
int elpis_claim_candidate_identity(const elpis_evidence_claim_candidate_v1 *candidate,
                                    hacf_digest *out);

/* Validate: typer profile exists, claim type in registry, payload digests match,
 * source spans exist and belong to same expansion, nonzero span count bounded,
 * subject exists when kind is nonzero, confidence in range, reserved zero. */
int elpis_claim_candidate_validate(const elpis_evidence_claim_candidate_v1 *candidate);

/* Compare candidates by identity */
int elpis_claim_candidate_cmp(const elpis_evidence_claim_candidate_v1 *a,
                               const elpis_evidence_claim_candidate_v1 *b);

/* Compare candidates for canonical ordering: claim_type, payload_digest, candidate_identity */
int elpis_claim_candidate_canonical_cmp(const elpis_evidence_claim_candidate_v1 *a,
                                         const elpis_evidence_claim_candidate_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
