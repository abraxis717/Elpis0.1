/* elpis_semantic/embedding_profile.h — Embedding profile identity.
 *
 * An embedding profile identifies the exact procedure under which vector bytes
 * were produced. The profile digest binds every field affecting vector
 * interpretation. No machine paths, no mutable provider handles.
 */
#ifndef ELPIS_SEMANTIC_EMBEDDING_PROFILE_H
#define ELPIS_SEMANTIC_EMBEDDING_PROFILE_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EMBEDDING_PROFILE_ABI_VERSION 1u
#define EMBEDDING_DIMENSION_CEILING   65536u

/* ──────────────────────────────────────────────────────────────────── */
/* Provider kind                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum embedding_provider_kind {
    EMBEDDING_PROVIDER_EXTERNAL_PRECOMPUTED = 1u,
    EMBEDDING_PROVIDER_LOCAL_DETERMINISTIC  = 2u,
    EMBEDDING_PROVIDER_REMOTE               = 3u,
    EMBEDDING_PROVIDER_IMPORTED_SEALED      = 4u
} embedding_provider_kind;

/* ──────────────────────────────────────────────────────────────────── */
/* Pooling policy                                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum embedding_pooling_policy {
    EMBEDDING_POOLING_NONE            = 1u,
    EMBEDDING_POOLING_CLS             = 2u,
    EMBEDDING_POOLING_MEAN            = 3u,
    EMBEDDING_POOLING_WEIGHTED_MEAN   = 4u,
    EMBEDDING_POOLING_LAST_TOKEN      = 5u,
    EMBEDDING_POOLING_PROVIDER_DEFINED = 6u
} embedding_pooling_policy;

/* ──────────────────────────────────────────────────────────────────── */
/* Normalization policy                                                  */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum embedding_normalization_policy {
    EMBEDDING_NORMALIZATION_NONE               = 1u,
    EMBEDDING_NORMALIZATION_UNIT_L2            = 2u,
    EMBEDDING_NORMALIZATION_PROVIDER_DEFINED   = 3u
} embedding_normalization_policy;

/* ──────────────────────────────────────────────────────────────────── */
/* Distance metric                                                       */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum embedding_distance_metric {
    EMBEDDING_METRIC_COSINE       = 1u,
    EMBEDDING_METRIC_INNER_PRODUCT = 2u,
    EMBEDDING_METRIC_SQUARED_L2   = 3u
} embedding_distance_metric;

/* ──────────────────────────────────────────────────────────────────── */
/* Vector dtype                                                          */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum embedding_vector_dtype {
    EMBEDDING_DTYPE_FLOAT32 = 1u
    /* P1: float32 only. Other dtypes must fail closed. */
} embedding_vector_dtype;

/* ──────────────────────────────────────────────────────────────────── */
/* Profile flags                                                         */
/* ──────────────────────────────────────────────────────────────────── */

#define EMBEDDING_PROFILE_FLAG_NONE  0u
#define EMBEDDING_PROFILE_FLAG_MASK  0xFFu

/* ──────────────────────────────────────────────────────────────────── */
/* Profile identity                                                      */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_embedding_profile_v1 {
    uint32_t                              abi_version;
    embedding_provider_kind               provider_kind;
    hacf_digest                           model_identity_digest;
    hacf_digest                           tokenizer_identity_digest;
    hacf_digest                           preprocessing_policy_digest;
    embedding_pooling_policy              pooling_policy;
    hacf_digest                           pooling_policy_digest; /* for provider-defined */
    embedding_normalization_policy        normalization_policy;
    hacf_digest                           normalization_policy_digest; /* for provider-defined */
    embedding_distance_metric             distance_metric;
    uint32_t                              dimensions;
    embedding_vector_dtype                vector_dtype;
    hacf_digest                           truncation_policy_digest;
    uint32_t                              profile_flags;
    hacf_digest                           profile_identity; /* computed digest */
    uint8_t                               reserved[48];      /* must be zero */
} elpis_semantic_embedding_profile_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Profile operations                                                    */
/* ──────────────────────────────────────────────────────────────────── */

/* Compute profile identity. Domain: "elpis.semantic.embedding_profile.v1"
 * Byte stream: domain_tag || abi_version(4 BE) || provider_kind(4 BE)
 *             || model_identity_digest(32) || tokenizer_identity_digest(32)
 *             || preprocessing_policy_digest(32)
 *             || pooling_policy(4 BE) || pooling_policy_digest(32)
 *             || normalization_policy(4 BE) || normalization_policy_digest(32)
 *             || distance_metric(4 BE) || dimensions(4 BE)
 *             || vector_dtype(4 BE) || truncation_policy_digest(32)
 *             || profile_flags(4 BE). */
int elpis_embedding_profile_identity(const elpis_semantic_embedding_profile_v1 *profile,
                                      hacf_digest *out);

/* Validate profile: known ABI, known enums, dimensions in [1, ceiling],
 * zero reserved, canonical digest fields. Returns SEMANTIC_OK or error. */
int elpis_semantic_embedding_profile_validate(const elpis_semantic_embedding_profile_v1 *profile);

/* Create zeroed profile. Caller must populate fields and call identity(). */
elpis_semantic_embedding_profile_v1 *elpis_embedding_profile_create(void);
void elpis_embedding_profile_destroy(elpis_semantic_embedding_profile_v1 *profile);

/* Compare two profiles by identity digest. */
int elpis_embedding_profile_cmp(const elpis_semantic_embedding_profile_v1 *a,
                                 const elpis_semantic_embedding_profile_v1 *b);

/* Check if two profiles are identical (same identity digest). Returns 1 if yes. */
int elpis_embedding_profile_is_same(const elpis_semantic_embedding_profile_v1 *a,
                                     const elpis_semantic_embedding_profile_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
