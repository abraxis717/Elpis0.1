/* elpis_semantic/evidence_admission_policy.h — Evidence-admission policy.
 *
 * A sealed policy governing admission of claim and relation candidates.
 * P4 v1 default policy is defined prospectively and enforced deterministically.
 *
 * Identity domain: "elpis.semantic.evidence_admission_policy.v1"
 */
#ifndef ELPIS_SEMANTIC_EVIDENCE_ADMISSION_POLICY_H
#define ELPIS_SEMANTIC_EVIDENCE_ADMISSION_POLICY_H

#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EVIDENCE_ADMISSION_POLICY_ABI_VERSION 1u

/* Duplicate handling */
typedef enum evidence_duplicate_handling {
    DUPLICATE_COLLAPSE       = 1u, /* collapse exact duplicates */
    DUPLICATE_REJECT         = 2u, /* reject all duplicates */
    DUPLICATE_REJECT_CONFLICT = 3u /* reject conflicting duplicates */
} evidence_duplicate_handling;

/* Conflict handling */
typedef enum evidence_conflict_handling {
    CONFLICT_RETAIN_BOTH     = 1u, /* retain SUPPORTS and CONTRADICTS independently */
    CONFLICT_REJECT_BOTH     = 2u,
    CONFLICT_DEFER           = 3u
} evidence_conflict_handling;

/* Unsupported type behavior */
typedef enum evidence_unsupported_type_behavior {
    UNSUPPORTED_REJECT       = 1u,
    UNSUPPORTED_SKIP         = 2u
} evidence_unsupported_type_behavior;

#define EVIDENCE_POLICY_MAX_PROVIDER_DIGESTS 16u
#define EVIDENCE_POLICY_MAX_CLAIM_TYPE_IDS   64u
#define EVIDENCE_POLICY_MAX_RELATION_TYPE_IDS 64u

/* Policy flags */
#define ADMISSION_POLICY_FLAG_NONE       0u
#define ADMISSION_POLICY_FLAG_STRICT     0x01u
#define ADMISSION_POLICY_FLAG_MASK       0x01u

typedef struct elpis_evidence_admission_policy_v1 {
    uint32_t                            abi_version;
    hacf_digest                         allowed_typer_profile_digests[EVIDENCE_POLICY_MAX_PROVIDER_DIGESTS];
    uint32_t                            allowed_typer_count;
    uint32_t                            allowed_claim_type_ids[EVIDENCE_POLICY_MAX_CLAIM_TYPE_IDS];
    uint32_t                            allowed_claim_type_count;
    uint32_t                            allowed_relation_type_ids[EVIDENCE_POLICY_MAX_RELATION_TYPE_IDS];
    uint32_t                            allowed_relation_type_count;
    uint32_t                            minimum_claim_confidence_key;
    uint32_t                            minimum_relation_confidence_key;
    uint32_t                            maximum_claim_authority;
    uint32_t                            maximum_relation_authority;
    uint32_t                            minimum_source_authority;
    uint32_t                            require_exact_span_validation;
    uint32_t                            require_target_resolution;
    uint32_t                            require_subject_resolution;
    uint32_t                            require_scope_resolution_when_present;
    uint32_t                            require_qualifier_resolution_when_present;
    uint32_t                            allow_primary_items;
    uint32_t                            allow_context_items;
    uint32_t                            context_item_parent_required;
    uint32_t                            minimum_distinct_source_spans;
    uint32_t                            minimum_distinct_retrieval_items;
    uint32_t                            minimum_distinct_documents;
    uint32_t                            minimum_distinct_bundles;
    evidence_duplicate_handling         duplicate_handling_policy;
    evidence_conflict_handling          conflict_handling_policy;
    evidence_unsupported_type_behavior  unsupported_type_behavior;
    uint32_t                            admission_limit;
    uint32_t                            policy_flags;
    hacf_digest                         policy_identity;
    uint8_t                             reserved[48];
} elpis_evidence_admission_policy_v1;

/* Initialize with P4 v1 default policy */
void elpis_admission_policy_init_default(elpis_evidence_admission_policy_v1 *policy);

/* Zero-initialize and set abi_version */
void elpis_admission_policy_init(elpis_evidence_admission_policy_v1 *policy);

/* Compute policy identity.
 * Domain: "elpis.semantic.evidence_admission_policy.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || allowed_typer_count(4 BE) || for each: digest(32)
 *             || allowed_claim_type_count(4 BE) || for each: type_id(4 BE)
 *             || allowed_relation_type_count(4 BE) || for each: type_id(4 BE)
 *             || minimum_claim_confidence_key(4 BE)
 *             || minimum_relation_confidence_key(4 BE)
 *             || maximum_claim_authority(4 BE) || maximum_relation_authority(4 BE)
 *             || minimum_source_authority(4 BE)
 *             || require_exact_span_validation(4 BE)
 *             || require_target_resolution(4 BE)
 *             || require_subject_resolution(4 BE)
 *             || require_scope_resolution_when_present(4 BE)
 *             || require_qualifier_resolution_when_present(4 BE)
 *             || allow_primary_items(4 BE) || allow_context_items(4 BE)
 *             || context_item_parent_required(4 BE)
 *             || minimum_distinct_source_spans(4 BE)
 *             || minimum_distinct_retrieval_items(4 BE)
 *             || minimum_distinct_documents(4 BE)
 *             || minimum_distinct_bundles(4 BE)
 *             || duplicate_handling_policy(4 BE)
 *             || conflict_handling_policy(4 BE)
 *             || unsupported_type_behavior(4 BE)
 *             || admission_limit(4 BE) || policy_flags(4 BE). */
int elpis_admission_policy_identity(const elpis_evidence_admission_policy_v1 *policy,
                                     hacf_digest *out);

/* Validate policy: nonzero reserved fields rejected, counts in range, etc. */
int elpis_admission_policy_validate(const elpis_evidence_admission_policy_v1 *policy);

/* Check if a typer profile is allowed */
int elpis_policy_allows_typer(const elpis_evidence_admission_policy_v1 *policy,
                               const hacf_digest *typer_digest);

/* Check if a claim type is allowed */
int elpis_policy_allows_claim_type(const elpis_evidence_admission_policy_v1 *policy,
                                    uint32_t claim_type);

/* Check if a relation type is allowed */
int elpis_policy_allows_relation_type(const elpis_evidence_admission_policy_v1 *policy,
                                       uint32_t relation_type);

#ifdef __cplusplus
}
#endif
#endif
