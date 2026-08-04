/* elpis_semantic/evidence_relation_candidate.h — Relation candidate contract.
 *
 * A relation candidate proposes one typed semantic hyperedge.
 * P4 v1 relation types are explicit numeric registry entries.
 *
 * Identity domain: "elpis.semantic.relation_candidate.v1"
 */
#ifndef ELPIS_SEMANTIC_EVIDENCE_RELATION_CANDIDATE_H
#define ELPIS_SEMANTIC_EVIDENCE_RELATION_CANDIDATE_H

#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EVIDENCE_RELATION_CANDIDATE_ABI_VERSION 1u

/* P4 v1 semantic relation types — explicit numeric registry */
typedef enum evidence_relation_type {
    RELATION_TYPE_MENTIONS             = 100u,
    RELATION_TYPE_DEFINES              = 101u,
    RELATION_TYPE_SUPPORTS             = 102u,
    RELATION_TYPE_CONTRADICTS          = 103u,
    RELATION_TYPE_QUALIFIES            = 104u,
    RELATION_TYPE_LIMITS_SCOPE_OF      = 105u,
    RELATION_TYPE_PROVIDES_CONTEXT_FOR = 106u
} evidence_relation_type;

/* Relation polarity */
typedef enum evidence_relation_polarity {
    RELATION_POLARITY_AFFIRMATIVE  = 1u,
    RELATION_POLARITY_NEGATIVE     = 2u,
    RELATION_POLARITY_UNSPECIFIED  = 3u
} evidence_relation_polarity;

/* Evidence/target object kind for resolution */
typedef enum evidence_object_kind {
    OBJECT_KIND_NONE          = 0u,
    OBJECT_KIND_CLAIM_NODE    = 1u,
    OBJECT_KIND_HYPEREDGE     = 2u,
    OBJECT_KIND_EXISTING_NODE = 3u
} evidence_object_kind;

/* Relation role IDs */
typedef enum evidence_relation_role {
    RELATION_ROLE_NONE          = 0u,
    RELATION_ROLE_EVIDENCE      = 1u,
    RELATION_ROLE_TARGET        = 2u,
    RELATION_ROLE_QUALIFIER     = 3u,
    RELATION_ROLE_SCOPE         = 4u,
    RELATION_ROLE_ADDITIONAL    = 5u
} evidence_relation_role;

/* Candidate flags */
#define RELATION_CANDIDATE_FLAG_NONE  0u
#define RELATION_CANDIDATE_FLAG_MASK  0x01u

#define EVIDENCE_MAX_RELATION_PARTICIPANTS 16u
#define EVIDENCE_MAX_RELATION_SOURCE_SPANS 32u

typedef struct elpis_evidence_relation_participant {
    hacf_digest     object_digest;
    uint32_t        role;
    uint32_t        ordinal;
    uint8_t         reserved[16];
} elpis_evidence_relation_participant;

typedef struct elpis_evidence_relation_candidate_v1 {
    uint32_t                                      abi_version;
    hacf_digest                                   typer_profile_digest;
    evidence_relation_type                        relation_type;
    hacf_digest                                   evidence_claim_candidate_digest;
    evidence_object_kind                          evidence_object_kind;
    hacf_digest                                   evidence_object_digest;
    evidence_object_kind                          target_object_kind;
    hacf_digest                                   target_object_digest;
    uint32_t                                      evidence_role;
    uint32_t                                      target_role;
    elpis_evidence_relation_participant           additional_participants[EVIDENCE_MAX_RELATION_PARTICIPANTS];
    uint32_t                                      additional_participant_count;
    evidence_relation_polarity                    relation_polarity;
    hacf_digest                                   relation_scope_digest;
    hacf_digest                                   relation_qualifier_digest;
    hacf_digest                                   source_span_digests[EVIDENCE_MAX_RELATION_SOURCE_SPANS];
    uint32_t                                      source_span_count;
    uint32_t                                      confidence_key;
    uint32_t                                      candidate_flags;
    hacf_digest                                   candidate_identity;
    uint8_t                                       reserved[32];
} elpis_evidence_relation_candidate_v1;

/* Zero-initialize and set abi_version */
void elpis_relation_candidate_init(elpis_evidence_relation_candidate_v1 *candidate);

/* Compute candidate identity.
 * Domain: "elpis.semantic.relation_candidate.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || typer_profile_digest(32) || relation_type(4 BE)
 *             || evidence_claim_candidate_digest(32)
 *             || evidence_object_kind(4 BE) || evidence_object_digest(32)
 *             || target_object_kind(4 BE) || target_object_digest(32)
 *             || evidence_role(4 BE) || target_role(4 BE)
 *             || additional_participant_count(4 BE)
 *             || for each additional: object_digest(32) || role(4 BE) || ordinal(4 BE)
 *             || relation_polarity(4 BE) || relation_scope_digest(32)
 *             || relation_qualifier_digest(32)
 *             || source_span_count(4 BE) || for each span: digest(32)
 *             || confidence_key(4 BE) || candidate_flags(4 BE). */
int elpis_relation_candidate_identity(const elpis_evidence_relation_candidate_v1 *candidate,
                                       hacf_digest *out);

/* Validate: typer profile exists, relation type allowed, evidence/target objects
 * exist, roles allowed, cardinality satisfied, source spans exist, confidence in range,
 * no duplicate ordinal, no unresolved target, reserved zero. */
int elpis_relation_candidate_validate(const elpis_evidence_relation_candidate_v1 *candidate);

/* Check if a relation type is allowed in P4 v1 */
int elpis_relation_type_is_allowed(evidence_relation_type type);

/* Get allowed roles for a relation type */
uint32_t elpis_relation_allowed_roles(evidence_relation_type type,
                                       uint32_t *roles, uint32_t max_roles);

/* Compare candidates by identity */
int elpis_relation_candidate_cmp(const elpis_evidence_relation_candidate_v1 *a,
                                  const elpis_evidence_relation_candidate_v1 *b);

/* Compare for canonical ordering: relation_type, target_digest, evidence_digest, candidate_identity */
int elpis_relation_candidate_canonical_cmp(const elpis_evidence_relation_candidate_v1 *a,
                                            const elpis_evidence_relation_candidate_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
