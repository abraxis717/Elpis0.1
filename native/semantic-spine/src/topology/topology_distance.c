/* topology_distance.c — Integer shortest-path distances via deterministic multi-source Dijkstra. */
#include "elpis_semantic/topology_constellation.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>
#include <limits.h>

/* Internal priority queue for Dijkstra */
typedef struct {
    uint32_t cost;
    uint32_t hops;
    uint32_t anchor_priority;
    hacf_digest anchor_digest;
    hacf_digest vertex_digest;
    hacf_digest pred_vertex;
    hacf_digest pred_incidence;
} dijkstra_entry_t;

static int dijkstra_cmp(const dijkstra_entry_t *a, const dijkstra_entry_t *b) {
    if (a->cost != b->cost) return (a->cost < b->cost) ? -1 : 1;
    if (a->hops != b->hops) return (a->hops < b->hops) ? -1 : 1;
    if (a->anchor_priority != b->anchor_priority)
        return (a->anchor_priority < b->anchor_priority) ? -1 : 1;
    int d = memcmp(&a->anchor_digest, &b->anchor_digest, HACF_DIGEST_BYTES);
    if (d != 0) return d;
    d = memcmp(&a->vertex_digest, &b->vertex_digest, HACF_DIGEST_BYTES);
    if (d != 0) return d;
    d = memcmp(&a->pred_vertex, &b->pred_vertex, HACF_DIGEST_BYTES);
    if (d != 0) return d;
    return memcmp(&a->pred_incidence, &b->pred_incidence, HACF_DIGEST_BYTES);
}

/* Simple min-heap for Dijkstra priority queue */
#define DIJKSTRA_MAX 4096
typedef struct {
    dijkstra_entry_t entries[DIJKSTRA_MAX];
    uint32_t size;
} dijkstra_heap_t;

static void heap_push(dijkstra_heap_t *h, dijkstra_entry_t e) {
    uint32_t i = h->size++;
    h->entries[i] = e;
    while (i > 0) {
        uint32_t parent = (i - 1) / 2;
        if (dijkstra_cmp(&h->entries[i], &h->entries[parent]) >= 0) break;
        dijkstra_entry_t tmp = h->entries[i];
        h->entries[i] = h->entries[parent];
        h->entries[parent] = tmp;
        i = parent;
    }
}

static dijkstra_entry_t heap_pop(dijkstra_heap_t *h) {
    dijkstra_entry_t top = h->entries[0];
    h->size--;
    if (h->size > 0) {
        h->entries[0] = h->entries[h->size];
        uint32_t i = 0;
        while (1) {
            uint32_t left = 2 * i + 1, right = 2 * i + 2, best = i;
            if (left < h->size && dijkstra_cmp(&h->entries[left], &h->entries[best]) < 0)
                best = left;
            if (right < h->size && dijkstra_cmp(&h->entries[right], &h->entries[best]) < 0)
                best = right;
            if (best == i) break;
            dijkstra_entry_t tmp = h->entries[i];
            h->entries[i] = h->entries[best];
            h->entries[best] = tmp;
            i = best;
        }
    }
    return top;
}

int elpis_topology_compute_distances(
    elpis_semantic_topology_constellations_v1 *constellations,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_relation_registry_v1 *registry,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_anchors_v1 *anchors) {
    if (!constellations || !policy || !registry || !graph || !anchors)
        return SEMANTIC_E_INVAL;

    /* For each anchor, run Dijkstra from the anchor vertex */
    uint32_t record_idx = 0;

    for (uint32_t a = 0; a < anchors->anchor_count; a++) {
        const topology_anchor_v1 *anchor = &anchors->anchors[a];
        hacf_digest anchor_id;
        elpis_topology_anchor_identity(anchor, &anchor_id);

        /* Build adjacency: node vertices are connected via hyperedge vertices */
        /* Each incidence provides a path node -> hyperedge -> node with the hyperedge's cost */

        /* Dijkstra state */
        uint32_t best_cost[TOPOLOGY_DEFAULT_MAX_VERTICES];
        uint32_t best_hops[TOPOLOGY_DEFAULT_MAX_VERTICES];
        uint32_t visited[TOPOLOGY_DEFAULT_MAX_VERTICES];
        memset(best_cost, 0xFF, sizeof(best_cost));
        memset(best_hops, 0xFF, sizeof(best_hops));
        memset(visited, 0, sizeof(visited));

        /* Find anchor vertex index */
        int anchor_vertex_idx = -1;
        for (uint32_t v = 0; v < graph->vertex_count; v++) {
            if (hacf_digest_cmp(&graph->vertices[v].vertex_identity,
                                 &anchor->anchor_vertex_digest) == 0) {
                anchor_vertex_idx = (int)v;
                break;
            }
        }
        if (anchor_vertex_idx < 0) continue; /* Anchor vertex not found in graph */

        /* Initialize Dijkstra */
        dijkstra_heap_t heap;
        heap.size = 0;
        best_cost[anchor_vertex_idx] = 0;
        best_hops[anchor_vertex_idx] = 0;

        dijkstra_entry_t start = {0};
        start.cost = 0;
        start.hops = 0;
        start.anchor_priority = anchor->priority;
        memcpy(&start.anchor_digest, &anchor_id, HACF_DIGEST_BYTES);
        memcpy(&start.vertex_digest, &graph->vertices[anchor_vertex_idx].vertex_identity,
               HACF_DIGEST_BYTES);
        heap_push(&heap, start);

        while (heap.size > 0) {
            dijkstra_entry_t cur = heap_pop(&heap);
            int cur_idx = -1;
            for (uint32_t v = 0; v < graph->vertex_count; v++) {
                if (hacf_digest_cmp(&graph->vertices[v].vertex_identity,
                                     &cur.vertex_digest) == 0) {
                    cur_idx = (int)v;
                    break;
                }
            }
            if (cur_idx < 0) continue;
            if (visited[cur_idx]) continue;
            visited[cur_idx] = 1;

            /* Traverse incidences connected to current vertex */
            for (uint32_t inc_idx = 0; inc_idx < graph->incidence_count; inc_idx++) {
                const topology_incidence_v1 *inc = &graph->incidences[inc_idx];

                /* Determine traversal direction */
                int neighbor_idx = -1;
                if (hacf_digest_cmp(&inc->node_vertex_digest, &cur.vertex_digest) == 0) {
                    /* Node vertex -> hyperedge vertex */
                    for (uint32_t v = 0; v < graph->vertex_count; v++) {
                        if (hacf_digest_cmp(&graph->vertices[v].vertex_identity,
                                             &inc->hyperedge_vertex_digest) == 0) {
                            neighbor_idx = (int)v;
                            break;
                        }
                    }
                } else if (hacf_digest_cmp(&inc->hyperedge_vertex_digest, &cur.vertex_digest) == 0) {
                    /* Hyperedge vertex -> node vertex */
                    for (uint32_t v = 0; v < graph->vertex_count; v++) {
                        if (hacf_digest_cmp(&graph->vertices[v].vertex_identity,
                                             &inc->node_vertex_digest) == 0) {
                            neighbor_idx = (int)v;
                            break;
                        }
                    }
                }

                if (neighbor_idx < 0 || visited[neighbor_idx]) continue;

                /* Only traverse semantic relations */
                const topology_relation_entry_v1 *entry = NULL;
                for (uint32_t r = 0; r < registry->entry_count; r++) {
                    if (registry->entries[r].topology_class == inc->relation_class) {
                        entry = &registry->entries[r];
                        break;
                    }
                }
                if (!entry || entry->classification == TOPOLOGY_CLASSIFICATION_TRANSPORT) continue;
                if (entry->traversal_cost == 0) continue;

                uint32_t new_cost = cur.cost + inc->traversal_cost;
                uint32_t new_hops = cur.hops + 1;

                if (new_cost > policy->max_semantic_path_cost) continue;
                if (new_hops > policy->max_semantic_path_hops) continue;
                if (new_cost >= best_cost[neighbor_idx]) continue;

                best_cost[neighbor_idx] = new_cost;
                best_hops[neighbor_idx] = new_hops;

                dijkstra_entry_t next = {0};
                next.cost = new_cost;
                next.hops = new_hops;
                next.anchor_priority = anchor->priority;
                memcpy(&next.anchor_digest, &anchor_id, HACF_DIGEST_BYTES);
                memcpy(&next.vertex_digest, &graph->vertices[neighbor_idx].vertex_identity,
                       HACF_DIGEST_BYTES);
                memcpy(&next.pred_vertex, &cur.vertex_digest, HACF_DIGEST_BYTES);
                memcpy(&next.pred_incidence, &inc->incidence_identity, HACF_DIGEST_BYTES);
                heap_push(&heap, next);
            }
        }

        /* Record distance for each reachable vertex */
        for (int v = 0; v < (int)graph->vertex_count; v++) {
            if (visited[v]) {
                if (record_idx < TOPOLOGY_DEFAULT_MAX_VERTICES) {
                    topology_distance_record_v1 *rec = &constellations->distance_records[record_idx];
                    memset(rec, 0, sizeof(*rec));
                    memcpy(&rec->target_vertex_digest, &graph->vertices[v].vertex_identity,
                           HACF_DIGEST_BYTES);
                    memcpy(&rec->anchor_digest, &anchor_id, HACF_DIGEST_BYTES);
                    rec->semantic_cost = best_cost[v];
                    rec->hop_count = best_hops[v];
                    record_idx++;
                }
            }
        }
    }

    constellations->distance_record_count = record_idx;
    return SEMANTIC_OK;
}
