/* elpis_semantic/embedding_collection.h — Embedding-reference collections.
 *
 * An embedding-reference collection is an immutable attachment layer over one
 * exact semantic snapshot or query overlay. It binds profiles, vectors, and
 * references in canonical order. Collections are immutable — adding a reference
 * creates a new collection.
 *
 * Canonical order:
 *   1. profiles by profile digest
 *   2. vectors by vector digest
 *   3. references by (semantic_node_digest, profile_digest, provenance_digest,
 *      authority, reference_flags, vector_digest)
 */
#ifndef ELPIS_SEMANTIC_EMBEDDING_COLLECTION_H
#define ELPIS_SEMANTIC_EMBEDDING_COLLECTION_H

#include "elpis_semantic/embedding_ref.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EMBEDDING_COLLECTION_ABI_VERSION 1u
#define EMBEDDING_MAX_PROFILES     32u
#define EMBEDDING_MAX_VECTORS    8192u
#define EMBEDDING_MAX_REFERENCES 16384u

/* ──────────────────────────────────────────────────────────────────── */
/* Target kind                                                           */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum embedding_collection_target_kind {
    EMBEDDING_TARGET_BASE_SNAPSHOT = 1u,
    EMBEDDING_TARGET_QUERY_OVERLAY = 2u
} embedding_collection_target_kind;

/* ──────────────────────────────────────────────────────────────────── */
/* Collection identity                                                   */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_embedding_collection_v1 {
    uint32_t                                abi_version;
    embedding_collection_target_kind        target_kind;
    hacf_digest                             target_digest; /* snapshot or overlay digest */
    hacf_digest                             profile_digests[EMBEDDING_MAX_PROFILES];
    uint32_t                                profile_count;
    hacf_digest                             vector_digests[EMBEDDING_MAX_VECTORS];
    uint32_t                                vector_count;
    hacf_digest                             reference_digests[EMBEDDING_MAX_REFERENCES];
    uint32_t                                reference_count;
    hacf_digest                             collection_policy_digest;
    hacf_digest                             collection_identity;  /* computed digest */
    hacf_digest                             hacf_package_digest;  /* HACF package identity */
    uint8_t                                 reserved[32];          /* must be zero */
} elpis_semantic_embedding_collection_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Collection operations                                                 */
/* ──────────────────────────────────────────────────────────────────── */

/* Create a zeroed collection. */
elpis_semantic_embedding_collection_v1 *elpis_embedding_collection_create(void);
void elpis_embedding_collection_destroy(elpis_semantic_embedding_collection_v1 *col);

/* Add a profile digest to the collection (canonical order by digest).
 * Duplicate profiles silently collapse. */
int elpis_embedding_collection_add_profile(elpis_semantic_embedding_collection_v1 *col,
                                            const hacf_digest *profile_digest);

/* Add a vector digest (canonical order by digest). Duplicate vectors collapse. */
int elpis_embedding_collection_add_vector(elpis_semantic_embedding_collection_v1 *col,
                                           const hacf_digest *vector_digest);

/* Add a reference digest (canonical order by reference key).
 * Exact duplicate references collapse. Conflicting references are rejected. */
int elpis_embedding_collection_add_reference(elpis_semantic_embedding_collection_v1 *col,
                                              const hacf_digest *reference_digest);

/* Finalize and compute collection identity. Domain: "elpis.semantic.embedding_collection.v1"
 * Byte stream: domain_tag || abi_version(4 BE) || target_kind(4 BE)
 *             || target_digest(32)
 *             || profile_count(4 BE) || for each profile: digest(32)
 *             || vector_count(4 BE) || for each vector: digest(32)
 *             || reference_count(4 BE) || for each reference: digest(32)
 *             || collection_policy_digest(32). */
int elpis_embedding_collection_finalize(elpis_semantic_embedding_collection_v1 *col,
                                         hacf_digest *out);

/* Validate collection: known ABI, zero reserved, sorted digests,
 * profile/vector/reference counts within bounds. */
int elpis_embedding_collection_validate(const elpis_semantic_embedding_collection_v1 *col);

/* Compare two collections by identity digest. */
int elpis_embedding_collection_cmp(const elpis_semantic_embedding_collection_v1 *a,
                                    const elpis_semantic_embedding_collection_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
