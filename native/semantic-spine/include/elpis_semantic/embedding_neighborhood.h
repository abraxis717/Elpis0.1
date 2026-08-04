/* elpis_semantic/embedding_neighborhood.h — Bounded semantic-neighborhood views.
 *
 * A semantic-neighborhood view is a deterministic metric observation over a
 * bounded set of semantic nodes sharing one exact embedding profile.
 *
 * This is an immutable derived view. It does not create semantic edges,
 * mutate the hypergraph, or persist SEMANTICALLY_NEAR as an admitted relation.
 */
#ifndef ELPIS_SEMANTIC_EMBEDDING_NEIGHBORHOOD_H
#define ELPIS_SEMANTIC_EMBEDDING_NEIGHBORHOOD_H

#include "elpis_semantic/embedding_metric.h"
#include "elpis_semantic/embedding_ref.h"
#include "elpis_semantic/embedding_collection.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EMBEDDING_NEIGHBORHOOD_ABI_VERSION 1u
#define EMBEDDING_MAX_NEIGHBORHOOD_RESULTS 1024u

/* ──────────────────────────────────────────────────────────────────── */
/* Neighborhood result entry                                             */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct embedding_neighborhood_entry {
    hacf_digest     semantic_node_digest;
    hacf_digest     embedding_ref_digest;
    hacf_digest     embedding_vector_digest;
    int64_t         score_key;
    double          raw_score;
    uint32_t        authority;
    hacf_digest     provenance_digest;
    uint32_t        rank;             /* 1-based deterministic rank */
} embedding_neighborhood_entry;

/* ──────────────────────────────────────────────────────────────────── */
/* Neighborhood query parameters                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct embedding_neighborhood_query {
    hacf_digest     profile_digest;       /* exact embedding profile */
    hacf_digest     query_vector_digest;  /* query vector (or source node's vector) */
    const uint8_t   *query_vector_bytes;  /* canonical bytes of query vector */
    uint32_t        query_vector_dimensions;
    uint32_t        min_authority;
    hacf_digest     provenance_filter;    /* all-zero = no filter */
    uint32_t        node_type_filter;     /* zero = no filter */
    uint32_t        offset;
    uint32_t        limit;
    hacf_digest     neighborhood_policy_digest;
    uint8_t         reserved[32];
} embedding_neighborhood_query;

/* ──────────────────────────────────────────────────────────────────── */
/* Neighborhood view identity                                            */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_embedding_neighborhood_v1 {
    uint32_t                                abi_version;
    hacf_digest                             query_vector_digest;
    hacf_digest                             profile_digest;
    hacf_digest                             target_view_digest;     /* composed view digest */
    hacf_digest                             collection_identities[EMBEDDING_MAX_PROFILES]; /* bound collections */
    uint32_t                                collection_count;
    hacf_digest                             neighborhood_policy_digest;
    embedding_neighborhood_entry            results[EMBEDDING_MAX_NEIGHBORHOOD_RESULTS];
    uint32_t                                result_count;
    hacf_digest                             neighborhood_identity;  /* computed digest */
    uint8_t                                 reserved[32];
} elpis_semantic_embedding_neighborhood_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Neighborhood operations                                               */
/* ──────────────────────────────────────────────────────────────────── */

/* Create a zeroed neighborhood view. */
elpis_semantic_embedding_neighborhood_v1 *elpis_embedding_neighborhood_create(void);
void elpis_embedding_neighborhood_destroy(elpis_semantic_embedding_neighborhood_v1 *nb);

/* Resolve a neighborhood view. This is the core operation:
 *
 * Given the composed view data (nodes + embedding references), profile, and
 * query, compute the bounded neighborhood.
 *
 * composed_view_nodes: array of node digests in the composed view
 * composed_node_count: total nodes
 * refs:                array of embedding references
 * ref_count:           total references
 * profile:             the exact embedding profile
 * query:               the neighborhood query parameters
 * out_neighborhood:    filled with the neighborhood view
 *
 * Returns SEMANTIC_OK or error.
 *
 * Canonical ranking:
 *   Similarity metrics: higher score_key first, then smaller node digest, then smaller ref digest.
 *   Distance metrics: lower distance key first, then smaller node digest, then smaller ref digest.
 *
 * Duplicate-node resolution: retain highest-authority reference per node, then best score,
 * then lexicographically smallest reference digest. */
int elpis_embedding_resolve_neighborhood(
    const hacf_digest *composed_view_nodes, uint32_t composed_node_count,
    const elpis_semantic_embedding_ref_v1 *refs, uint32_t ref_count,
    const elpis_semantic_embedding_vector_v1 *vectors, uint32_t vector_count,
    const uint8_t **vector_bytes, /* parallel array of canonical bytes */
    const elpis_semantic_embedding_profile_v1 *profile,
    const embedding_neighborhood_query *query,
    elpis_semantic_embedding_neighborhood_v1 *out_neighborhood);

/* Compute neighborhood identity. Domain: "elpis.semantic.embedding_neighborhood.v1" */
int elpis_embedding_neighborhood_identity(
    const elpis_semantic_embedding_neighborhood_v1 *nb, hacf_digest *out);

/* Validate neighborhood view. */
int elpis_embedding_neighborhood_validate(const elpis_semantic_embedding_neighborhood_v1 *nb);

#ifdef __cplusplus
}
#endif
#endif
