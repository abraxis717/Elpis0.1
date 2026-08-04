/* snapshot_view.c — Read-only snapshot view with lookup and enumeration.
 *
 * Index nodes and hyperedges by identity digest for O(n) lookup.
 * All results are ordered canonically.
 */
#include "elpis_semantic/snapshot_view.h"
#include "view_internal.h"
#include <stdlib.h>
#include <string.h>

/* struct semantic_snapshot_view defined in view_internal.h */

/* Helper: binary search over sorted records by digest.
 * Returns index or (uint32_t)-1 if not found. */
static uint32_t find_node_by_digest(const elpis_semantic_node_v1 *nodes, uint32_t count,
                                     const hacf_digest *digest) {
    uint32_t lo = 0, hi = count;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        int c = memcmp(&nodes[mid].node_identity, digest, HACF_DIGEST_BYTES);
        if (c < 0) lo = mid + 1;
        else hi = mid;
    }
    if (lo < count && memcmp(&nodes[lo].node_identity, digest, HACF_DIGEST_BYTES) == 0)
        return lo;
    return (uint32_t)-1;
}

static uint32_t find_hyperedge_by_digest(const elpis_semantic_hyperedge_v1 *edges, uint32_t count,
                                          const hacf_digest *digest) {
    uint32_t lo = 0, hi = count;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        int c = memcmp(&edges[mid].hyperedge_identity, digest, HACF_DIGEST_BYTES);
        if (c < 0) lo = mid + 1;
        else hi = mid;
    }
    if (lo < count && memcmp(&edges[lo].hyperedge_identity, digest, HACF_DIGEST_BYTES) == 0)
        return lo;
    return (uint32_t)-1;
}

/* For P0, the view is built from a manifest that references segment files.
 * Since we don't have a full segment loading pipeline yet, we accept a
 * pre-built set of records. The snapshot_view_create function takes
 * record arrays that represent the merged snapshot content.
 *
 * TODO(P1): Build from segment files on disk for full persistence. */
semantic_snapshot_view *semantic_view_create(const semantic_snapshot_manifest *manifest) {
    if (!manifest) return NULL;
    semantic_snapshot_view *view = calloc(1, sizeof(*view));
    if (!view) return NULL;
    view->manifest = manifest;
    /* Records will be loaded via segment reading in P1.
     * For P0 testing, we provide a setter for direct injection. */
    return view;
}

/* Direct record injection for P0 testing (bypasses file I/O). */
void semantic_view_set_records(semantic_snapshot_view *view,
                                const elpis_semantic_node_v1 *nodes, uint32_t node_count,
                                const elpis_semantic_assertion_v1 *assertions, uint32_t assertion_count,
                                const elpis_semantic_hyperedge_v1 *hyperedges, uint32_t hyperedge_count,
                                const elpis_semantic_incidence_v1 *incidences, uint32_t incidence_count) {
    if (!view) return;

    /* Allocate and copy — view owns its data. */
    if (node_count) {
        view->nodes = malloc(node_count * sizeof(elpis_semantic_node_v1));
        if (view->nodes) memcpy(view->nodes, nodes, node_count * sizeof(elpis_semantic_node_v1));
    }
    view->node_count = node_count;

    if (assertion_count) {
        view->assertions = malloc(assertion_count * sizeof(elpis_semantic_assertion_v1));
        if (view->assertions) memcpy(view->assertions, assertions, assertion_count * sizeof(elpis_semantic_assertion_v1));
    }
    view->assertion_count = assertion_count;

    if (hyperedge_count) {
        view->hyperedges = malloc(hyperedge_count * sizeof(elpis_semantic_hyperedge_v1));
        if (view->hyperedges) memcpy(view->hyperedges, hyperedges, hyperedge_count * sizeof(elpis_semantic_hyperedge_v1));
    }
    view->hyperedge_count = hyperedge_count;

    if (incidence_count) {
        view->incidences = malloc(incidence_count * sizeof(elpis_semantic_incidence_v1));
        if (view->incidences) memcpy(view->incidences, incidences, incidence_count * sizeof(elpis_semantic_incidence_v1));
    }
    view->incidence_count = incidence_count;
}

void semantic_view_destroy(semantic_snapshot_view *view) {
    if (!view) return;
    free(view->nodes);
    free(view->assertions);
    free(view->hyperedges);
    free(view->incidences);
    free(view);
}

const elpis_semantic_node_v1 *semantic_view_lookup_node(
    const semantic_snapshot_view *view, const hacf_digest *node_identity) {
    if (!view || !node_identity) return NULL;
    uint32_t idx = find_node_by_digest(view->nodes, view->node_count, node_identity);
    if (idx == (uint32_t)-1) return NULL;
    return &view->nodes[idx];
}

uint32_t semantic_view_node_assertions(
    const semantic_snapshot_view *view,
    const hacf_digest *node_identity,
    uint32_t min_authority,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_assertion_v1 **out, uint32_t out_capacity) {
    if (!view || !node_identity || !out) return 0;
    *out = NULL;

    /* Find matching assertions. */
    uint32_t count = 0;
    for (uint32_t i = 0; i < view->assertion_count; i++) {
        const elpis_semantic_assertion_v1 *a = &view->assertions[i];
        if (a->asserted_object_kind != SEMANTIC_OBJECT_KIND_NODE) continue;
        if (memcmp(&a->asserted_object_digest, node_identity, HACF_DIGEST_BYTES) != 0) continue;
        if (a->authority < min_authority) continue;
        if (count < out_capacity) out[count] = &view->assertions[i];
        count++;
    }
    return count;
}

const elpis_semantic_hyperedge_v1 *semantic_view_lookup_hyperedge(
    const semantic_snapshot_view *view, const hacf_digest *hyperedge_identity) {
    if (!view || !hyperedge_identity) return NULL;
    uint32_t idx = find_hyperedge_by_digest(view->hyperedges, view->hyperedge_count, hyperedge_identity);
    if (idx == (uint32_t)-1) return NULL;
    return &view->hyperedges[idx];
}

uint32_t semantic_view_hyperedge_assertions(
    const semantic_snapshot_view *view,
    const hacf_digest *hyperedge_identity,
    uint32_t min_authority,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_assertion_v1 **out, uint32_t out_capacity) {
    if (!view || !hyperedge_identity || !out) return 0;
    *out = NULL;

    uint32_t count = 0;
    for (uint32_t i = 0; i < view->assertion_count; i++) {
        const elpis_semantic_assertion_v1 *a = &view->assertions[i];
        if (a->asserted_object_kind != SEMANTIC_OBJECT_KIND_HYPEREDGE) continue;
        if (memcmp(&a->asserted_object_digest, hyperedge_identity, HACF_DIGEST_BYTES) != 0) continue;
        if (a->authority < min_authority) continue;
        if (count < out_capacity) out[count] = &view->assertions[i];
        count++;
    }
    return count;
}

uint32_t semantic_view_hyperedge_participants(
    const semantic_snapshot_view *view,
    const hacf_digest *hyperedge_identity,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_participant_descriptor **out, uint32_t out_capacity) {
    if (!view || !hyperedge_identity || !out) return 0;
    *out = NULL;

    const elpis_semantic_hyperedge_v1 *edge = semantic_view_lookup_hyperedge(view, hyperedge_identity);
    if (!edge) return 0;

    uint32_t count = 0;
    for (uint32_t i = 0; i < edge->participant_count; i++) {
        if (count < out_capacity) out[count] = &edge->participants[i];
        count++;
    }
    return count;
}

uint32_t semantic_view_node_hyperedges(
    const semantic_snapshot_view *view,
    const hacf_digest *node_identity,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_hyperedge_v1 **out, uint32_t out_capacity) {
    if (!view || !node_identity || !out) return 0;
    *out = NULL;

    uint32_t count = 0;
    for (uint32_t i = 0; i < view->hyperedge_count; i++) {
        const elpis_semantic_hyperedge_v1 *e = &view->hyperedges[i];
        for (uint32_t j = 0; j < e->participant_count; j++) {
            if (memcmp(&e->participants[j].node_identity, node_identity, HACF_DIGEST_BYTES) == 0) {
                if (count < out_capacity) out[count] = e;
                count++;
                break; /* avoid duplicate if node appears multiple times */
            }
        }
    }
    return count;
}

uint32_t semantic_view_enumerate_nodes_by_type(
    const semantic_snapshot_view *view,
    uint32_t node_type,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_node_v1 **out, uint32_t out_capacity) {
    if (!view || !out) return 0;
    *out = NULL;

    uint32_t count = 0;
    for (uint32_t i = 0; i < view->node_count; i++) {
        if (view->nodes[i].node_type == node_type) {
            if (count < out_capacity) out[count] = &view->nodes[i];
            count++;
        }
    }
    return count;
}

uint32_t semantic_view_enumerate_hyperedges_by_type(
    const semantic_snapshot_view *view,
    uint32_t hyperedge_type,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_hyperedge_v1 **out, uint32_t out_capacity) {
    if (!view || !out) return 0;
    *out = NULL;

    uint32_t count = 0;
    for (uint32_t i = 0; i < view->hyperedge_count; i++) {
        if (view->hyperedges[i].hyperedge_type == hyperedge_type) {
            if (count < out_capacity) out[count] = &view->hyperedges[i];
            count++;
        }
    }
    return count;
}

uint32_t semantic_view_enumerate_incidences_by_role(
    const semantic_snapshot_view *view,
    uint32_t incidence_role,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_incidence_v1 **out, uint32_t out_capacity) {
    if (!view || !out) return 0;
    *out = NULL;

    uint32_t count = 0;
    for (uint32_t i = 0; i < view->incidence_count; i++) {
        if (view->incidences[i].incidence_role == incidence_role) {
            if (count < out_capacity) out[count] = &view->incidences[i];
            count++;
        }
    }
    return count;
}

uint32_t semantic_view_enumerate_nodes_by_authority(
    const semantic_snapshot_view *view,
    uint32_t min_authority,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_node_v1 **out, uint32_t out_capacity) {
    if (!view || !out) return 0;
    *out = NULL;

    uint32_t count = 0;
    for (uint32_t i = 0; i < view->node_count; i++) {
        /* Check if any assertion for this node has sufficient authority. */
        int has_auth = 0;
        for (uint32_t j = 0; j < view->assertion_count; j++) {
            const elpis_semantic_assertion_v1 *a = &view->assertions[j];
            if (a->asserted_object_kind != SEMANTIC_OBJECT_KIND_NODE) continue;
            if (memcmp(&a->asserted_object_digest, &view->nodes[i].node_identity, HACF_DIGEST_BYTES) != 0) continue;
            if (a->authority >= min_authority) { has_auth = 1; break; }
        }
        if (has_auth) {
            if (count < out_capacity) out[count] = &view->nodes[i];
            count++;
        }
    }
    return count;
}

uint32_t semantic_view_total_nodes(const semantic_snapshot_view *view) {
    return view ? view->node_count : 0;
}

uint32_t semantic_view_total_hyperedges(const semantic_snapshot_view *view) {
    return view ? view->hyperedge_count : 0;
}

uint32_t semantic_view_total_assertions(const semantic_snapshot_view *view) {
    return view ? view->assertion_count : 0;
}

uint32_t semantic_view_total_incidences(const semantic_snapshot_view *view) {
    return view ? view->incidence_count : 0;
}
