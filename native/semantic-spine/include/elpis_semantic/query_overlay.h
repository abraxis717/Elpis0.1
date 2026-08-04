/* elpis_semantic/query_overlay.h — Immutable per-query overlays.
 *
 * A query overlay is an immutable query-local semantic layer over one exact
 * base snapshot. It may introduce new nodes, hyperedges, and assertions, and
 * may reference base-snapshot nodes, but may never alter or delete base records.
 *
 * Composed view = base snapshot + overlay + policy, with deterministic digest.
 */
#ifndef ELPIS_SEMANTIC_QUERY_OVERLAY_H
#define ELPIS_SEMANTIC_QUERY_OVERLAY_H

#include "elpis_semantic/snapshot.h"
#include "elpis_semantic/snapshot_view.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SEMANTIC_OVERLAY_ABI_VERSION 1u
#define SEMANTIC_MAX_EXTERNAL_DEPS 16u

/* ───────────────────────────────────────────────────────────────────── */
/* Query overlay                                                         */
/* ───────────────────────────────────────────────────────────────────── */

typedef struct semantic_query_overlay {
    uint32_t              abi_version;
    hacf_digest           base_snapshot_manifest_digest;
    hacf_digest           base_hacf_graph_snapshot_digest;
    hacf_digest           query_digest;
    hacf_digest           query_local_segment_digest;
    hacf_digest           external_dependency_digests[SEMANTIC_MAX_EXTERNAL_DEPS];
    uint32_t              external_dependency_count;
    hacf_digest           overlay_policy_digest;
    hacf_digest           overlay_identity;
    /* Builder for query-local records */
    semantic_hypergraph_builder *local_builder;
    uint8_t               reserved[32];
} semantic_query_overlay;

/* ───────────────────────────────────────────────────────────────────── */
/* Overlay operations                                                    */
/* ───────────────────────────────────────────────────────────────────── */

/* Create overlay over a base snapshot. query_digest is the SHA-256 of the query. */
semantic_query_overlay *semantic_overlay_create(
    const semantic_snapshot_manifest *base_manifest,
    const semantic_type_registry *registry,
    const hacf_digest *query_digest);
void semantic_overlay_destroy(semantic_query_overlay *overlay);

/* Add query-local records to the overlay. These follow the same validation
 * as the base builder, but nodes referenced in hyperedges may exist either
 * in the overlay's local builder OR in the base snapshot. */
int semantic_overlay_add_node(semantic_query_overlay *overlay,
                               const elpis_semantic_node_v1 *node);
int semantic_overlay_add_hyperedge(semantic_query_overlay *overlay,
                                    const elpis_semantic_hyperedge_v1 *edge);
int semantic_overlay_add_assertion(semantic_query_overlay *overlay,
                                    const elpis_semantic_assertion_v1 *assertion);
int semantic_overlay_add_incidence(semantic_query_overlay *overlay,
                                    const elpis_semantic_incidence_v1 *incidence);

/* Add opaque external dependency digest. In P0 these are identity-only. */
int semantic_overlay_add_external_dependency(semantic_query_overlay *overlay,
                                              const hacf_digest *dep_digest);

/* Finalize overlay — compute overlay identity. Domain: "elpis.semantic.overlay.v1" */
int semantic_overlay_finalize(semantic_query_overlay *overlay);

/* ───────────────────────────────────────────────────────────────────── */
/* Composed view                                                         */
/* ───────────────────────────────────────────────────────────────────── */

/* A composed view binds base snapshot + overlay + policy into a single
 * read-only view. Domain: "elpis.semantic.composed_view.v1" */

typedef struct semantic_composed_view semantic_composed_view;

/* Create composed view. policy_digest is the SHA-256 of the overlay policy. */
semantic_composed_view *semantic_composed_view_create(
    const semantic_snapshot_view *base_view,
    const semantic_query_overlay *overlay,
    const hacf_digest *policy_digest);
void semantic_composed_view_destroy(semantic_composed_view *view);

/* Composed view digest — deterministic from base, overlay, and policy. */
int semantic_composed_view_digest(const semantic_composed_view *view, hacf_digest *out);

/* Lookup operations — overlay records shadow base records of the same identity.
 * If an overlay node has the same identity as a base node, the overlay's
 * version takes precedence (but base is never altered). */
const elpis_semantic_node_v1 *semantic_composed_view_lookup_node(
    const semantic_composed_view *view, const hacf_digest *node_identity);
const elpis_semantic_hyperedge_v1 *semantic_composed_view_lookup_hyperedge(
    const semantic_composed_view *view, const hacf_digest *hyperedge_identity);

/* Enumerate all nodes (base + overlay merged, overlay shadows base by identity). */
uint32_t semantic_composed_view_enumerate_nodes(
    const semantic_composed_view *view,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_node_v1 **out, uint32_t out_capacity);

uint32_t semantic_composed_view_total_nodes(const semantic_composed_view *view);
uint32_t semantic_composed_view_total_hyperedges(const semantic_composed_view *view);

/* Get base and overlay identities from the composed view. */
int semantic_composed_view_base_identity(const semantic_composed_view *view, hacf_digest *out);
int semantic_composed_view_overlay_identity(const semantic_composed_view *view, hacf_digest *out);

#ifdef __cplusplus
}
#endif
#endif
