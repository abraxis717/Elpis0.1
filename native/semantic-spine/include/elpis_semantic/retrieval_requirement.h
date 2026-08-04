/* elpis_semantic/retrieval_requirement.h — Retrieval requirement declaration.
 *
 * A retrieval requirement is a typed declaration of missing external context.
 * It is NOT an R3 query, NOT a RetrievalBundle, and contains no retrieved
 * evidence. It references only existing immutable identities.
 *
 * P2 does NOT generate query text or new embedding vectors.
 *
 * Identity domain: "elpis.semantic.retrieval_requirement.v1"
 */
#ifndef ELPIS_SEMANTIC_RETRIEVAL_REQUIREMENT_H
#define ELPIS_SEMANTIC_RETRIEVAL_REQUIREMENT_H

#include "elpis_semantic/context_requirement.h"
#include "elpis_semantic/context_deficit.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RETRIEVAL_REQUIREMENT_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Retrieval purpose code                                                */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum retrieval_purpose {
    RETRIEVAL_PURPOSE_OBJECT_LOOKUP    = 1,
    RETRIEVAL_PURPOSE_TYPE_COVERAGE    = 2,
    RETRIEVAL_PURPOSE_ASSERTION_SUPPORT = 3,
    RETRIEVAL_PURPOSE_EVIDENCE_RELATION = 4,
    RETRIEVAL_PURPOSE_EXTERNAL_CONTEXT  = 5,
    RETRIEVAL_PURPOSE_CONFLICT_RESOLUTION = 6
} retrieval_purpose;

/* ──────────────────────────────────────────────────────────────────── */
/* Query source kind                                                     */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum query_source_kind {
    SOURCE_OVERLAY      = 1,
    SOURCE_NODE         = 2,
    SOURCE_VECTOR       = 3,
    SOURCE_TEXT_OBJECT  = 4,
    SOURCE_OPAQUE       = 5
} query_source_kind;

/* ──────────────────────────────────────────────────────────────────── */
/* Retrieval requirement record                                          */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_retrieval_requirement_v1 {
    uint32_t                    abi_version;
    hacf_digest                 originating_requirement_digest;
    uint32_t                    deficit_reason;
    uint32_t                    retrieval_purpose;
    uint32_t                    target_object_kind;
    hacf_digest                 target_object_digest;
    uint32_t                    requested_semantic_type;
    hacf_digest                 requested_namespace_digest;
    uint32_t                    requested_min_authority;
    hacf_digest                 requested_embedding_profile_digest;
    uint32_t                    query_source_kind;
    hacf_digest                 query_source_digest;
    uint32_t                    requested_result_limit;
    uint32_t                    retrieval_flags;
    uint32_t                    requirement_priority_key;
    hacf_digest                 retrieval_identity;
    uint8_t                     reserved[32];
} elpis_semantic_retrieval_requirement_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Retrieval requirement operations                                      */
/* ──────────────────────────────────────────────────────────────────── */

/* Zero-initialize a retrieval requirement. Sets abi_version. */
void elpis_retrieval_requirement_init(
    elpis_semantic_retrieval_requirement_v1 *req);

/* Compute retrieval requirement identity.
 * Domain: "elpis.semantic.retrieval_requirement.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || originating_requirement_digest(32)
 *             || deficit_reason(4 BE)
 *             || retrieval_purpose(4 BE)
 *             || target_object_kind(4 BE)
 *             || target_object_digest(32)
 *             || requested_semantic_type(4 BE)
 *             || requested_namespace_digest(32)
 *             || requested_min_authority(4 BE)
 *             || requested_embedding_profile_digest(32)
 *             || query_source_kind(4 BE)
 *             || query_source_digest(32)
 *             || requested_result_limit(4 BE)
 *             || retrieval_flags(4 BE)
 *             || requirement_priority_key(4 BE). */
int elpis_retrieval_requirement_identity(
    const elpis_semantic_retrieval_requirement_v1 *req, hacf_digest *out);

/* Validate: known ABI, valid enums, zero reserved,
 * originating requirement digest non-zero, result_limit > 0. */
int elpis_retrieval_requirement_validate(
    const elpis_semantic_retrieval_requirement_v1 *req);

/* Check if two retrieval requirements are exact duplicates (same identity).
 * Returns 1 if duplicates, 0 if not, negative on error. */
int elpis_retrieval_requirement_is_duplicate(
    const elpis_semantic_retrieval_requirement_v1 *a,
    const elpis_semantic_retrieval_requirement_v1 *b);

/* Compare two retrieval requirements by priority (descending) then identity
 * digest (ascending) for canonical ordering. */
int elpis_retrieval_requirement_cmp(
    const elpis_semantic_retrieval_requirement_v1 *a,
    const elpis_semantic_retrieval_requirement_v1 *b);

/* Derive a retrieval requirement from a deficit result + requirement.
 * The caller must validate the output. */
int elpis_retrieval_requirement_from_deficit(
    const elpis_semantic_context_requirement_v1 *requirement,
    const elpis_semantic_requirement_result_v1  *result,
    const hacf_digest                            *query_overlay_digest,
    elpis_semantic_retrieval_requirement_v1      *out);

int elpis_write_retrieval_requirement(const char *path,
                                       const elpis_semantic_retrieval_requirement_v1 *req);
int elpis_read_retrieval_requirement(const char *path,
                                      elpis_semantic_retrieval_requirement_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
