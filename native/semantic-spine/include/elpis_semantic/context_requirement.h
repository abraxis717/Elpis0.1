/* elpis_semantic/context_requirement.h — Context requirement specification.
 *
 * A context requirement declares what must be present in a composed view
 * (base snapshot + query overlay + embedding collections) for a semantic
 * query to produce a complete, trustworthy result.
 *
 * Each requirement targets one object kind, references one requirement type,
 * and carries an extensible policy blob (extension_bytes) that encodes type-
 * specific parameters via one of the context_*_ext structs below.
 *
 * Requirement identity is deterministic: domain_tag || abi_version ||
 * requirement_type || requirement_level || target_object_kind ||
 * target_object_digest || requirement_policy_digest ||
 * minimum_authority || requirement_flags || extension_size || extension_bytes.
 *
 * No timestamps, file paths, or process IDs enter identity.
 */
#ifndef ELPIS_SEMANTIC_CONTEXT_REQUIREMENT_H
#define ELPIS_SEMANTIC_CONTEXT_REQUIREMENT_H

#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CONTEXT_REQUIREMENT_ABI_VERSION 1u
#define CONTEXT_MAX_EXTENSION_BYTES     128

/* ──────────────────────────────────────────────────────────────────── */
/* Requirement level                                                     */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum semantic_requirement_level {
    MANDATORY  = 1,
    PREFERRED  = 2,
    DIAGNOSTIC = 3
} semantic_requirement_level;

/* ──────────────────────────────────────────────────────────────────── */
/* Target object kind                                                    */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum semantic_target_object_kind {
    KIND_GLOBAL           = 0,
    KIND_NODE             = 1,
    KIND_HYPEREDGE        = 2,
    KIND_QUERY_OVERLAY    = 3,
    KIND_COMPOSED_VIEW    = 4,
    KIND_EMBEDDING_VECTOR = 5
} semantic_target_object_kind;

/* ──────────────────────────────────────────────────────────────────── */
/* Requirement type                                                      */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum semantic_requirement_type {
    TYPE_OBJECT_PRESENT                = 1,
    TYPE_TYPE_COVERAGE                 = 2,
    TYPE_ASSERTION_COVERAGE            = 3,
    TYPE_ROLE_COMPLETENESS             = 4,
    TYPE_EVIDENCE_RELATION_COVERAGE    = 5,
    TYPE_EMBEDDING_REFERENCE_COVERAGE  = 6,
    TYPE_EMBEDDING_NEIGHBORHOOD_COVERAGE = 7,
    TYPE_EXPLICIT_EXTERNAL_CONTEXT     = 8,
    TYPE_CONFLICT_EVIDENCE_COVERAGE    = 9,
    TYPE_OPAQUE_APPLICATION            = 10
} semantic_requirement_type;

/* ──────────────────────────────────────────────────────────────────── */
/* Deficit reason                                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum semantic_deficit_reason {
    DEF_NONE                                = 0,
    DEF_OBJECT_ABSENT                       = 1,
    DEF_TYPE_COVERAGE_BELOW_MIN             = 2,
    DEF_TYPE_COVERAGE_ABOVE_MAX             = 3,
    DEF_ASSERTION_COUNT_BELOW_MIN           = 4,
    DEF_PROVENANCE_DIVERSITY_BELOW_MIN      = 5,
    DEF_AUTHORITY_BELOW_MIN                 = 6,
    DEF_REQUIRED_ROLE_ABSENT                = 7,
    DEF_ROLE_CARDINALITY_INSUFFICIENT       = 8,
    DEF_ROLE_CARDINALITY_EXCESS             = 26,
    DEF_ORDERED_ROLE_GAP                    = 9,
    DEF_EVIDENCE_RELATION_ABSENT            = 10,
    DEF_EVIDENCE_COUNT_BELOW_MIN            = 11,
    DEF_EVIDENCE_PROVENANCE_BELOW_MIN       = 12,
    DEF_EVIDENCE_NODE_COUNT_BELOW_MIN       = 27,
    DEF_EVIDENCE_AUTHORITY_BELOW_MIN        = 28,
    DEF_EMBEDDING_REFERENCE_ABSENT          = 13,
    DEF_EMBEDDING_REFERENCE_AUTHORITY_INSUFFICIENT = 14,
    DEF_EMBEDDING_REFERENCE_COUNT_BELOW_MIN = 29,
    DEF_NO_ELIGIBLE_NEIGHBORS               = 15,
    DEF_NEIGHBOR_COUNT_BELOW_MIN            = 16,
    DEF_BEST_SCORE_BELOW_MIN                = 17,
    DEF_KTH_SCORE_BELOW_MIN                 = 18,
    DEF_EXTERNAL_CONTEXT_REQUIRED           = 19,
    DEF_UNRESOLVED_TYPED_CONFLICT           = 20,
    DEF_CONFLICT_RESOLUTION_INSUFFICIENT    = 21,
    DEF_CONFLICT_RESOLUTION_EVIDENCE_INSUFFICIENT = 30,
    DEF_CONFLICT_RESOLUTION_PROVENANCE_INSUFFICIENT = 31,
    DEF_EVALUATION_BLOCKED_UNKNOWN          = 22,
    DEF_EVALUATION_BLOCKED_INVALID_REF      = 23,
    DEF_EVALUATION_BLOCKED_VIEW_MISMATCH    = 24,
    DEF_EVALUATION_BLOCKED_PROFILE_MISMATCH = 25,
    DEF_EVALUATION_BLOCKED_MISSING_COLLECTION = 32,
    DEF_EVALUATION_BLOCKED_NEIGHBORHOOD_POLICY_MISMATCH = 33
} semantic_deficit_reason;

/* ──────────────────────────────────────────────────────────────────── */
/* Context requirement record                                            */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_context_requirement_v1 {
    uint32_t                          abi_version;
    semantic_requirement_type         requirement_type;
    semantic_requirement_level        requirement_level;
    semantic_target_object_kind       target_object_kind;
    hacf_digest                       target_object_digest;
    hacf_digest                       requirement_policy_digest;
    uint32_t                          minimum_authority;
    uint32_t                          requirement_flags;
    uint32_t                          extension_size;
    uint8_t                           extension_bytes[CONTEXT_MAX_EXTENSION_BYTES];
    hacf_digest                       requirement_identity;
    uint8_t                           reserved[32];
} elpis_semantic_context_requirement_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Extension structs — packed into extension_bytes per requirement type  */
/* ──────────────────────────────────────────────────────────────────── */

/* TYPE_OBJECT_PRESENT */
typedef struct context_object_present_ext {
    uint32_t       required_object_kind;
    hacf_digest    required_object_digest;
} context_object_present_ext;

/* TYPE_TYPE_COVERAGE */
typedef struct context_type_coverage_ext {
    uint32_t       object_kind;
    uint32_t       semantic_type;
    uint32_t       minimum_count;
    uint32_t       maximum_count;
    uint32_t       min_authority;
    hacf_digest    provenance_policy_digest;
} context_type_coverage_ext;

/* TYPE_ASSERTION_COVERAGE */
typedef struct context_assertion_coverage_ext {
    hacf_digest    asserted_object_digest;
    uint32_t       min_assertion_count;
    uint32_t       min_distinct_provenance_count;
    uint32_t       min_authority;
    uint32_t       allowed_flag_mask;
    uint32_t       forbidden_flag_mask;
} context_assertion_coverage_ext;

/* TYPE_ROLE_COMPLETENESS */
typedef struct context_role_completeness_ext {
    hacf_digest    hyperedge_digest;
    uint32_t       role_id;
    uint32_t       min_role_count;
    uint32_t       max_role_count;
    uint32_t       ordered_role_policy;
} context_role_completeness_ext;

/* TYPE_EVIDENCE_RELATION_COVERAGE */
typedef struct context_evidence_relation_ext {
    hacf_digest    target_object_digest;
    uint32_t       allowed_evidence_types[4];
    uint32_t       allowed_target_roles[4];
    uint32_t       allowed_evidence_roles[4];
    uint32_t       type_count;
    uint32_t       min_relation_count;
    uint32_t       min_distinct_evidence_nodes;
    uint32_t       min_distinct_provenance;
    uint32_t       min_authority;
} context_evidence_relation_ext;

/* TYPE_EMBEDDING_REFERENCE_COVERAGE */
typedef struct context_embedding_reference_ext {
    hacf_digest    semantic_node_digest;
    hacf_digest    embedding_profile_digest;
    uint32_t       min_reference_count;
    uint32_t       min_authority;
    hacf_digest    provenance_filter_digest;
    uint32_t       required_flag_mask;
    uint32_t       forbidden_flag_mask;
} context_embedding_reference_ext;

/* TYPE_EMBEDDING_NEIGHBORHOOD_COVERAGE */
typedef struct context_embedding_neighborhood_ext {
    uint32_t       source_kind;
    hacf_digest    source_digest;
    hacf_digest    embedding_profile_digest;
    uint32_t       candidate_node_type_filter;
    uint32_t       min_authority;
    hacf_digest    provenance_filter_digest;
    uint32_t       min_eligible_neighbor_count;
    int64_t        min_best_score_key;
    int64_t        min_kth_score_key;
    hacf_digest    neighborhood_policy_digest;
} context_embedding_neighborhood_ext;

/* TYPE_EXPLICIT_EXTERNAL_CONTEXT */
typedef struct context_external_context_ext {
    uint32_t       external_context_class;
    hacf_digest    requested_target_digest;
    hacf_digest    requested_namespace_digest;
    uint32_t       requested_authority_floor;
    uint32_t       retrieval_purpose_code;
    hacf_digest    query_construction_policy_digest;
} context_external_context_ext;

/* TYPE_CONFLICT_EVIDENCE_COVERAGE */
typedef struct context_conflict_evidence_ext {
    hacf_digest    target_object_digest;
    uint32_t       conflict_hyperedge_types[4];
    uint32_t       resolution_hyperedge_types[4];
    uint32_t       type_count;
    uint32_t       min_resolution_count;
    uint32_t       min_distinct_provenance;
    uint32_t       min_authority;
} context_conflict_evidence_ext;

/* TYPE_OPAQUE_APPLICATION */
typedef struct context_opaque_application_ext {
    hacf_digest    evaluator_policy_digest;
    uint32_t       opaque_type_id;
    uint8_t        opaque_data[64];
} context_opaque_application_ext;

/* ──────────────────────────────────────────────────────────────────── */
/* Requirement operations                                                */
/* ──────────────────────────────────────────────────────────────────── */

/* Zero-initialize a context requirement. Sets abi_version. */
void elpis_context_requirement_init(elpis_semantic_context_requirement_v1 *req);

/* Compute requirement identity digest. Domain: "elpis.semantic.context_requirement.v1"
 * Byte stream: domain_tag || abi_version(4 BE) || requirement_type(4 BE)
 *             || requirement_level(4 BE) || target_object_kind(4 BE)
 *             || target_object_digest(32) || requirement_policy_digest(32)
 *             || minimum_authority(4 BE) || requirement_flags(4 BE)
 *             || extension_size(4 BE) || extension_bytes[extension_size]. */
int elpis_context_requirement_identity(
    const elpis_semantic_context_requirement_v1 *req, hacf_digest *out);

/* Validate requirement: known ABI, valid enums, zero reserved,
 * extension_size <= CONTEXT_MAX_EXTENSION_BYTES. */
int elpis_context_requirement_validate(
    const elpis_semantic_context_requirement_v1 *req);

/* Check if two requirements are exact duplicates (same identity digest).
 * Returns 1 if duplicates, 0 if not, negative on error. */
int elpis_context_requirement_is_duplicate(
    const elpis_semantic_context_requirement_v1 *a,
    const elpis_semantic_context_requirement_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
