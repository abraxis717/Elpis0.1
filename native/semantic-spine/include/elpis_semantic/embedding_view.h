/* elpis_semantic/embedding_view.h — Embedding-aware composed view extension.
 *
 * Extends the companion read-only view layer without changing P0 object
 * identities. Provides embedding reference resolution over composed views.
 */
#ifndef ELPIS_SEMANTIC_EMBEDDING_VIEW_H
#define ELPIS_SEMANTIC_EMBEDDING_VIEW_H

#include "elpis_semantic/query_overlay.h"
#include "elpis_semantic/embedding_collection.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ──────────────────────────────────────────────────────────────────── */
/* Embedding-aware composed view                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct embedding_composed_view {
    const semantic_snapshot_view      *base_view;
    const semantic_query_overlay      *overlay;
    hacf_digest                        policy_digest;
    const elpis_semantic_embedding_collection_v1 *collections;
    uint32_t                           col_count;
    /* Cached references indexed by semantic node */
    const elpis_semantic_embedding_ref_v1 *refs;
    uint32_t                           ref_count;
    hacf_digest                        composed_view_digest;
} embedding_composed_view;

/* Create an embedding-aware composed view.
 * base_view:     P0 snapshot view
 * overlay:       P0 query overlay (NULL for base-only view)
 * policy_digest: overlay policy digest
 * collections:   array of embedding collections attached to this view
 * col_count:     number of collections */
embedding_composed_view *embedding_composed_view_create(
    const semantic_snapshot_view *base_view,
    const semantic_query_overlay *overlay,
    const hacf_digest *policy_digest,
    const elpis_semantic_embedding_collection_v1 *collections,
    uint32_t col_count);

void embedding_composed_view_destroy(embedding_composed_view *view);

/* Get the P0 composed view digest (identity unchanged). */
int embedding_composed_view_digest(const embedding_composed_view *view, hacf_digest *out);

/* ──────────────────────────────────────────────────────────────────── */
/* Embedding reference resolution                                        */
/* ──────────────────────────────────────────────────────────────────── */

/* Get all embedding references for a semantic node.
 * Returns count placed in out_refs (up to out_capacity). */
uint32_t embedding_composed_view_node_refs(
    const embedding_composed_view *view,
    const hacf_digest *node_digest,
    const elpis_semantic_embedding_ref_v1 **out_refs,
    uint32_t out_capacity);

/* Get embedding references filtered by profile. */
uint32_t embedding_composed_view_node_refs_by_profile(
    const embedding_composed_view *view,
    const hacf_digest *node_digest,
    const hacf_digest *profile_digest,
    const elpis_semantic_embedding_ref_v1 **out_refs,
    uint32_t out_capacity);

/* Get embedding references filtered by authority (>= min). */
uint32_t embedding_composed_view_node_refs_by_authority(
    const embedding_composed_view *view,
    const hacf_digest *node_digest,
    uint32_t min_authority,
    const elpis_semantic_embedding_ref_v1 **out_refs,
    uint32_t out_capacity);

/* Get embedding references filtered by provenance digest. */
uint32_t embedding_composed_view_node_refs_by_provenance(
    const embedding_composed_view *view,
    const hacf_digest *node_digest,
    const hacf_digest *provenance_digest,
    const elpis_semantic_embedding_ref_v1 **out_refs,
    uint32_t out_capacity);

/* Get nodes referencing a specific vector. */
uint32_t embedding_composed_view_nodes_for_vector(
    const embedding_composed_view *view,
    const hacf_digest *vector_digest,
    hacf_digest *out_nodes,
    uint32_t out_capacity);

/* Get all nodes in the view with their embedding references. */
uint32_t embedding_composed_view_enumerate_embedded_nodes(
    const embedding_composed_view *view,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_node_v1 **out_nodes,
    uint32_t out_capacity);

/* Get collection identities attached to base snapshot. */
uint32_t embedding_composed_view_base_collection_count(const embedding_composed_view *view);
uint32_t embedding_composed_view_overlay_collection_count(const embedding_composed_view *view);

/* Get bound collections. Returns count placed in out (up to out_capacity). */
uint32_t embedding_composed_view_collections(
    const embedding_composed_view *view,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_embedding_collection_v1 **out,
    uint32_t out_capacity);

#ifdef __cplusplus
}
#endif
#endif
