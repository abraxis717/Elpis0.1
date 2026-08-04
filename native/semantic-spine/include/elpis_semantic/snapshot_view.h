/* elpis_semantic/snapshot_view.h — Read-only snapshot view.
 *
 * Provides lookup and enumeration operations over an immutable snapshot.
 * Results are ordered canonically. Preserves the distinction between one
 * semantic object and multiple assertions of that object.
 */
#ifndef ELPIS_SEMANTIC_SNAPSHOT_VIEW_H
#define ELPIS_SEMANTIC_SNAPSHOT_VIEW_H

#include "elpis_semantic/snapshot.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct semantic_snapshot_view semantic_snapshot_view;

/* ───────────────────────────────────────────────────────────────────── */
/* View creation and destruction                                         */
/* ───────────────────────────────────────────────────────────────────── */

/* Create a read-only view over a snapshot manifest. */
semantic_snapshot_view *semantic_view_create(const semantic_snapshot_manifest *manifest);

/* Direct record injection for P0 (bypasses file I/O). Records are copied. */
void semantic_view_set_records(semantic_snapshot_view *view,
                                const elpis_semantic_node_v1 *nodes, uint32_t node_count,
                                const elpis_semantic_assertion_v1 *assertions, uint32_t assertion_count,
                                const elpis_semantic_hyperedge_v1 *hyperedges, uint32_t hyperedge_count,
                                const elpis_semantic_incidence_v1 *incidences, uint32_t incidence_count);

void semantic_view_destroy(semantic_snapshot_view *view);

/* ───────────────────────────────────────────────────────────────────── */
/* Node operations                                                       */
/* ───────────────────────────────────────────────────────────────────── */

/* Lookup node by identity digest. Returns NULL if not found. */
const elpis_semantic_node_v1 *semantic_view_lookup_node(
    const semantic_snapshot_view *view, const hacf_digest *node_identity);

/* Enumerate assertions for a node. Returns count placed in out (up to out_capacity).
 * Results ordered by (provenance, authority, flags). */
uint32_t semantic_view_node_assertions(
    const semantic_snapshot_view *view,
    const hacf_digest *node_identity,
    uint32_t min_authority,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_assertion_v1 **out, uint32_t out_capacity);

/* ───────────────────────────────────────────────────────────────────── */
/* Hyperedge operations                                                  */
/* ───────────────────────────────────────────────────────────────────── */

/* Lookup hyperedge by identity digest. */
const elpis_semantic_hyperedge_v1 *semantic_view_lookup_hyperedge(
    const semantic_snapshot_view *view, const hacf_digest *hyperedge_identity);

/* Enumerate assertions for a hyperedge. */
uint32_t semantic_view_hyperedge_assertions(
    const semantic_snapshot_view *view,
    const hacf_digest *hyperedge_identity,
    uint32_t min_authority,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_assertion_v1 **out, uint32_t out_capacity);

/* Enumerate participants of a hyperedge. Ordered canonically. */
uint32_t semantic_view_hyperedge_participants(
    const semantic_snapshot_view *view,
    const hacf_digest *hyperedge_identity,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_participant_descriptor **out, uint32_t out_capacity);

/* ───────────────────────────────────────────────────────────────────── */
/* Traversal operations                                                  */
/* ───────────────────────────────────────────────────────────────────── */

/* Enumerate hyperedges incident to a node (node is a participant).
 * Ordered by hyperedge identity digest. */
uint32_t semantic_view_node_hyperedges(
    const semantic_snapshot_view *view,
    const hacf_digest *node_identity,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_hyperedge_v1 **out, uint32_t out_capacity);

/* ───────────────────────────────────────────────────────────────────── */
/* Filtered enumeration                                                  */
/* ───────────────────────────────────────────────────────────────────── */

/* Filter nodes by type. Returns count placed. */
uint32_t semantic_view_enumerate_nodes_by_type(
    const semantic_snapshot_view *view,
    uint32_t node_type,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_node_v1 **out, uint32_t out_capacity);

/* Filter hyperedges by type. */
uint32_t semantic_view_enumerate_hyperedges_by_type(
    const semantic_snapshot_view *view,
    uint32_t hyperedge_type,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_hyperedge_v1 **out, uint32_t out_capacity);

/* Filter incidences by role. */
uint32_t semantic_view_enumerate_incidences_by_role(
    const semantic_snapshot_view *view,
    uint32_t incidence_role,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_incidence_v1 **out, uint32_t out_capacity);

/* Filter nodes/hyperedges by minimum authority (of their best assertion). */
uint32_t semantic_view_enumerate_nodes_by_authority(
    const semantic_snapshot_view *view,
    uint32_t min_authority,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_node_v1 **out, uint32_t out_capacity);

/* ───────────────────────────────────────────────────────────────────── */
/* Total counts                                                          */
/* ───────────────────────────────────────────────────────────────────── */

uint32_t semantic_view_total_nodes(const semantic_snapshot_view *view);
uint32_t semantic_view_total_hyperedges(const semantic_snapshot_view *view);
uint32_t semantic_view_total_assertions(const semantic_snapshot_view *view);
uint32_t semantic_view_total_incidences(const semantic_snapshot_view *view);

#ifdef __cplusplus
}
#endif
#endif
