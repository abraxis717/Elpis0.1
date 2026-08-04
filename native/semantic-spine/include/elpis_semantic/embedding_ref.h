/* elpis_semantic/embedding_ref.h — Node-to-embedding reference identity.
 *
 * An embedding reference is an attachment to a semantic node. It is not part
 * of semantic-node identity. Multiple embedding references may exist for one
 * node when profiles, provenance, authority, or flags differ.
 *
 * The reference identity binds: semantic node, embedding profile, vector,
 * provenance, authority, and reference flags.
 */
#ifndef ELPIS_SEMANTIC_EMBEDDING_REF_H
#define ELPIS_SEMANTIC_EMBEDDING_REF_H

#include "elpis_semantic/embedding_profile.h"
#include "elpis_semantic/embedding_vector.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EMBEDDING_REF_ABI_VERSION 1u

/* Reference flags. */
#define EMBEDDING_REF_FLAG_NONE      0u
#define EMBEDDING_REF_FLAG_PRIMARY   0x01u  /* primary reference for this node */
#define EMBEDDING_REF_FLAG_MASK      0xFFu

/* Authority levels for embedding references. */
#define EMBEDDING_AUTH_ADVISORY   0u
#define EMBEDDING_AUTH_REFERENCE  1u
#define EMBEDDING_AUTH_CANONICAL  2u
#define EMBEDDING_AUTH_SYSTEM     3u

/* ──────────────────────────────────────────────────────────────────── */
/* Embedding reference identity                                          */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_embedding_ref_v1 {
    uint32_t        abi_version;
    hacf_digest     semantic_node_digest;
    hacf_digest     embedding_profile_digest;
    hacf_digest     embedding_vector_digest;
    uint32_t        reference_flags;
    hacf_digest     provenance_digest;
    uint32_t        authority;
    hacf_digest     ref_identity;       /* computed digest */
    uint8_t         reserved[32];       /* must be zero */
} elpis_semantic_embedding_ref_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Reference operations                                                  */
/* ──────────────────────────────────────────────────────────────────── */

/* Compute reference identity. Domain: "elpis.semantic.embedding_ref.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || semantic_node_digest(32)
 *             || embedding_profile_digest(32)
 *             || embedding_vector_digest(32)
 *             || reference_flags(4 BE)
 *             || provenance_digest(32)
 *             || authority(4 BE). */
int elpis_embedding_ref_identity(const elpis_semantic_embedding_ref_v1 *ref,
                                  hacf_digest *out);

/* Create a zeroed reference. */
elpis_semantic_embedding_ref_v1 *elpis_embedding_ref_create(void);
void elpis_embedding_ref_destroy(elpis_semantic_embedding_ref_v1 *ref);

/* Validate reference: known ABI, zero reserved, valid authority,
 * non-zero digests (except all-zero provenance for system refs is OK if
 * authority >= EMBEDDING_AUTH_SYSTEM). */
int elpis_embedding_ref_validate(const elpis_semantic_embedding_ref_v1 *ref);

/* Compare references by (semantic_node_digest, profile_digest, provenance_digest,
 * authority, reference_flags, vector_digest). */
int elpis_embedding_ref_cmp(const elpis_semantic_embedding_ref_v1 *a,
                             const elpis_semantic_embedding_ref_v1 *b);

/* Check if two references are exact duplicates (same identity). */
int elpis_embedding_ref_is_duplicate(const elpis_semantic_embedding_ref_v1 *a,
                                      const elpis_semantic_embedding_ref_v1 *b);

/* Check if two references conflict: same node + profile + provenance + authority
 * + flags but different vector. Conflicts must be rejected on admission. */
int elpis_embedding_ref_is_conflict(const elpis_semantic_embedding_ref_v1 *a,
                                     const elpis_semantic_embedding_ref_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
